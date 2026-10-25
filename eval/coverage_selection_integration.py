"""Paired installed-wheel/public-stdio selector experiment; no product mocks.

Reuses the existing SQLite fixture and V40 independent source oracle. Input
questions/corpora are unchanged. Gold is opened ONLY after every delivery.
This measures evidence coverage, NOT generated-answer correctness or billing.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import time

POLICIES = ("fixed", "adaptive-gap-b1-v1", "mmr-budget-v1", "facet-cover-v1", "facet-guarded-v1",
            "facet-cover-v2", "facet-guarded-v2", "facet-bundled-v1", "facet-bundled-cover-v1", "semantic-audit-v1", "semantic-rescue-v1", "semantic-prune-v1")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inputs(args):
    if args.suite == "v40":
        base = args.repo / "eval/prepared_model_comparison40"
        cases = json.loads((base / "questions.json").read_text())["cases"]
        plan = json.loads((base / "source_plan.json").read_text())["families"]
        docs = {f["id"]: {p: (base / "sources" / f["id"] / p).read_text(encoding="utf-8")
                          for p in f["paths"]} for f in plan}
    elif args.suite == "new16":
        value = json.loads((args.repo / "eval/adaptive_gap_holdout/inputs.json").read_text())
        cases, docs = value["cases"], {f["id"]: f["documents"] for f in value["families"]}
    else:
        base = args.repo / "eval/fresh_dialogues/fixtures"
        cases = json.loads((base / "cases.json").read_text())["cases"]
        cases = [{**case, "project_group": "nacre"} for case in cases]
        docs = {"nacre": {str(p.relative_to(base / "project")): p.read_text(encoding="utf-8")
                           for p in sorted((base / "project").rglob("*.md"))}}
    return cases, docs


def request(case, root):
    result = {"question": case["question"], "project_path": str(root), "scope": "project"}
    for name in ("search_question", "lookup_queries"):
        if name in case:
            result[name] = case[name]
    return result


def candidate_fingerprint(rows):
    keys = ("path_or_url", "section", "line_start", "line_end", "snippet", "scope", "version_binding", "authority")
    values = sorted((json.dumps([r.get(k) for k in keys], ensure_ascii=False) for r in rows))
    return digest(json.dumps(values, ensure_ascii=False).encode())


def worker(args):
    import yaml
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.section_compression import observe_section_compression
    runtime = load("coverage_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = load("coverage_state", args.repo / "eval/prepared_model_comparison40/run.py")
    cases, families = inputs(args)
    cases = [c for c in cases if c["project_group"] == args.family]
    root, out = args.work / args.family / "project", args.out / args.family
    runtime.write_project(root, families[args.family])
    catalog_path = root / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    catalog["documentation_languages"] = {p: ["en"] for p in families[args.family]}
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    with runtime.isolated_service(args.work / args.family / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before = (helper.logical_state(inventory), helper.source_state(root))
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="off", DOCATLAS_CONTEXT_ABSTENTION="off")
        for case in cases:
            payload = call_docs_tool_payload("get_docs_context", request(case, root), service)
            assert payload.get("kind") == "docs_context", payload
            save(out / (case["id"] + "-pool.json"), payload)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="minilm-sections-v1",
            DOCATLAS_MINILM_MODEL_DIR=str(args.model), DOCATLAS_MCP_MODEL_VIEW="1",
            DOCATLAS_MCP_TEXT_FALLBACK="1", DOCATLAS_SECTION_TOP_K="5",
            DOCATLAS_SECTION_UNITS="markdown-owner-v1" if (args.policy=="facet-guarded-v1" or args.policy.startswith("semantic-")) else "legacy",
            DOCATLAS_SUFFICIENCY_MODEL_DIR=str(args.qa_model), DOCATLAS_SECTION_WIRE_FORMAT="v1",
            DOCATLAS_SECTION_SELECTION=args.policy, HF_HUB_OFFLINE="1")
        with observe_section_compression() as observations:
            try:
                asyncio.run(_run_async(service))
            finally:
                save(out / "server.json", {"observations": observations,
                    "database_unchanged": before[0] == helper.logical_state(inventory),
                    "files_unchanged": before[1] == helper.source_state(root),
                    "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024})


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.interfaces.host_context import extract_tool_payload
    from docmancer.docs.application.section_compression import expand_sections
    from docmancer.docs.application.model_context_view import resolve_model_reference
    import tiktoken
    encoder = tiktoken.get_encoding("o200k_base")
    cases, families = inputs(args)
    records, prompts = [], []
    for family in families:
        out = args.out / family
        out.mkdir(parents=True)
        root = args.work / family / "project"
        params = StdioServerParameters(command=sys.executable, args=["-I", str(Path(__file__).resolve()),
            "--worker", "--family", family, "--suite", args.suite, "--policy", args.policy,
            "--repo", str(args.repo), "--work", str(args.work), "--out", str(args.out),
            "--model", str(args.model), "--qa-model", str(args.qa_model)], env=dict(os.environ))
        with (out / "stderr.log").open("w") as err:
          async with stdio_client(params, errlog=err) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                await session.initialize()
                profile = await session.call_tool("docs_status", {
                    "action": "project", "project_path": str(root), "include_language": True})
                assert not profile.isError
                assert json.loads(profile.content[0].text)["documentation_language"]["languages"] == ["en"]
                for case in (c for c in cases if c["project_group"] == family):
                    before = time.monotonic()
                    response = await session.call_tool("get_docs_context", request(case, root))
                    elapsed = time.monotonic() - before
                    raw = response.model_dump(by_alias=True)
                    save(out / (case["id"] + "-response.json"), raw)
                    pool = json.loads((out / (case["id"] + "-pool.json")).read_text())
                    record = {"case_id": case["id"], "family": family, "seconds": elapsed,
                        "question": case["question"], "search_question": case.get("search_question"),
                        "candidate_fingerprint": candidate_fingerprint(pool.get("sources", [])),
                        "candidate_rows": len(pool.get("sources", [])), "runtime_error": bool(response.isError)}
                    if response.isError:
                        record["error"] = raw
                        records.append(record)
                        continue
                    packet = extract_tool_payload(response)
                    expanded = expand_sections(packet)
                    wire = response.content[0].text
                    view = json.loads(wire)
                    assert view["context_format"] == "docatlas.model-context.v1"
                    assert expanded["answer_supported"] is False and expanded["answer_available"] is False
                    originals = {r["evidence_id"]: r for r in pool.get("sources", [])}
                    for item, row in zip(view["sources"], expanded["sources"], strict=True):
                        assert row == originals[row["evidence_id"]], "whole acquired source changed"
                        assert item["text"] == row["snippet"]
                        assert resolve_model_reference(view, raw["_meta"], item["ref"]) == row
                    save(out / (case["id"] + "-expanded.json"), expanded)
                    (out / (case["id"] + "-wire.json")).write_text(wire, encoding="utf-8")
                    instruction = "Answer only from the supplied evidence. Cite source refs. Retain conditions and exceptions. Identify unsupported parts; do not invent them."
                    prompt = instruction + "\n" + case["question"] + "\n" + wire
                    record.update(tokens=len(encoder.encode(wire)), prepared_input_tokens=len(encoder.encode(prompt)),
                        rows=len(expanded["sources"]), whole_source_rows=True)
                    prompts.append({"case_id": case["id"], "question": case["question"], "context": wire,
                        "instruction": instruction, "context_sha256": digest(wire.encode())})
                    records.append(record)
        server = json.loads((out / "server.json").read_text())
        assert server["database_unchanged"] and server["files_unchanged"]
        assert server["rss_peak_bytes"] <= 1_500_000_000
        good = [r for r in records if r["family"] == family and not r["runtime_error"]]
        assert len(server["observations"]) == len(good)
        for record, obs in zip(good, server["observations"], strict=True):
            assert obs["candidate_rows"] == record["candidate_rows"]
            assert obs["selection_policy"] == args.policy
            assert obs["scoring_question_sha256"] == digest((record["search_question"] or record["question"]).encode())
            semantic = obs.get("semantic_sufficiency") or {}
            record.update(groups=obs["selected_sections"], forward_passes=obs["forward_passes"],
                probe_count=obs.get("selection_diagnostics", {}).get("probe_count", 1),
                semantic_status=semantic.get("status"), semantic_added=semantic.get("added_groups", 0),
                semantic_removed=semantic.get("removed_groups", 0),
                semantic_qa_seconds=semantic.get("runtime_seconds", 0),
                semantic_probes_scored=semantic.get("probes_scored", 0),
                semantic_unknown=len(semantic.get("probes_unscored", [])))
    save(args.out / "DELIVERY.json", records)
    (args.out / "PROMPTS.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in prompts), encoding="utf-8")
    return records


def assess(args, records):
    cases, families = inputs(args)
    corpus = args.repo / "eval/prepared_model_comparison40"
    oracle = load("coverage_oracle", corpus / "evaluate.py")
    paths = {"v40": corpus / "gold_spans.json", "new16": args.repo / "eval/adaptive_gap_holdout/gold.json",
             "fresh8": args.repo / "eval/fresh_dialogues/oracle/gold.json"}
    gold = {r["id"]: r for r in json.loads(paths[args.suite].read_text())["cases"]}
    for row in records:
        case = next(c for c in cases if c["id"] == row["case_id"])
        item = gold[row["case_id"]]
        kind = case.get("answerability") or {"full": "within_budget", "partial": "partial", "no_answer": "unanswerable"}[item["category"]]
        row["answerability"] = kind
        if row["runtime_error"]:
            row.update(passed=False, integrity=False, claims=[])
            continue
        prepared = {"root": str(args.work / row["family"] / "project"), "sources": {}}
        for path, text in families[row["family"]].items():
            offsets = [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared["sources"][path] = {"raw": text.encode(), "content": text,
                "sha256": digest(text.encode()), "line_offsets": offsets, "errors": []}
        payload = json.loads((args.out / row["family"] / (row["case_id"] + "-expanded.json")).read_text())
        _, intervals, errors = oracle._source_rows(payload, prepared)
        claims = []
        if args.suite == "v40":
            coverage = oracle._gold(case, item, prepared, intervals)
            errors += coverage.get("errors", [])
            claims = [{"id": c["claim_id"], "covered": c["covered"]} for c in coverage["claims"] if c["documented"]]
        else:
            if args.suite == "new16":
                facts = [{"id": str(i), "witnesses": [{"path": item["path"], "text": q}]} for i, q in enumerate(item["witnesses"])]
            else:
                facts = item["required_facts"]
            for fact in facts:
                covered = []
                for w in fact["witnesses"]:
                    text = prepared["sources"][w["path"]]["content"]
                    assert text.count(w["text"]) == 1, "ambiguous independent witness"
                    start = text.index(w["text"])
                    covered.append(not oracle._uncovered(start, start + len(w["text"]), intervals.get(w["path"], [])))
                claims.append({"id": fact["id"], "covered": all(covered)})
        row.update(claims=claims, integrity=not errors, errors=errors,
            passed=not errors and (not payload["sources"] if kind == "unanswerable" else all(c["covered"] for c in claims)))
    summary = {"head": os.environ.get("TESTED_SHA"), "suite": args.suite, "policy": args.policy,
        "cases": len(records), "runtime_errors": sum(r["runtime_error"] for r in records),
        "integrity_errors": sum(not r["integrity"] for r in records),
        "counts": {k: {"passed": sum(r["passed"] for r in records if r["answerability"] == k),
                        "total": sum(r["answerability"] == k for r in records)} for k in ("within_budget", "partial", "unanswerable")},
        "required_facts": sum(len(r["claims"]) for r in records),
        "retained_facts": sum(c["covered"] for r in records for c in r["claims"]),
        "model_visible_tokens": sum(r.get("tokens", 0) for r in records),
        "prepared_input_tokens": sum(r.get("prepared_input_tokens", 0) for r in records),
        "seconds_total": sum(r["seconds"] for r in records),
        "seconds_median": statistics.median(r["seconds"] for r in records),
        "forward_passes": sum(r.get("forward_passes", 0) for r in records),
        "qa_seconds": sum(r.get("semantic_qa_seconds", 0) for r in records),
        "semantic_gap_cases": [r["case_id"] for r in records if r.get("semantic_status") == "candidate_gap"],
        "qa_probe_count": sum(r.get("semantic_probes_scored", 0) for r in records),
        "stdio_search_calls": len(records), "baseline_public_calls": len(records), "language_calls": len(families),
        "answer_model_calls": 0, "provider_usage": None,
        "boundary": "installed wheel; real SQLite, CPU MiniLM, public stdio; evidence not final-answer accuracy"}
    save(args.out / "ASSESSMENTS.json", records)
    save(args.out / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    assert not summary["runtime_errors"] and not summary["integrity_errors"], "execution/integrity failure, not successful quality evaluation"


def main():
    p = argparse.ArgumentParser()
    for name in ("repo", "work", "out", "model", "qa-model"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--suite", choices=("v40", "new16", "fresh8"), required=True)
    p.add_argument("--policy", choices=POLICIES, required=True)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--family")
    args = p.parse_args()
    args.qa_model = args.qa_model.resolve()
    if args.worker:
        return worker(args)
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo), "installed wheel required"
    assert all(f.read_bytes() == (args.repo / "docmancer" / f.relative_to(origin)).read_bytes() for f in origin.rglob("*.py"))
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    # Freeze bytes without reading gold's content into retrieval or scoring.
    dirs = ("prepared_model_comparison40", "adaptive_gap_holdout", "fresh_dialogues/fixtures", "fresh_dialogues/oracle")
    hashes = {str(f.relative_to(args.repo)): digest(f.read_bytes()) for d in dirs
              for f in sorted((args.repo / "eval" / d).rglob("*")) if f.is_file() and "__pycache__" not in f.parts}
    save(args.out / "FREEZE.json", {"head": os.environ.get("TESTED_SHA"), "files": hashes, "policies": POLICIES})
    records = asyncio.run(client(args))
    assess(args, records)
    assert all(digest((args.repo / f).read_bytes()) == h for f, h in hashes.items())


if __name__ == "__main__":
    main()
