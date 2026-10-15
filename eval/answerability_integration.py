"""Real installed stdio MCP acceptance; no mocked retrieval, model or storage.

80 paired context calls (40 compressed baseline + 40 gated), five SQLite
preparations. Gold is read only after all client responses are saved.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import time
from datetime import timedelta


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_cases(repo):
    base = repo / "eval/prepared_model_comparison40"
    cases = json.loads((base / "questions.json").read_text())["cases"]
    families = json.loads((base / "source_plan.json").read_text())["families"]
    assert len(cases) == 40
    return base, cases, families


def worker(args):
    runtime = module("answerability_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = module("answerability_helpers", args.repo / "eval/prepared_model_comparison40/run.py")
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.answerability import observe_answerability
    corpus, cases, families = load_cases(args.repo)
    family = next(f for f in families if f["id"] == args.family)
    root = args.work / args.family / "project"
    docs = {p: (corpus / "sources" / args.family / p).read_text(encoding="utf-8") for p in family["paths"]}
    runtime.write_project(root, docs)
    with runtime.isolated_service(args.work / args.family / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before_db, before_files = helper.logical_state(inventory), helper.source_state(root)
        out = args.out / args.family
        save(out / "preparation.json", inventory)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="minilm-sections-v1",
                          DOCATLAS_MINILM_MODEL_DIR=str(args.model),
                          DOCATLAS_ABSTENTION_MODEL_DIR=str(args.qa_model),
                          DOCATLAS_ABSTENTION_LANGUAGE="en", DOCATLAS_CONTEXT_ABSTENTION="off",
                          DOCATLAS_MCP_TEXT_FALLBACK="1", HF_HUB_OFFLINE="1")
        with observe_answerability() as observations:
            for case in (c for c in cases if c["project_group"] == args.family):
                request = {"question": case["question"], "project_path": str(root), "scope": "project"}
                baseline = call_docs_tool_payload("get_docs_context", request, service)
                save(out / (case["id"] + "-baseline.json"), baseline)
            assert observations == []
            os.environ["DOCATLAS_CONTEXT_ABSTENTION"] = "enforce"
            try:
                asyncio.run(_run_async(service))
            finally:
                peak = Path("/sys/fs/cgroup/memory.peak")
                save(out / "server.json", {"observations": observations,
                      "database_unchanged": helper.logical_state(inventory) == before_db,
                      "files_unchanged": helper.source_state(root) == before_files,
                      "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                      "container_memory_peak": int(peak.read_text()) if peak.exists() else None})


async def client(args):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections
    _, cases, families = load_cases(args.repo)
    records = []
    for family in families:
        group = family["id"]
        out = args.out / group
        out.mkdir(parents=True)
        params = StdioServerParameters(command=sys.executable, args=["-I", str(Path(__file__).resolve()),
            "--worker", "--family", group, "--repo", str(args.repo), "--work", str(args.work),
            "--out", str(args.out), "--model", str(args.model), "--qa-model", str(args.qa_model)], env=dict(os.environ))
        with (out / "stderr.log").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                    await session.initialize()
                    for case in (c for c in cases if c["project_group"] == group):
                        request = {"question": case["question"], "project_path": str(args.work / group / "project"), "scope": "project"}
                        begin = time.perf_counter()
                        response = await session.call_tool("get_docs_context", request)
                        elapsed = time.perf_counter() - begin
                        assert len(response.content) == 1 and response.content[0].type == "text"
                        wire = response.content[0].text
                        (out / (case["id"] + "-wire.json")).write_text(wire, encoding="utf-8")
                        raw = json.loads(wire)
                        payload = expand_sections(raw)
                        baseline = expand_sections(json.loads((out / (case["id"] + "-baseline.json")).read_text()))
                        if not response.isError:
                            if payload.get("sources"):
                                assert payload == baseline, "pass-through must retain every baseline field and source"
                            else:
                                assert payload.get("reason_code") == "answer_not_found_in_acquired_context", payload
                                assert not payload.get("read_next") and not payload.get("source_groups")
                                assert payload.get("answer_supported") is False and payload.get("edit_ready") is False
                                assert payload.get("answerability", {}).get("corpus_absence_proven") is False
                        save(out / (case["id"] + "-expanded.json"), payload)
                        record = {"case_id": case["id"], "family": group, "is_error": bool(response.isError),
                                  "refused": not response.isError and not payload.get("sources"), "seconds": elapsed,
                                  "reason_code": (payload.get("error") or {}).get("reason_code") or payload.get("reason_code")}
                        records.append(record)
                        print(json.dumps(record), flush=True)
        server = json.loads((out / "server.json").read_text())
        assert server["database_unchanged"] and server["files_unchanged"]
    return records


def assess(args, records):
    corpus, cases, families = load_cases(args.repo)
    oracle = module("answerability_independent_oracle", corpus / "evaluate.py")
    gold = {c["id"]: c for c in json.loads((corpus / "gold_spans.json").read_text())["cases"]}
    by_case, by_family = {c["id"]: c for c in cases}, {f["id"]: f for f in families}
    rows = []
    for r in records:
        case = by_case[r["case_id"]]
        prepared = {"root": str(args.work / r["family"] / "project"), "sources": {}}
        for path in by_family[r["family"]]["paths"]:
            data = (corpus / "sources" / r["family"] / path).read_bytes()
            text, offsets = data.decode("utf-8"), [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared["sources"][path] = {"raw": data, "content": text, "sha256": sha(data), "line_offsets": offsets, "errors": []}
        payload = json.loads((args.out / r["family"] / (r["case_id"] + "-expanded.json")).read_text())
        verified, intervals, errors = oracle._source_rows(payload, prepared)
        coverage = oracle._gold(case, gold[case["id"]], prepared, intervals)
        passed = not r["is_error"] and not errors and not coverage.get("errors") and (
            r["refused"] if case["answerability"] == "unanswerable" else coverage["all_documented_claims_covered"])
        rows.append({**r, "kind": case["answerability"], "pass": passed, "errors": errors, "coverage": coverage})
    servers = [json.loads((args.out / f["id"] / "server.json").read_text()) for f in families]
    summary = {"head": os.environ.get("TESTED_SHA"), "cases": len(rows),
               "counts": {kind: {"total": sum(r["kind"] == kind for r in rows), "pass": sum(r["pass"] for r in rows if r["kind"] == kind)}
                          for kind in sorted({r["kind"] for r in rows})},
               "failed": [r["case_id"] for r in rows if not r["pass"]],
               "operational_errors": sum(r["is_error"] for r in rows),
               "server_rss_peak_bytes": max(s["rss_peak_bytes"] for s in servers),
               "container_peak_bytes": max(s["container_memory_peak"] or 0 for s in servers),
               "seconds_median": statistics.median(r["seconds"] for r in rows),
               "public_calls": 80, "preparations": 5,
               "boundary": "installed wheel, real SQLite, actual public stdio client; unchanged independent gold"}
    save(args.out / "ASSESSMENTS.json", rows)
    save(args.out / "SUMMARY.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    assert all(r["pass"] for r in rows), "Unchanged all40 semantic acceptance gate FAILED"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("repo", "work", "out", "model", "qa-model"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--family")
    args = parser.parse_args()
    for key in ("repo", "work", "out", "model", "qa_model"):
        setattr(args, key, getattr(args, key).resolve())
    if args.worker:
        worker(args)
        return
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo), "Installed package required"
    product = {str(p.relative_to(origin)): sha(p.read_bytes()) for p in origin.rglob("*.py")}
    assert all(sha((args.repo / "docmancer" / p).read_bytes()) == h for p, h in product.items())
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    corpus, _, _ = load_cases(args.repo)
    frozen = {str(p.relative_to(args.repo)): sha(p.read_bytes()) for p in corpus.rglob("*") if p.is_file()}
    save(args.out / "FREEZE.json", {"head": os.environ.get("TESTED_SHA"), "installed": product, "inputs": frozen,
                                   "model": json.loads((args.qa_model / "manifest.json").read_text()),
                                   "policy": "all checked contiguous source intervals; CLS null vs span; threshold0; max_answer30; seq384; stride128; no tuning"})
    records = asyncio.run(client(args))
    assert all(sha((args.repo / p).read_bytes()) == h for p, h in frozen.items())
    assess(args, records)


if __name__ == "__main__":
    main()
