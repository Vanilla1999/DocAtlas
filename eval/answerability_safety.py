"""Installed public-MCP safety acceptance, NOT a semantic refusal success gate.

No fake reader/retrieval/storage. The full V40 oracle is used only after delivery.
Historical semantic evaluators and their failed artifacts are intentionally kept.
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
import sys
import time

DOCUMENT = '''# Aster Service

## Network

Aster listens on port 8127. Enable TLS by setting transport = "tls".

## Refresh

The refresh interval is 17 seconds. Set refresh_enabled = false to disable refresh.
'''
# These are independent public integration controls, not inference rules.
CONTROLS = {
    "observe_positive": ("What port does Aster listen on?", "observe", "en", None),
    "observe_absent": ("Who founded Aster?", "observe", "en", None),
    "observe_partial": ("What port does Aster listen on, and who founded Aster?", "observe", "en", None),
    "declared_russian": ("Какой порт использует Aster?", "observe", "ru", None),
    "off_missing_assets": ("What port does Aster listen on?", "off", "en", None),
    "enforce_blocked": ("What port does Aster listen on?", "enforce", "en", "answerability_enforcement_not_validated"),
    "enforce_without_assets": ("What port does Aster listen on?", "enforce", "en", "answerability_enforcement_not_validated"),
    "observe_missing_assets": ("What port does Aster listen on?", "observe", "en", "answerability_model_unavailable_or_corrupt"),
    "observe_query_limit": ("What port does Aster listen on? " * 15, "observe", "en", "answerability_query_limit"),
    "invalid_mode": ("What port does Aster listen on?", "automatic", "en", "answerability_invalid_config"),
}


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load evaluator: {path}")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cases_and_families(repo: Path):
    corpus = repo / "eval/prepared_model_comparison40"
    cases = json.loads((corpus / "questions.json").read_text(encoding="utf-8"))["cases"]
    families = json.loads((corpus / "source_plan.json").read_text(encoding="utf-8"))["families"]
    if len(cases) != 40:
        raise RuntimeError("Expected unchanged V40")
    return corpus, cases, families


def group_cases(args, group: str) -> list[dict]:
    if group in CONTROLS:
        return [{"id": group, "question": CONTROLS[group][0]}]
    return [c for c in cases_and_families(args.repo)[1] if c["project_group"] == group]


def worker(args) -> None:
    from docmancer.mcp._docs_server_part01 import _run_async, call_docs_tool_payload
    from docmancer.docs.application.answerability import observe_answerability
    runtime = module("safety_fixture", args.repo / "eval/evidence_quality_v2/runtime.py")
    helper = module("safety_state", args.repo / "eval/prepared_model_comparison40/run.py")
    control = args.group in CONTROLS
    root = args.work / args.group / "project"
    out = args.out / args.group
    if control:
        docs = {"README.md": DOCUMENT}
        _, setting, language, _ = CONTROLS[args.group]
    else:
        corpus, _, families = cases_and_families(args.repo)
        family = next(f for f in families if f["id"] == args.group)
        docs = {p: (corpus / "sources" / args.group / p).read_text(encoding="utf-8") for p in family["paths"]}
        setting, language = "observe", "en"
    runtime.write_project(root, docs)
    with runtime.isolated_service(args.work / args.group / "state") as (service, config):
        inventory = runtime.index_project(service, config, root)
        before_db, before_files = helper.logical_state(inventory), helper.source_state(root)
        save(out / "preparation.json", inventory)
        os.environ.update(DOCATLAS_CONTEXT_COMPRESSION="off" if control else "minilm-sections-v1",
                          DOCATLAS_MINILM_MODEL_DIR=str(args.model),
                          DOCATLAS_CONTEXT_ABSTENTION="off", DOCATLAS_MCP_TEXT_FALLBACK="1",
                          DOCATLAS_ABSTENTION_LANGUAGE=language, HF_HUB_OFFLINE="1")
        missing = args.group in {"off_missing_assets", "enforce_without_assets", "observe_missing_assets"}
        os.environ["DOCATLAS_ABSTENTION_MODEL_DIR"] = str(args.work / "missing" if missing else args.qa_model)
        with observe_answerability() as observations:
            for case in group_cases(args, args.group):
                request = {"question": case["question"], "project_path": str(root), "scope": "project"}
                save(out / (case["id"] + "-baseline.json"), call_docs_tool_payload("get_docs_context", request, service))
            assert observations == [], "off must not run the QA observer"
            os.environ["DOCATLAS_CONTEXT_ABSTENTION"] = setting
            try:
                asyncio.run(_run_async(service))
            finally:
                peak = Path("/sys/fs/cgroup/memory.peak")
                save(out / "server.json", {
                    "observations": observations,
                    "database_unchanged": helper.logical_state(inventory) == before_db,
                    "files_unchanged": helper.source_state(root) == before_files,
                    "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
                    "container_peak_bytes": int(peak.read_text()) if peak.exists() else None,
                })


async def run_clients(args, groups: list[str]) -> list[dict]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.section_compression import expand_sections
    from docmancer.docs.application.context_json import serialize_context_json
    records = []
    for group in groups:
        out = args.out / group
        out.mkdir(parents=True, exist_ok=True)
        params = StdioServerParameters(command=sys.executable, args=[
            "-I", str(Path(__file__).resolve()), "--worker", "--group", group,
            "--repo", str(args.repo), "--work", str(args.work), "--out", str(args.out),
            "--model", str(args.model), "--qa-model", str(args.qa_model)], env=dict(os.environ))
        with (out / "stderr.log").open("w", encoding="utf-8") as err:
            async with stdio_client(params, errlog=err) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
                    await session.initialize()
                    for case in group_cases(args, group):
                        request = {"question": case["question"], "project_path": str(args.work / group / "project"), "scope": "project"}
                        begin = time.perf_counter()
                        response = await session.call_tool("get_docs_context", request)
                        elapsed = time.perf_counter() - begin
                        assert len(response.content) == 1 and response.content[0].type == "text"
                        wire = response.content[0].text
                        (out / (case["id"] + "-wire.json")).write_text(wire, encoding="utf-8")
                        payload = json.loads(wire)
                        baseline = json.loads((out / (case["id"] + "-baseline.json")).read_text(encoding="utf-8"))
                        expected_error = CONTROLS[group][3] if group in CONTROLS else None
                        code = (payload.get("error") or {}).get("reason_code")
                        if expected_error:
                            passed = bool(response.isError and code == expected_error and not payload.get("sources") and not payload.get("read_next"))
                            unchanged = None
                        else:
                            unchanged = payload == baseline and wire == serialize_context_json(baseline)
                            passed = bool(not response.isError and unchanged and expand_sections(payload).get("sources"))
                        save(out / (case["id"] + "-expanded.json"), expand_sections(payload))
                        records.append({"case_id": case["id"], "group": group, "pass": passed,
                                        "is_error": bool(response.isError), "reason_code": code,
                                        "response_and_wire_unchanged": unchanged, "seconds": elapsed})
                        print(json.dumps(records[-1]), flush=True)
        server = json.loads((out / "server.json").read_text(encoding="utf-8"))
        assert server["database_unchanged"] and server["files_unchanged"], group
        observations = server["observations"]
        if group in CONTROLS:
            setting = CONTROLS[group][1]
            if setting != "observe" or CONTROLS[group][3]:
                assert observations == [], "blocked/failed/off calls cannot claim semantic decisions"
            else:
                assert len(observations) == 1
                if group == "declared_russian":
                    assert observations[0]["decision"] == "unknown" and not observations[0]["scan_complete"]
        else:
            assert len(observations) == len(group_cases(args, group))
    return records


def assess_v40(args, records: list[dict]) -> dict:
    corpus, cases, families = cases_and_families(args.repo)
    oracle = module("safety_independent_oracle", corpus / "evaluate.py")
    gold = {c["id"]: c for c in json.loads((corpus / "gold_spans.json").read_text(encoding="utf-8"))["cases"]}
    by_case, by_family = {c["id"]: c for c in cases}, {f["id"]: f for f in families}
    assessments = []
    for record in records:
        if record["group"] in CONTROLS:
            continue
        case, family = by_case[record["case_id"]], record["group"]
        prepared = {"root": str(args.work / family / "project"), "sources": {}}
        for path in by_family[family]["paths"]:
            data = (corpus / "sources" / family / path).read_bytes()
            content, offsets = data.decode("utf-8"), [0]
            for line in content.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared["sources"][path] = {"raw": data, "content": content, "sha256": sha(data), "line_offsets": offsets, "errors": []}
        payload = json.loads((args.out / family / (case["id"] + "-expanded.json")).read_text(encoding="utf-8"))
        _, intervals, errors = oracle._source_rows(payload, prepared)
        coverage = oracle._gold(case, gold[case["id"]], prepared, intervals)
        semantic_pass = not record["is_error"] and not errors and not coverage.get("errors") and (
            not payload.get("sources") if case["answerability"] == "unanswerable" else coverage["all_documented_claims_covered"])
        assessments.append({**record, "kind": case["answerability"], "semantic_pass": bool(semantic_pass),
                            "source_errors": errors, "coverage": coverage})
    save(args.out / "V40_ASSESSMENTS.json", assessments)
    counts = {kind: {"total": sum(r["kind"] == kind for r in assessments),
                     "pass": sum(r["semantic_pass"] for r in assessments if r["kind"] == kind)}
              for kind in sorted({r["kind"] for r in assessments})}
    return {"counts": counts, "semantic_gate_passed": bool(assessments) and all(r["semantic_pass"] for r in assessments),
            "failed": [r["case_id"] for r in assessments if not r["semantic_pass"]]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("repo", "work", "out", "model", "qa-model"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--suite", choices=("all", "controls"), default="all")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--group")
    args = parser.parse_args()
    for key in ("repo", "work", "out", "model", "qa_model"):
        setattr(args, key, getattr(args, key).resolve())
    if args.worker:
        worker(args)
        return
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(args.repo), "installed wheel required"
    product = {str(p.relative_to(origin)): sha(p.read_bytes()) for p in origin.rglob("*.py")}
    assert all(sha((args.repo / "docmancer" / p).read_bytes()) == h for p, h in product.items())
    assert not args.work.exists() and not args.out.exists()
    args.work.mkdir(parents=True, mode=0o700)
    args.out.mkdir(parents=True)
    corpus, _, families = cases_and_families(args.repo)
    frozen = {str(p.relative_to(args.repo)): sha(p.read_bytes()) for p in corpus.rglob("*") if p.is_file()}
    save(args.out / "FREEZE.json", {"head": os.environ.get("TESTED_SHA"), "product": product,
        "inputs": frozen, "controls": CONTROLS, "document_sha256": sha(DOCUMENT.encode()),
        "training_permitted": False, "purpose": "observation safety, not semantic enforcement acceptance",
        "qa_manifest": json.loads((args.qa_model / "manifest.json").read_text(encoding="utf-8"))})
    groups = ([] if args.suite == "controls" else [f["id"] for f in families]) + list(CONTROLS)
    records = asyncio.run(run_clients(args, groups))
    assert all(sha((args.repo / p).read_bytes()) == h for p, h in frozen.items())
    semantic = assess_v40(args, records) if args.suite == "all" else {"semantic_gate_passed": False, "status": "NOT_EVALUATED"}
    servers = [json.loads((args.out / group / "server.json").read_text(encoding="utf-8")) for group in groups]
    diagnostic_nulls = sum(o["decision"] == "no_answer" for s in servers for o in s["observations"])
    useful_preserved = args.suite == "controls" or all(
        semantic["counts"][k]["pass"] == semantic["counts"][k]["total"] for k in ("within_budget", "partial"))
    accepted = bool(records) and all(r["pass"] for r in records) and useful_preserved
    report = {"head": os.environ.get("TESTED_SHA"), "safety_gate_passed": accepted,
        "semantic_acceptance": semantic, "automatic_refusal_implemented": False,
        "public_context_calls": 2 * len(records), "stdio_calls": len(records), "preparations": len(groups),
        "cases": records, "diagnostic_no_answer_predictions_not_enforced": diagnostic_nulls,
        "rss_peak_bytes": max(s["rss_peak_bytes"] for s in servers),
        "container_peak_bytes": max(s["container_peak_bytes"] or 0 for s in servers),
        "source_and_database_unchanged": all(s["database_unchanged"] and s["files_unchanged"] for s in servers),
        "boundary": "installed wheel; real SQLite; public in-process baselines and real stdio experimental responses"}
    save(args.out / "SUMMARY.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2), flush=True)
    if not accepted:
        raise SystemExit("Observation safety gate FAILED; see SUMMARY.json")


if __name__ == "__main__":
    main()
