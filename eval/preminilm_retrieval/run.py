"""One frozen arm through an installed wheel, real prepare/SQLite/MCP stdio.

The coordinator runs three fresh containers sequentially with identical /work
paths. Execution never imports gold or supplies labels to retrieval or MiniLM.
Quality failures remain measurements; source/state/incomplete-run failures fail.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import time
import traceback
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ARMS, DATASETS, dataset, documents, load, read, rows_from_wire,
                    save, sha, source_intervals, verify_freeze)
from observe_sql import observe_sql


def check_install(args) -> dict:
    import docmancer
    origin = Path(docmancer.__file__).resolve().parent
    if origin.is_relative_to(args.repo) or not origin.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("product must come from the selected installed wheel, not checkout")
    if Path(sys.prefix).resolve() != args.python.parent.parent.resolve():
        raise ValueError("wrong installed interpreter")
    checked = {}
    with zipfile.ZipFile(args.wheel) as wheel:
        for name in wheel.namelist():
            if name.startswith("docmancer/") and not name.endswith("/"):
                expected = wheel.read(name)
                target = origin.parent / name
                source = args.source_root / name
                if target.read_bytes() != expected or source.read_bytes() != expected:
                    raise ValueError("installed/source/wheel bytes differ: " + name)
                checked[name] = sha(expected)
    return {"origin": str(origin), "python": sys.executable, "prefix": sys.prefix,
            "wheel": str(args.wheel), "wheel_sha256": sha(args.wheel.read_bytes()),
            "checked_files": checked}


def selected_environment(arm: str) -> dict[str, str]:
    settings = {
        "DOCATLAS_MINILM_MODEL_DIR": "/model",
        "DOCATLAS_CONTEXT_COMPRESSION": "minilm-sections-v1",
        "DOCATLAS_SECTION_SELECTION": "facet-guarded-lexical-v2",
        "DOCATLAS_SECTION_UNITS": "markdown-owner-v1",
        "DOCATLAS_CONTEXT_ASSEMBLY": "adaptive",
        "DOCATLAS_MCP_TEXT_FALLBACK": "1", "DOCATLAS_MCP_COMPACT_TEXT": "1",
        "DOCATLAS_MCP_MODEL_VIEW": "off", "DOCATLAS_TRACE": "0",
        "HF_HUB_OFFLINE": "1", "DOCATLAS_OFFLINE": "1",
    }
    if arm != "main":
        settings["DOCATLAS_ACQUISITION_POLICY"] = arm
    return settings


def worker(args) -> None:
    verify_freeze(args.repo, args.freeze, holdout="new20" in args.datasets)
    installed = check_install(args)
    runtime = load("preminilm_fixture_runtime", args.repo / "eval/evidence_quality_v2/runtime.py")
    state = load("preminilm_fixture_state", args.repo / "eval/heuristic_removal/receipts.py")
    from docmancer.mcp._docs_server_part01 import _run_async
    from docmancer.docs.application.experimental_candidate_selection import experimental_selection_observer
    from docmancer.docs.application.section_compression import observe_section_compression

    _, groups = dataset(args.repo, args.dataset)
    docs = documents(args.repo, args.dataset, args.family, groups[args.family])
    root = args.work / args.dataset / args.family / "project"
    folder = args.out / args.dataset / args.family
    runtime.write_project(root, docs)
    with observe_sql() as sql, runtime.isolated_service(root.parent / "state") as (service, config):
        # isolated_service intentionally clears host DOCATLAS settings. Set the
        # frozen arm only inside this context, before the real preparation.
        os.environ.update(selected_environment(args.arm))
        if args.arm == "main":
            os.environ.pop("DOCATLAS_ACQUISITION_POLICY", None)
        inventory = runtime.index_project(service, config, root)
        snapshots = state.snapshots(inventory, root, docs)
        save(folder / "PREPARE.json", {"root": str(root), "inventory": inventory,
             "snapshot_sources": snapshots,
             "source_sha256": {p: sha(v.encode("utf-8")) for p, v in docs.items()},
             "installed": installed, "environment": selected_environment(args.arm)})
        before_db, before_files = state.database(inventory["storage_path"]), state.files(root)
        native = []
        with experimental_selection_observer(native.append) as native_state, observe_section_compression() as mini:
            try:
                sql["active"] = True
                asyncio.run(_run_async(service))
            finally:
                sql["active"] = False
                save(folder / "NATIVE.json", native)
                save(folder / "MINILM.json", mini)
                save(folder / "SQL.json", sql)
                save(folder / "STATE.json", {
                    "native_observer_calls": native_state.calls,
                    "native_observer_errors": native_state.errors,
                    "database_unchanged": state.database(inventory["storage_path"]) == before_db,
                    "files_unchanged": state.files(root) == before_files,
                })


def unpack(reply) -> tuple[dict, str]:
    if reply.structuredContent is not None or len(reply.content) != 1 or reply.content[0].type != "text":
        raise ValueError("unexpected OpenCode text transport shape")
    text = reply.content[0].text
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("tool text must be an object")
    return payload, text


def append_event(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")


async def execute(args) -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    frozen = verify_freeze(args.repo, args.freeze, holdout="new20" in args.datasets)
    if args.out.exists() or args.work.exists():
        raise ValueError("fresh output and /work required; never overwrite an attempt")
    args.out.mkdir(parents=True)
    args.work.mkdir(parents=True, mode=0o700)
    expected = sum(DATASETS[name][1] for name in args.datasets)
    summary = {"arm": args.arm, "baseline_sha": frozen["baseline_sha"],
               "candidate_sha": frozen["candidate_sha"], "datasets": args.datasets,
               "context_calls": 0, "preparations": 0, "safety_calls": 0,
               "paid_model_calls": 0, "expected_context_calls": expected,
               "status": "running", "records": [], "invariant_errors": [],
               "autonomous_opencode": "NOT_TESTED", "provider_usage": None}
    ledger = args.out / "EXECUTION_LEDGER.jsonl"
    started = time.monotonic()
    try:
        for name in args.datasets:
            cases, families = dataset(args.repo, name)
            for family, paths in families.items():
                selected = [c for c in cases if c["project_group"] == family]
                if not selected:
                    continue
                folder = args.out / name / family
                folder.mkdir(parents=True)
                root = args.work / name / family / "project"
                docs = documents(args.repo, name, family, paths)
                command = ["-I", str(Path(__file__).resolve()), "--worker", "--repo", str(args.repo),
                           "--source-root", str(args.source_root), "--wheel", str(args.wheel),
                           "--python", str(args.python), "--arm", args.arm,
                           "--datasets", ",".join(args.datasets), "--dataset", name, "--family", family,
                           "--work", str(args.work), "--out", str(args.out), "--freeze", str(args.freeze)]
                env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH" and not k.startswith("DOCATLAS_")}
                env.update(HF_HUB_OFFLINE="1", PYTHONNOUSERSITE="1")
                params = StdioServerParameters(command=str(args.python), args=command, env=env)
                append_event(ledger, {"operation": "prepare_and_start_server", "status": "started",
                                     "dataset": name, "family": family})
                with (folder / "STDERR.log").open("w", encoding="utf-8") as stderr:
                    async with stdio_client(params, errlog=stderr) as streams:
                        async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=240)) as session:
                            await session.initialize()
                            summary["preparations"] += 1
                            listed = await session.list_tools()
                            if {t.name for t in listed.tools} != {"get_docs_context", "prepare_docs", "docs_status"}:
                                raise ValueError("default public tool catalog changed")
                            for position, case in enumerate(selected):
                                arguments = {"question": case["question"], "project_path": str(root), "scope": "project"}
                                append_event(ledger, {"operation": "get_docs_context", "status": "started",
                                                     "dataset": name, "case_id": case["id"], "arguments": arguments})
                                summary["context_calls"] += 1
                                call_started = time.monotonic()
                                reply = await session.call_tool("get_docs_context", arguments)
                                call_finished = time.monotonic()
                                elapsed = call_finished - call_started
                                payload, text = unpack(reply)
                                source_rows = rows_from_wire(payload)
                                _, source_errors = source_intervals(source_rows, docs, str(root))
                                if any(payload.get(k) is True for k in ("answer_supported", "answer_available", "edit_ready")):
                                    source_errors.append({"error": "retrieval-only authority escalation"})
                                record = {
                                    "id": case["id"], "dataset": name, "family": family,
                                    "answerability": case["answerability"], "root": str(root),
                                    "question": case["question"], "is_error": bool(reply.isError),
                                    "status": payload.get("status"), "kind": payload.get("kind"),
                                    "error": payload.get("error"),
                                    "format": payload.get("context_format"), "rows": len(source_rows),
                                    "utf8_bytes": len(text.encode("utf-8")),
                                    "o200k_tokens": projection_token_count(text.encode("utf-8")),
                                    "seconds": elapsed, "first_call_in_server": position == 0,
                                    "call_started_monotonic": call_started,
                                    "call_finished_monotonic": call_finished,
                                    "source_errors": source_errors,
                                }
                                save(folder / (case["id"] + "-reply.json"), reply.model_dump(mode="json", by_alias=True))
                                save(folder / (case["id"] + "-payload.json"), payload)
                                save(folder / (case["id"] + "-record.json"), record)
                                summary["records"].append(record)
                                append_event(ledger, {"operation": "get_docs_context", "status": "returned",
                                                     "dataset": name, "case_id": case["id"], "seconds": elapsed,
                                                     "is_error": bool(reply.isError)})
                                print(json.dumps(record, ensure_ascii=False), flush=True)
                                if source_errors:
                                    raise ValueError("source fidelity invariant failed: " + case["id"])
                            # One explicit scope-denial call per arm; never count
                            # an error as an inexpensive documentation success.
                            if summary["safety_calls"] == 0:
                                summary["safety_calls"] += 1
                                safety_started = time.monotonic()
                                denied = await session.call_tool("get_docs_context", {
                                    "question": selected[0]["question"], "project_path": str(root),
                                    "scope": "module", "module_path": "__absent_preminilm_control__"})
                                safety_finished = time.monotonic()
                                packet, _ = unpack(denied)
                                if rows_from_wire(packet) or packet.get("status") not in {"failed", "insufficient_evidence"}:
                                    raise ValueError("unavailable scope returned evidence")
                                save(folder / "SCOPE_DENIAL.json", denied.model_dump(mode="json", by_alias=True))
                                save(folder / "SCOPE_DENIAL_RECORD.json", {
                                    "call_started_monotonic": safety_started,
                                    "call_finished_monotonic": safety_finished,
                                    "seconds": safety_finished - safety_started,
                                    "status": packet.get("status"), "is_error": bool(denied.isError)})
                                append_event(ledger, {"operation": "scope_denial_control", "status": "returned",
                                                     "dataset": name, "family": family})
                observer = read(folder / "STATE.json")
                sql = read(folder / "SQL.json")
                if (observer["native_observer_errors"] or not observer["database_unchanged"]
                        or not observer["files_unchanged"] or sql["errors"]
                        or sql["connections"] != sql["attached_connections"]):
                    raise ValueError("observer/state invariant failed: " + name + "/" + family)
                native = read(folder / "NATIVE.json")
                generation = read(folder / "PREPARE.json")["inventory"]["generation_id"]
                if observer["native_observer_calls"] != len(native):
                    raise ValueError("missing native observer receipts")
                for receipt in native:
                    _, errors = source_intervals(receipt["pool"], docs, str(root), candidate=True,
                                                 generation=generation)
                    if errors:
                        raise ValueError("native source fidelity failed: " + repr(errors[:3]))
                append_event(ledger, {"operation": "server_completed", "status": "returned",
                                     "dataset": name, "family": family, "observer": observer})
                save(args.out / "SUMMARY.json", summary)
        verify_freeze(args.repo, args.freeze, holdout="new20" in args.datasets)
        if summary["context_calls"] != expected or summary["safety_calls"] != 1:
            raise ValueError("incomplete operation counts")
        summary["status"] = "completed"
    except Exception as exc:
        summary["status"] = "incomplete_or_invariant_failure"
        summary["invariant_errors"].append({"error": str(exc), "traceback": traceback.format_exc()})
    finally:
        summary["seconds"] = time.monotonic() - started
        save(args.out / "SUMMARY.json", summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "records"}), flush=True)
    return 0 if summary["status"] == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "source-root", "wheel", "python", "work", "out", "freeze"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--datasets", default="v40,new20")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--dataset", choices=DATASETS)
    parser.add_argument("--family")
    args = parser.parse_args()
    for name in ("repo", "source_root", "wheel", "work", "out", "freeze"):
        setattr(args, name, getattr(args, name).resolve())
    args.python = args.python.absolute()
    args.datasets = args.datasets.split(",")
    if len(set(args.datasets)) != len(args.datasets) or any(n not in DATASETS for n in args.datasets):
        parser.error("datasets must be a unique comma-separated subset of v40,new20")
    if args.worker:
        if args.dataset not in args.datasets or not args.family:
            parser.error("worker needs selected dataset and family")
        worker(args)
        return 0
    return asyncio.run(execute(args))


if __name__ == "__main__":
    raise SystemExit(main())
