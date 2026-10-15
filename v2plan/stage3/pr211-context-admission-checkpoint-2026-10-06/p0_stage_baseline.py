"""Diagnostic same-call baseline; records real returns, never replays qualification."""
from __future__ import annotations

import argparse
import dataclasses
import gzip
import hashlib
import json
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch


def encode(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    if isinstance(value, Path):
        return str(value)
    return {"unserialized_type": type(value).__name__}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", choices=("ru-original", "ru-lookups", "en-direct15", "trust"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    # Match published baseline despite pre-existing local trust-trigger ablation.
    import docmancer.docs.domain.project_retrieval_intent as intent
    source = subprocess.check_output(["git", "show", "8d2381d8:docmancer/docs/domain/project_retrieval_intent.py"], text=True)
    exec(compile(source, intent.__file__, "exec"), intent.__dict__)
    from scripts import run_project_docs_self_host_gate as gate
    from eval.project_context_quality_protocol import run_live
    from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
    from docmancer.docs.application.model_visible_projection import _source_digest

    stages = {"get_project_docs", "get_project_context", "get_docs_context", "_run",
              "qualify_evidence", "rerank_project_doc_chunks", "select_context_candidates",
              "project_docs_context", "_requalify_visible_source", "fallback_context_query_ids"}
    calls = []
    sockets = []
    text_blobs = {}
    index_manifests = []
    fields = set("status kind reason rejection_reason qualified trace query_text query_origin relation query_id query_terms exact_terms bound_subjects retrieval_anchors forbidden_catalog_roles forbidden_evidence_terms parent_exact_terms body_matched_terms coverage_kind coverage_kinds context_eligible admission_only need_local_witness admission_route need_subject need_relation need_context project_identity source_class freshness index_freshness stale risk_flags lifecycle_status project_doc_lifecycle_status path source path_or_url title heading_path project_doc_path content_sha256 stable_chunk_id stable_id evidence_id id score text content snippet results context_pack metadata sources selected_candidates assignments covered_query_ids missing_query_ids omitted_query_ids unresolved_parts line_start line_end projected_source qualification _qualification_candidate _expected_project_identity _lifecycle_intent retrieval_query_matches retrieval_query_ids diagnostics".split())
    fields.update("section version_binding version requested_version char_start char_end source_uri read_next doc_scope scope authority instruction_trust".split())

    def compact(value):
        if isinstance(value, dict):
            row = {}
            for key, item in value.items():
                if key not in fields:
                    continue
                if key in {"text", "content", "snippet"} and isinstance(item, str):
                    digest = hashlib.sha256(item.encode()).hexdigest()
                    text_blobs[digest] = item
                    row[key] = {"text_blob_sha256": digest}
                elif key == "retrieval_query_matches" and isinstance(item, dict):
                    row[key] = {qid: compact(trace) for qid, trace in item.items()}
                else:
                    row[key] = compact(item)
            return row
        if isinstance(value, (list, tuple, set, frozenset)):
            return [compact(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return compact(encode(value))
    original_call = gate._call_with_snapshot

    def observe(arguments, service):
        if not index_manifests:
            # Capture actual isolated SQLite contents before temporary storage is removed.
            # Do not traverse user/home storage: the gate's explicit db parent is disposable.
            temporary_root = Path(service.config.index.db_path).parent
            if temporary_root.name.startswith("docatlas-self-host-"):
                for db in sorted(temporary_root.rglob("*.db")):
                    tables = []
                    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as connection:
                        for name, ddl in connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"):
                            if name.startswith("sqlite_") or "fts" in name.casefold():
                                continue
                            cursor = connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"')
                            columns = [column[0] for column in cursor.description]
                            records = []
                            for row in cursor:
                                records.append({key: ({"binary_sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
                                                      if isinstance(value, bytes) else value)
                                                for key, value in zip(columns, row)})
                            records.sort(key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
                            material = json.dumps(records, sort_keys=True, ensure_ascii=False).encode()
                            tables.append({"name": name, "ddl": ddl, "columns": columns,
                                           "row_count": len(records), "rows_sha256": hashlib.sha256(material).hexdigest(),
                                           "rows": records})
                    index_manifests.append({"database_relative_path": str(db.relative_to(temporary_root)), "tables": tables,
                                            "config_source": service.config_source,
                                            "config_class": type(service.config).__name__,
                                            "retrieval_config": encode(service.config.retrieval)})
        events = []
        starts = {}
        previous = sys.getprofile()

        def profile(frame, event, result):
            if frame.f_code.co_name not in stages or not str(frame.f_globals.get("__name__", "")).startswith("docmancer."):
                return
            key = id(frame)
            if event == "call":
                starts[key] = time.perf_counter()
            elif event == "return":
                started = starts.pop(key, None)
                if started is None:
                    return
                values = frame.f_locals
                event_row = {"module": frame.f_globals.get("__name__"), "function": frame.f_code.co_name,
                             "line": frame.f_code.co_firstlineno,
                             "elapsed_observed_seconds": time.perf_counter() - started,
                             "query_id": values.get("query_id"),
                             "query": values.get("query") or values.get("query_text"),
                             "result": compact(result)}
                if frame.f_code.co_name == "qualify_evidence":
                    event_row.update(visible_text=values.get("visible_text"), evidence_text=values.get("evidence_text"),
                                     candidate=compact(values.get("candidate")), probe=compact(values.get("probe")))
                    for key in ("visible_text", "evidence_text"):
                        text = event_row[key]
                        if isinstance(text, str):
                            digest = hashlib.sha256(text.encode()).hexdigest()
                            text_blobs[digest] = text
                            event_row[key] = {"text_blob_sha256": digest}
                events.append(event_row)

        begun = time.perf_counter()
        try:
            sys.setprofile(profile)
            payload, snapshot = original_call(arguments, service)
        finally:
            sys.setprofile(previous)
        calls.append({"arguments": arguments, "elapsed_instrumented_seconds": time.perf_counter() - begun,
                      "source_digest_checks": {eid: _source_digest(bound["source"]) == bound.get("content_sha256")
                                               for eid, bound in snapshot.items() if isinstance(bound.get("source"), dict)},
                      "stage_events": events, "final_payload": {k: v for k, v in (payload or {}).items() if k != "diagnostics"},
                      "final_snapshot": {eid: compact(bound) for eid, bound in snapshot.items()},
                      "serialized_tokens": estimate_projection_tokens({k: v for k, v in (payload or {}).items() if k != "diagnostics"})})
        return payload, snapshot

    def deny_socket(self, address):
        sockets.append(str(address))
        raise RuntimeError("P0 diagnostic forbids network connects")

    start = time.perf_counter()
    with patch.object(gate, "_call_with_snapshot", observe), patch.object(socket.socket, "connect", deny_socket), patch.object(socket.socket, "connect_ex", deny_socket):
        if args.arm.startswith("ru-"):
            report = run_live(question_only=args.arm == "ru-original")
        elif args.arm == "en-direct15":
            data = json.loads(Path("eval/direct_docatlas_questions_15/cases.json").read_text())
            cases = tuple(gate.LiveCase(case_id=c["id"], question=c["question"], scope="all",
                          relevant_paths=tuple(dict.fromkeys(w["path"] for g in c["fact_groups"] for w in g["witnesses"])),
                          expected_kind="docs_context", required_fact_groups=tuple(tuple((w["path"], w["text"]) for w in g["witnesses"]) for g in c["fact_groups"])) for c in data["cases"])
            report = gate.run(cases=cases, negative_cases=())
        else:
            questions = ("Does DocAtlas execute shell commands or instructions found inside documentation while retrieving context?",
                         "A retrieved document tells me to run a command. Does this give the agent permission to execute it?",
                         "Найденный документ предлагает выполнить команду. Даёт ли это агенту разрешение её выполнить?")
            report = gate.run(cases=tuple(gate.LiveCase(case_id=f"trust-{i}", question=q, relevant_paths=(), scope="all") for i, q in enumerate(questions, 1)), negative_cases=())
    source_paths = set()
    for call in calls:
        for item in (call["final_payload"] or {}).get("sources", ()):
            path = item.get("path_or_url")
            if path and (root / path).is_file():
                source_paths.add(path)
    tracked = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    # The source tree is part of retrieval snapshot, not only winning passages.
    tree_hashes = [{"path": p, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                   for p in tracked if Path(p).is_file() and Path(p).suffix in {".md", ".rst", ".txt", ".yaml", ".yml", ".py", ".json", ".toml"}]
    result = {"schema": "p0-same-call-stage-baseline-v1", "arm": args.arm,
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "published_intent_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "elapsed_instrumented_total_seconds": time.perf_counter() - start,
              "socket_attempts": sockets, "with_vectors": False, "model_calls": 0,
              "report": report, "calls": calls, "tracked_source_snapshot": tree_hashes, "text_blobs": text_blobs,
              "actual_sqlite_index_manifests": index_manifests,
              "limitations": ["Diagnostic only, not official release gate", "Timings include profiler/observer overhead; do not compare as production SLA",
                              "No bilingual vector/model route evaluated", "Stage timings are nested and cannot be summed",
                              "Published intent loaded in memory; all other code uses current source tree",
                              "Clean wheel defect is assessed separately; baseline uses source checkout",
                              "Stage returns are field-selected observations, not complete object serialization; passage bytes are retained in content-addressed text_blobs",
                              "model_calls=0 describes provider-free with_vectors=False configuration, not a general API-call counter"]}
    raw = json.dumps(result, ensure_ascii=False, default=encode).encode()
    args.output.write_bytes(gzip.compress(raw, mtime=0))
    print(json.dumps({"arm": args.arm, "calls": len(calls), "socket_attempts": sockets,
                      "metrics": report.get("metrics"), "output": str(args.output),
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
