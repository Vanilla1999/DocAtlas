"""Live installed-MCP selection study. No scorer/retrieval/storage mocks.

Gold is opened only after every response is persisted. Quality FAIL is reported
separately from successful execution. Answers are not fabricated by this driver:
PROMPTS.jsonl contains only actual delivered contexts for a separate answerer.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
from datetime import timedelta
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import statistics
import sys
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inputs(args):
    if args.suite == "v40":
        corpus = args.repo / "eval/prepared_model_comparison40"
        cases = json.loads((corpus / "questions.json").read_text())["cases"]
        families = json.loads((corpus / "source_plan.json").read_text())["families"]
        docs = {f["id"]: {p: (corpus / "sources" / f["id"] / p).read_text(encoding="utf-8")
                          for p in f["paths"]} for f in families}
        assert len(cases) == 40
    else:
        value = json.loads((args.repo / "eval/adaptive_gap_holdout/inputs.json").read_text())
        cases = value["cases"]
        docs = {f["id"]: f["documents"] for f in value["families"]}
        assert len(cases) == 16
    return cases, docs


def request(case, root):
    result = {"question": case["question"], "project_path": str(root), "scope": "project"}
    if case.get("search_question"):
        result["search_question"] = case["search_question"]
    return result


def worker(args):
    import yaml
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime = load("adaptive_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load("adaptive_state", args.repo / "eval/prepared_model_comparison40/run.py")
    cases, families = inputs(args)
    cases = [c for c in cases if c["project_group"] == args.family]
    root = args.work / args.family / "project"
    out = args.out / args.family
    runtime.write_project(root, families[args.family])
    if args.suite == "holdout":
        catalog = root / "docatlas.project-docs.yaml"
        value = yaml.safe_load(catalog.read_text())
        value["documentation_languages"] = {p: ["en"] for p in families[args.family]}
        catalog.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    with runtime.isolated_service(args.work / args.family / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before = (helper.logical_state(inventory), helper.source_state(root))
        save(out / "preparation.json", {"root": str(root), "inventory": inventory})
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="off", DOCATLAS_CONTEXT_ABSTENTION="off")
        for case in cases:
            original = call_docs_tool_payload("get_docs_context", request(case, root), service)
            assert original.get("kind") == "docs_context" and original.get("sources"), original
            save(out / (case["id"] + "-baseline.json"), original)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="minilm-sections-v1",
            DOCATLAS_MINILM_MODEL_DIR=str(args.model), DOCATLAS_MCP_TEXT_FALLBACK="1",
            DOCATLAS_MCP_MODEL_VIEW="1", DOCATLAS_SECTION_TOP_K="5",
            DOCATLAS_SECTION_UNITS="legacy", DOCATLAS_SECTION_WIRE_FORMAT="v1",
            DOCATLAS_SECTION_SELECTION=args.policy, HF_HUB_OFFLINE="1")
        with observe_section_compression() as observations:
            try:
                asyncio.run(_run_async(service))
            finally:
                peak = Path("/sys/fs/cgroup/memory.peak")
                save(out / "server.json", {
                    "observations": observations,
                    "database_unchanged": before[0] == helper.logical_state(inventory),
                    "files_unchanged": before[1] == helper.source_state(root),
                    "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                    "container_memory_peak": int(peak.read_text()) if peak.exists() else None,
                    "versions": {n: importlib.metadata.version(n) for n in
                                 ("onnxruntime", "tokenizers", "mcp", "tiktoken")}})


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections
    from docmancer.docs.application.model_context_view import resolve_model_reference
    from docmancer.docs.interfaces.host_context import extract_tool_payload
    import tiktoken
    encodings = {name: tiktoken.get_encoding(name) for name in ("o200k_base", "cl100k_base")}
    cases, families = inputs(args)
    records, controls, prompts = [], [], []
    for family in families:
        folder = args.out / family
        folder.mkdir(parents=True)
        root = args.work / family / "project"
        params = StdioServerParameters(command=sys.executable, args=[
            "-I", str(Path(__file__).resolve()), "--worker", "--family", family,
            "--suite", args.suite, "--policy", args.policy, "--repo", str(args.repo),
            "--work", str(args.work), "--out", str(args.out), "--model", str(args.model)],
            env=dict(os.environ))
        with (folder / "stderr.log").open("w") as err:
            async with stdio_client(params, errlog=err) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                    await session.initialize()
                    assert {t.name for t in (await session.list_tools()).tools} == {
                        "docs_status", "get_docs_context", "prepare_docs"}
                    if args.suite == "holdout":
                        status = await session.call_tool("docs_status", {
                            "action": "project", "project_path": str(root), "include_language": True})
                        assert not status.isError
                        profile = json.loads(status.content[0].text)["documentation_language"]
                        assert profile["status"] == "declared" and profile["languages"] == ["en"]
                        save(folder / "language.json", profile)
                    for case in (c for c in cases if c["project_group"] == family):
                        started = time.perf_counter()
                        req = request(case, root)
                        response = await session.call_tool("get_docs_context", req)
                        elapsed = time.perf_counter() - started
                        raw = response.model_dump(by_alias=True)
                        save(folder / (case["id"] + "-response.json"), raw)
                        assert not response.isError, raw
                        assert response.structuredContent is None
                        assert len(response.content) == 1 and response.content[0].type == "text"
                        text = response.content[0].text
                        display = json.loads(text)
                        packet = extract_tool_payload(response)
                        expanded = expand_sections(packet)
                        assert display["context_format"] == "docatlas.model-context.v1"
                        assert expanded["sources"] and expanded["answer_supported"] is False
                        baseline = json.loads((folder / (case["id"] + "-baseline.json")).read_text())
                        old = {r["evidence_id"]: r for r in baseline["sources"]}
                        assert all(r == old[r["evidence_id"]] for r in expanded["sources"])
                        for item, row in zip(display["sources"], expanded["sources"], strict=True):
                            assert item["text"] == row["snippet"]
                            assert resolve_model_reference(display, raw["_meta"], item["ref"]) == row
                        (folder / (case["id"] + "-wire.json")).write_text(text, encoding="utf-8")
                        save(folder / (case["id"] + "-expanded.json"), expanded)
                        measured = {name: len(enc.encode(text)) for name, enc in encodings.items()}
                        assert max(measured["o200k_base"], math.ceil(len(text.encode()) / 4)) <= 12000
                        machine = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
                        records.append({"case_id": case["id"], "family": family,
                            "answerability": case["answerability"], "question": case["question"],
                            "search_question": req.get("search_question"), "tokens": measured,
                            "machine_o200k": len(encodings["o200k_base"].encode(machine)),
                            "rows": len(expanded["sources"]), "seconds": elapsed,
                            "model_text_sha256": sha(text.encode()), "whole_source_rows": True})
                        prompts.append({"case_id": case["id"], "question": case["question"],
                            "context": text, "context_sha256": sha(text.encode()),
                            "instruction": "Answer only from the supplied evidence in the question language. Cite exact source refs. Preserve conditions and exceptions. Identify unsupported parts; do not invent them."})
                        print(json.dumps({"case_id":case["id"], "tokens":measured,
                                          "rows":len(expanded["sources"]), "seconds":round(elapsed,3)}), flush=True)
                    if args.suite == "holdout" and family == "aster":
                        overflow = await session.call_tool("get_docs_context", {
                            "question": "lease " * 140, "project_path": str(root), "scope": "project"})
                        error = json.loads(overflow.content[0].text)
                        save(folder / "query-overflow.json", overflow.model_dump(by_alias=True))
                        assert overflow.isError and error["error"]["reason_code"] == "section_compression_query_limit", error
                        controls.append("query_limit_no_silent_truncation")
                        row = next(r for r in expanded["sources"] if r.get("source_uri"))
                        result = await session.read_resource(row["source_uri"])
                        value = json.loads(result.contents[0].text)
                        save(folder / "source-read.json", value)
                        assert value["status"] in ("complete", "truncated"), value
                        controls.append("issued_source_read")
        report = json.loads((folder / "server.json").read_text())
        assert report["database_unchanged"] and report["files_unchanged"]
        assert report["rss_peak_bytes"] <= 1_000_000_000
        selected_cases = [c for c in cases if c["project_group"] == family]
        assert len(report["observations"]) == len(selected_cases)
        for case, obs in zip(selected_cases, report["observations"], strict=True):
            record = next(r for r in records if r["case_id"] == case["id"])
            expanded = json.loads((folder / (case["id"] + "-expanded.json")).read_text())
            assert obs["selection_policy"] == args.policy
            assert obs["scoring_question_sha256"] == sha((case.get("search_question") or case["question"]).encode())
            assert set(obs["selected_evidence_ids"]) == {r["evidence_id"] for r in expanded["sources"]}
            record.update(selected_groups=obs["selected_sections"], candidates=obs["candidate_sections"],
                          forward_passes=obs["forward_passes"], cutoff=obs.get("adaptive_cutoff"))
    save(args.out / "DELIVERY.json", {"records":records, "controls":controls,
        "stdio_search_calls":len(records), "public_baseline_calls":len(records),
        "preparations":len(families), "language_calls":len(families) if args.suite=="holdout" else 0,
        "paid_selection_calls":0, "answer_model_calls":0})
    (args.out / "PROMPTS.jsonl").write_text("".join(json.dumps(p,ensure_ascii=False)+"\n" for p in prompts), encoding="utf-8")
    return records


def assess(args, records):
    cases, families = inputs(args)
    corpus = args.repo / "eval/prepared_model_comparison40"
    oracle = load("adaptive_independent_oracle", corpus / "evaluate.py")
    goldpath = corpus / "gold_spans.json" if args.suite == "v40" else args.repo / "eval/adaptive_gap_holdout/gold.json"
    gold = {g["id"]: g for g in json.loads(goldpath.read_text())["cases"]}
    results = []
    for record in records:
        case = next(c for c in cases if c["id"] == record["case_id"])
        root = args.work / record["family"] / "project"
        prepared = {"root":str(root), "sources":{}}
        for path, text in families[record["family"]].items():
            offsets=[0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1]+len(line))
            prepared["sources"][path] = {"raw":text.encode(), "content":text,
                "sha256":sha(text.encode()), "line_offsets":offsets, "errors":[]}
        payload = json.loads((args.out/record["family"]/(case["id"]+"-expanded.json")).read_text())
        _, intervals, errors = oracle._source_rows(payload, prepared)
        if args.suite == "v40":
            coverage = oracle._gold(case, gold[case["id"]], prepared, intervals)
        else:
            item = gold[case["id"]]
            source = prepared["sources"][item["path"]]["content"]
            witnesses=[]
            for quote in item["witnesses"]:
                assert source.count(quote) == 1, (case["id"],quote)
                start=source.index(quote)
                missing=oracle._uncovered(start,start+len(quote),intervals.get(item["path"],[]))
                witnesses.append({"quote":quote,"covered":not missing,"missing_ranges":missing})
            coverage={"all_documented_claims_covered":all(w["covered"] for w in witnesses),
                      "witnesses":witnesses,"unsupported":item.get("unsupported"),"errors":[]}
        valid = not errors and not coverage.get("errors")
        passed = valid and (not payload["sources"] if case["answerability"] == "unanswerable"
                           else coverage["all_documented_claims_covered"])
        results.append({**record,"integrity":valid,"passed":passed,"coverage":coverage,"errors":errors})
    reports=[json.loads((args.out/f/"server.json").read_text()) for f in families]
    summary={"head":os.environ.get("TESTED_SHA"),"suite":args.suite,"policy":args.policy,
        "cases":len(results),"counts":{kind:{"total":sum(r["answerability"]==kind for r in results),
            "pass":sum(r["passed"] for r in results if r["answerability"]==kind)}
            for kind in ("within_budget","partial","unanswerable")},
        "quality_gate_passed":all(r["passed"] for r in results if r["answerability"]!="unanswerable"),
        "integrity_pass":sum(r["integrity"] for r in results),
        "failed_documented_ids":[r["case_id"] for r in results if not r["passed"] and r["answerability"]!="unanswerable"],
        "tokens_mean":{e:statistics.mean(r["tokens"][e] for r in results) for e in ("o200k_base","cl100k_base")},
        "tokens_max":max(r["tokens"]["o200k_base"] for r in results),
        "machine_tokens_mean":statistics.mean(r["machine_o200k"] for r in results),
        "k_histogram":dict(Counter(r["selected_groups"] for r in results)),
        "mean_k":statistics.mean(r["selected_groups"] for r in results),
        "seconds_median":statistics.median(r["seconds"] for r in results),
        "container_peak_bytes":max(r["container_memory_peak"] or 0 for r in reports),
        "semantic_refusal_implemented":False,"answer_model_calls":0,"provider_usage":None,
        "boundary":"new installed-wheel, real SQLite, real CPU ONNX, public stdio MCP; not answer generation"}
    save(args.out/"ASSESSMENTS.json",results)
    save(args.out/"SUMMARY.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    assert all(r["integrity"] for r in results), "source integrity regression"
    assert summary["container_peak_bytes"] <= 1_000_000_000


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for flag in ("repo","work","out","model"):
        ap.add_argument("--"+flag,type=Path,required=True)
    ap.add_argument("--suite",choices=("v40","holdout"),required=True)
    ap.add_argument("--policy",choices=("fixed","adaptive-gap-v1"),required=True)
    ap.add_argument("--worker",action="store_true")
    ap.add_argument("--family")
    args=ap.parse_args()
    for key in ("repo","work","out","model"):
        setattr(args,key,getattr(args,key).resolve())
    if args.worker:
        worker(args)
        return
    import docmancer
    product=Path(docmancer.__file__).resolve().parent
    assert not product.is_relative_to(args.repo), "installed wheel required"
    hashes={str(p.relative_to(product)):sha(p.read_bytes()) for p in product.rglob("*.py")}
    assert all(sha((args.repo/"docmancer"/p).read_bytes())==h for p,h in hashes.items())
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True,mode=0o700)
    args.out.mkdir(parents=True)
    inputs_root=args.repo/("eval/prepared_model_comparison40" if args.suite=="v40" else "eval/adaptive_gap_holdout")
    frozen={str(p.relative_to(args.repo)):sha(p.read_bytes()) for p in inputs_root.rglob("*") if p.is_file()}
    save(args.out/"FREEZE.json",{"head":os.environ.get("TESTED_SHA"),"installed":hashes,
        "corpus":frozen,"policy":args.policy,"suite":args.suite,"python":sys.version,
        "selection":"fixed5 or full first90%-gap, B0, cap5; no fitted thresholds"})
    records=asyncio.run(client(args))
    assess(args,records)
    assert all(sha((args.repo/p).read_bytes())==h for p,h in frozen.items())


if __name__ == "__main__":
    main()
