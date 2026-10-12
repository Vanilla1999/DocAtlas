"""Bounded paired integration run through the installed public DocAtlas API.

This driver never imports the oracle or supplies annotations to retrieval. It
records the actual public JSON before any offline assessment. There is one real
preparation per project family and one public context call per case and arm.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager, redirect_stderr
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import resource
import signal
import sqlite3
import subprocess
import sys
import time
import traceback


REPO = Path(__file__).resolve().parents[2]
CORPUS = Path(__file__).resolve().parent
ADMISSION = "source_valid_candidates_v1"
TOP_K = 2
FINAL_CAP = 12000
MODES = ("legacy", "prepared_parent_v1")
MAX_PUBLIC_CALL_SECONDS = 60


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def time_limit(seconds: int):
    def expired(signum, frame):
        raise TimeoutError(f"operation exceeded the frozen {seconds}-second limit")
    prior = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prior)


def logical_state(inventory: dict) -> dict:
    """Independent, read-only state checks; no expected implementation snapshot."""
    with closing(sqlite3.connect(Path(inventory["storage_path"]).as_uri() + "?mode=ro", uri=True)) as db:
        schema = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name",
        ).fetchall()
        tables = {}
        for name, _ in schema:
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(db.execute(f"SELECT * FROM {quoted}").fetchall(), key=repr)
            tables[name] = {"rows": len(rows), "sha256": sha(repr(rows).encode("utf-8"))}
    result = {"schema_sha256": sha(repr(schema).encode("utf-8")), "tables": tables}
    result["sha256"] = sha(canonical(result))
    return result


def source_state(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def committed_sources(inventory: dict, root: Path, documents: dict) -> tuple[list, dict]:
    with closing(sqlite3.connect(Path(inventory["storage_path"]).as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(
            "SELECT generation_id, source, source_identity, content, content_hash, metadata_json "
            "FROM generation_sources WHERE generation_id=? ORDER BY source", (inventory["generation_id"],),
        )]
        prepared = json.loads(db.execute(
            "SELECT validation_json FROM index_generations WHERE generation_id=?",
            (inventory["generation_id"],),
        ).fetchone()[0]).get("prepared_parents")
    receipts = []
    for row in rows:
        relative = Path(row["source"]).relative_to(root).as_posix()
        content = row.pop("content")
        row.update(path=relative, content_sha256=sha(content.encode("utf-8")),
                   metadata=json.loads(row.pop("metadata_json")),
                   matches_pinned_source=relative in documents and content == documents[relative])
        receipts.append(row)
    if {row["path"] for row in receipts} != set(documents) or not all(
        row["matches_pinned_source"] for row in receipts
    ):
        raise RuntimeError("published source snapshot differs from the pinned corpus")
    if not prepared:
        raise RuntimeError("prepared structure manifest is missing after enabled indexing")
    return receipts, prepared


def versions() -> dict:
    result = {"python": sys.version, "platform": platform.platform(), "executable": sys.executable}
    for package in ("doc-atlas", "torch", "transformers", "tokenizers", "safetensors", "tiktoken"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def freeze_manifest(model_path=None) -> dict:
    frozen=[p for p in CORPUS.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    frozen.extend((REPO/"docmancer").rglob("*.py"))
    frozen.extend((REPO/"eval/structural_assembly40").rglob("*.py"))
    frozen.extend([REPO/"pyproject.toml",REPO/"eval/evidence_quality_v2/runtime.py"])
    inputs={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in sorted(set(frozen))}
    return {"schema_version":2,"frozen_at_utc":now(),
      "base_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
      "corpus":"historical exposed V40; not blind holdout","question_count":40,
      "arms":list(MODES),"top_k":TOP_K,"final_json_cap":FINAL_CAP,
      "admission":ADMISSION,"prepared_parents":True,"scope":"project",
      "public_tool":"get_docs_context","models_called":0,
      "assembly":{"legacy":"joint/query_block/recovery","prepared_parent_v1":"owner section with native seed fallback"},
      "inputs_sha256":inputs,"runtime":versions()}


def pair_receipt(case: dict, records: dict, inventories: dict) -> dict:
    receipts = {mode: records[mode]["receipts"] for mode in MODES}
    details = {}
    for field in ("pool", "complete_candidates", "excluded"):
        values = {mode: [r[field] for r in receipts[mode]] for mode in MODES}
        details[field] = {"equal": values["legacy"] == values["prepared_parent_v1"],
                          **{mode + "_sha256": sha(canonical(values[mode])) for mode in MODES}}
    public_success = all(
        records[m]["metadata"]["status"] == "returned"
        and isinstance(records[m]["payload"], dict)
        and records[m]["payload"].get("kind") == "docs_context" for m in MODES
    )
    no_stage = public_success and not receipts["legacy"] and not receipts["prepared_parent_v1"]
    observation_ok = all(not records[m]["metadata"]["observation_errors"] for m in MODES)
    cardinality_ok = all(len(receipts[m]) == 1 for m in MODES) or no_stage
    equal = all(item["equal"] for item in details.values())
    chosen = {}
    for mode in MODES:
        chosen[mode] = [sorted(r["pool"][index]["id"] for index in r["selection"].get("selected_indices", []))
                        for r in receipts[mode]]
    return {
        "case_id": case["id"], "question": case["question"],
        "status": "not_reached_both" if no_stage and observation_ok else "paired" if equal and observation_ok and cardinality_ok and public_success else "unpaired",
        "receipt_count": {m: len(receipts[m]) for m in MODES}, "observation_ok": observation_ok,
        "receipt_cardinality_ok": cardinality_ok,
        "same_preselection_inputs": equal, "inputs": details,
        "pool_sizes": {m: [len(r["pool"]) for r in receipts[m]] for m in MODES},
        "over_budget_pool": any(len(r["pool"]) > TOP_K for r in receipts["legacy"]),
        "selected_set_changed": chosen["legacy"] != chosen["prepared_parent_v1"],
        "public_dto_changed": records["legacy"]["payload"] != records["prepared_parent_v1"]["payload"],
        "public_success_both": public_success,
        "generation_id": inventories["generation_id"],
    }


def run(args) -> int:
    started = time.perf_counter()
    run_dir, work_dir = args.run_dir.resolve(), args.work_dir.resolve()
    model_path = None
    if run_dir.exists() or work_dir.exists():
        raise ValueError("run/work directories must be new; existing attempts are never overwritten")
    if work_dir.is_relative_to(REPO) or run_dir.is_relative_to(work_dir):
        raise ValueError("isolated runtime must be outside the repository and report output")
    cases = json.loads((CORPUS / "questions.json").read_text())["cases"]
    plan = json.loads((CORPUS / "source_plan.json").read_text())
    if len(cases) != 40 or len({c["id"] for c in cases}) != 40 or len(plan["families"]) != 5:
        raise ValueError("this frozen driver requires the complete V40 corpus")
    run_dir.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    manifest = freeze_manifest(model_path)
    save(run_dir / "RUN_MANIFEST.json", manifest)
    (run_dir / "candidate.patch").write_bytes(subprocess.check_output(["git", "diff", "HEAD"], cwd=REPO))
    ledger_path = run_dir / "ledger.jsonl"
    def ledger(operation, status, **fields):
        with ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at_utc": now(), "operation": operation, "status": status, **fields},
                                    ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    summary = {"status": "running", "started_at_utc": now(), "preparations_attempted": 0,
               "context_calls_attempted": 0, "context_calls_returned": 0,
               "model_forward_attempts": 0, "model_forwards": 0,
               "source_continuation_calls": 0, "answer_generator_calls": 0, "pairs": []}
    def checkpoint():
        summary.update(elapsed_seconds=time.perf_counter()-started,
                       process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        save(run_dir / "raw-run-summary.json", summary)
    from eval.evidence_quality_v2 import runtime
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application.experimental_candidate_selection import experimental_selection_observer
    from docmancer.docs.application.query_trace import query_trace
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    try:
        ledger("model_preparation","not_needed",forwards=0)
        for family in plan["families"]:
            group = family["id"]
            root, state = work_dir / "projects" / group, work_dir / "state" / group
            documents = {name: (CORPUS / "sources" / group / name).read_bytes().decode("utf-8")
                         for name in family["paths"]}
            runtime.write_project(root, documents)
            with runtime.isolated_service(state) as (service, config):
                os.environ.update(DOCATLAS_EXPERIMENT_PREPARED_PARENTS="1",
                                  DOCATLAS_EXPERIMENT_ADMISSION=ADMISSION,
                                  DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS=str(FINAL_CAP),
                                  DOCATLAS_EXPERIMENT_SELECTOR_TOP_K=str(TOP_K),
                                  DOCATLAS_EXPERIMENT_MINI_PATH=str(model_path))
                summary["preparations_attempted"] += 1
                ledger("prepare_docs", "started", family=group, project_root=str(root))
                with time_limit(180):
                    inventory = runtime.index_project(service, config, root)
                sources, prepared = committed_sources(inventory, root, documents)
                original_db, original_files = logical_state(inventory), source_state(root)
                prep_path = run_dir / "preparation" / (group + ".json")
                save(prep_path, {"family": group, "root": str(root), "inventory": inventory,
                                 "snapshot_sources": sources, "prepared_manifest": prepared,
                                 "initial_database_state": original_db, "initial_file_hashes": original_files})
                ledger("prepare_docs", "returned", family=group, seconds=inventory["seconds"],
                       generation_id=inventory["generation_id"], prepared_manifest=bool(prepared))
                for case_index, case in enumerate(cases):
                    if case["project_group"] != group:
                        continue
                    order = MODES if case_index % 2 == 0 else MODES[::-1]
                    records = {}
                    for mode in order:
                        before_db, before_files = logical_state(inventory), source_state(root)
                        if before_db != original_db or before_files != original_files:
                            raise RuntimeError("state changed before an arm; no further context calls")
                        os.environ["DOCATLAS_EXPERIMENT_SELECTOR"] = "budget"
                        os.environ["DOCATLAS_EXPERIMENT_ASSEMBLER"] = mode
                        arguments = {"question": case["question"], "project_path": str(root), "scope": "project"}
                        destination = run_dir / "calls" / case["id"] / mode
                        destination.mkdir(parents=True)
                        receipts, trace, payload = [], io.StringIO(), None
                        meta = {"case_id": case["id"], "mode": mode, "question": case["question"],
                                "public_request": deepcopy(arguments), "project_root": str(root),
                                "inventory_path": str(prep_path), "status": "started", "started_at_utc": now(),
                                "database_sha256_before": before_db["sha256"],
                                "source_files_sha256_before": sha(canonical(before_files)),
                                "same_initial_state": True}
                        save(destination / "metadata.json", meta)
                        summary["context_calls_attempted"] += 1
                        ledger("get_docs_context", "started", case_id=case["id"], mode=mode)
                        checkpoint()
                        call_start, cpu_start = time.perf_counter(), time.process_time()
                        with experimental_selection_observer(receipts.append) as observation:
                            try:
                                with redirect_stderr(trace), query_trace(True), time_limit(MAX_PUBLIC_CALL_SECONDS):
                                    payload = call_docs_tool_payload("get_docs_context", arguments, service)
                                meta["status"] = "returned"
                                summary["context_calls_returned"] += 1
                            except Exception as exc:
                                meta.update(status="error", error_type=type(exc).__name__, error=str(exc),
                                            traceback=traceback.format_exc())
                            finally:
                                meta.update(elapsed_seconds=time.perf_counter()-call_start,
                                            process_cpu_seconds=time.process_time()-cpu_start)
                        meta.update(observation_calls=observation.calls, observation_errors=observation.errors,
                                    process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                        after_call_db, after_call_files = logical_state(inventory), source_state(root)
                        meta.update(database_unchanged=after_call_db == original_db,
                                    project_files_unchanged=after_call_files == original_files,
                                    database_sha256_after=after_call_db["sha256"],
                                    source_files_sha256_after=sha(canonical(after_call_files)))
                        if payload is not None:
                            # Exact public serialization: no private snapshots or diagnostic fields added.
                            wire = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
                            (destination / "public-payload.json").write_bytes(wire)
                            meta.update(wire_sha256=sha(wire), wire_utf8_bytes=len(wire),
                                        utf8_quarter_proxy=(len(wire)+3)//4,
                                        codec_o200k_base=projection_token_count(wire),
                                        public_source_count=len(payload.get("sources") or []))
                            meta["within_wire_budget"] = max(meta["utf8_quarter_proxy"], meta["codec_o200k_base"]) <= FINAL_CAP
                        (destination / "trace.jsonl").write_text(trace.getvalue(), encoding="utf-8")
                        save(destination / "selection.json", receipts)
                        save(destination / "metadata.json", meta)
                        for receipt in receipts:
                            selection = receipt["selection"]
                            summary["model_forward_attempts"] += selection.get("model_forward_attempts", 0)
                            summary["model_forwards"] += selection.get("model_forwards", 0)
                        records[mode] = {"metadata": meta, "receipts": receipts, "payload": payload}
                        ledger("get_docs_context", meta["status"], case_id=case["id"], mode=mode,
                               seconds=meta["elapsed_seconds"], source_count=meta.get("public_source_count"),
                               receipt_count=len(receipts), error=meta.get("error"))
                        if not meta["database_unchanged"] or not meta["project_files_unchanged"]:
                            raise RuntimeError("read-only state invariant failed after a call; stopping before the next arm")
                    paired = pair_receipt(case, records, inventory)
                    after_db, after_files = logical_state(inventory), source_state(root)
                    paired.update(database_unchanged=after_db == original_db, project_files_unchanged=after_files == original_files,
                                  database_sha256_before=original_db["sha256"], database_sha256_after=after_db["sha256"])
                    save(run_dir / "pairs" / (case["id"] + ".json"), paired)
                    summary["pairs"].append(paired)
                    checkpoint()
                    print(json.dumps({"case_id": case["id"], "completed_pairs": len(summary["pairs"]),
                                      "pair_status": paired["status"], "pool_sizes": paired["pool_sizes"],
                                      "mini_status": [r["selection"]["status"] for r in records["prepared_parent_v1"]["receipts"]],
                                      "model_forwards_total": summary["model_forwards"]}), flush=True)
                    if not paired["database_unchanged"] or not paired["project_files_unchanged"]:
                        raise RuntimeError("read-only state invariant failed; no further public calls authorized by this driver")
            home = runtime._FIXTURE_HOMES.pop(state.resolve(), None)
            if home is not None:
                home.cleanup()
        current = {name: sha((REPO / name).read_bytes()) for name in manifest["inputs_sha256"]}
        summary["frozen_inputs_unchanged"] = current == manifest["inputs_sha256"]
        summary["workload_completed"] = summary["context_calls_attempted"] == 80 and len(summary["pairs"]) == 40
        summary["comparable_case_count"] = sum(p["status"] in {"paired", "not_reached_both"} for p in summary["pairs"])
        summary["comparable_selection_case_count"] = sum(p["status"] == "paired" for p in summary["pairs"])
        summary["public_boundary_valid"] = (summary["context_calls_returned"] == 80
            and summary["comparable_case_count"] == 40 and summary["frozen_inputs_unchanged"]
            and all(p["database_unchanged"] and p["project_files_unchanged"] for p in summary["pairs"]))
        summary["status"] = ("completed" if summary["public_boundary_valid"] else "completed_with_integrity_errors") if summary["workload_completed"] else "incomplete"
    except Exception as exc:
        summary.update(status="error", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        ledger("run", "error", error_type=type(exc).__name__, error=str(exc))
    finally:
        summary["finished_at_utc"] = now()
        checkpoint()
    print(json.dumps({key: value for key, value in summary.items() if key != "pairs"}, ensure_ascii=False), flush=True)
    return 0 if summary["status"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
