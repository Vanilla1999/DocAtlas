"""Native literal-operand FTS controls for the existing recovery case.

Observe real SQLite rows returned to the public path. No query text, source
text, backend call result, acceptance threshold or project grant is rewritten.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch

from docmancer.core.sqlite_store import SQLiteStore
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project


def run_fts_literal_controls(require, observed_public_call):
    sources = {
        "manual/literal-operators.md": "FtsLiteralProbe AND OR NOT keeps λ payload.",
        "manual/without-operators.md": "FtsLiteralProbe keeps μ payload.",
        "manual/without-probe.md": "AND OR NOT retains ν payload.",
    }
    target = "manual/literal-operators.md"
    results = []
    with tempfile.TemporaryDirectory(prefix="docatlas-fts-literals-") as temporary:
        root = Path(temporary)
        project = root / "project"
        write_project(project, sources)
        with isolated_service(root / "state") as (service, config):
            prepared = index_project(service, config, project)
            require(prepared["indexed_paths"] == sorted(sources)
                    and not prepared["excluded_or_failed_paths"] and not prepared["unexpected_paths"],
                    "recovery_fts_exact_fixture_members", prepared)
            policy = service.member_storage_policy

            def state():
                return {
                    "generation": policy.generation(),
                    "storage": {item.relative_to(policy.db_path.parent).as_posix():
                                hashlib.sha256(item.read_bytes()).hexdigest()
                                for item in sorted(policy.db_path.parent.rglob("*")) if item.is_file()},
                    "project": {item.relative_to(project).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
                                for item in sorted(project.rglob("*")) if item.is_file()},
                }

            real_search = SQLiteStore._search_rows
            def read(question):
                before = state()
                calls = []
                def observe(store, query, *args, **kwargs):
                    rows = real_search(store, query, *args, **kwargs)
                    if query == question:
                        calls.append({
                            "question": query,
                            "rows": [{
                                "source": row.get("source"), "path": row.get("source_path"),
                                "stable_chunk_id": row.get("stable_chunk_id"),
                                "generation_id": row.get("generation_id"),
                                "mode": row.get("_lexical_query_mode"),
                                "window_sha256": hashlib.sha256(row["display_text"].encode()).hexdigest(),
                            } for row in rows],
                        })
                    return rows
                with patch.object(SQLiteStore, "_search_rows", observe):
                    capture = observed_public_call(service, {
                        "question": question, "project_path": str(project), "scope": "project",
                    })
                require(state() == before, "recovery_fts_read_only", {
                    "question": question, "capture": capture,
                })
                return capture, calls

            warm, warm_calls = read("Explain `FtsLiteralProbe`.")
            payload = warm["public_payload"]
            require(payload.get("status") == "ok" and payload.get("context_available") is True
                    and any(row.get("path_or_url") == target and row.get("snippet") == sources[target]
                            for row in payload.get("sources", []))
                    and all(payload.get(key) is False for key in (
                        "answer_supported", "answer_available", "edit_ready",
                    )), "recovery_fts_healthy_native_context", warm)
            require(warm_calls, "recovery_fts_observer_actual_calls", warm)

            # First the no-primary-hit lane: a primary-only mutant must still
            # pass it, so its intended first failure is the primary control.
            for name, question, expected_modes in (
                ("fallback", "AbsentAnchor FtsLiteralProbe AND OR NOT",
                 {path: "or_fallback" for path in sources}),
                ("primary", "FtsLiteralProbe AND OR NOT",
                 {path: "and" if path == target else "or_union" for path in sources}),
            ):
                capture, calls = read(question)
                payload = capture["public_payload"]
                require(payload.get("error") is None and payload.get("kind") == "docs_context"
                        and payload.get("status") != "failed" and calls,
                        "recovery_fts_literal_" + name, {"capture": capture, "calls": calls})
                for call in calls:
                    rows = call["rows"]
                    require(len(rows) == len(sources)
                            and {row["path"]: row["mode"] for row in rows} == expected_modes,
                            "recovery_fts_literal_" + name, {"capture": capture, "call": call})
                    require(all(
                        row["source"] == str(project / row["path"])
                        and row["generation_id"] == prepared["generation_id"]
                        and isinstance(row["stable_chunk_id"], str) and row["stable_chunk_id"]
                        and row["window_sha256"] == hashlib.sha256(sources[row["path"]].encode()).hexdigest()
                        for row in rows
                    ), "recovery_fts_current_source_rows", call)
                results.append({"id": name, "question": question, "backend_calls": calls})
    return {"public_reads": 3, "controls": results,
            "sources": [{"path": path, "sha256": hashlib.sha256(text.encode()).hexdigest()}
                        for path, text in sorted(sources.items())]}
