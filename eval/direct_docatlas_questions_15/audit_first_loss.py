"""Trace direct-question fact loss without changing the project under test."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

CODE_ROOT = Path(os.environ.get("DOCATLAS_CODE_ROOT") or Path(__file__).resolve().parents[2]).resolve()
sys.path.insert(0, str(CODE_ROOT))

import scripts.run_project_docs_self_host_gate as self_host_gate
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _contains(text: str, fragment: str) -> bool:
    return fragment.casefold() in text.casefold()


def _fact_in_rows(rows: list[dict], witnesses: list[dict]) -> bool:
    for row in rows:
        path = str(row.get("source_path") or row.get("path_or_url") or "")
        text = str(row.get("display_text") or row.get("snippet") or "")
        if any(path == witness["path"] and _contains(text, witness["text"]) for witness in witnesses):
            return True
    return False


def _first_loss(stages: dict[str, bool]) -> str:
    order = (
        ("source_truth", "document_gap"),
        ("indexed", "chunking_or_indexing"),
        ("retrieved", "retrieval"),
        ("qualified", "qualification"),
        ("ranked", "ranking"),
        ("selected", "selection"),
        ("visible", "projection"),
    )
    for key, label in order:
        if not stages[key]:
            return label
    return "visible"


def audit(project_root: Path, corpus_path: Path, output_path: Path) -> dict:
    project_root = project_root.resolve()
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    try:
        head = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        head = "unavailable"

    source_cache: dict[str, str] = {}
    source_hashes: dict[str, str | None] = {}
    for case in corpus["cases"]:
        for group in case["fact_groups"]:
            for witness in group["witnesses"]:
                rel = witness["path"]
                if rel in source_cache:
                    continue
                path = project_root / rel
                source_cache[rel] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
                source_hashes[rel] = _git_blob_sha(path) if path.is_file() else None

    previous_home = os.environ.get("DOCATLAS_HOME")
    report: dict = {
        "schema_version": "direct-docatlas-first-loss-v1",
        "project_head": head,
        "corpus": str(corpus_path),
        "request_contract": corpus["request_contract"],
        "results": [],
    }
    try:
        with TemporaryDirectory(prefix="docatlas-first-loss-") as raw_tmp:
            tmp = Path(raw_tmp)
            os.environ["DOCATLAS_HOME"] = str(tmp / "home")
            config = self_host_gate.DocmancerConfig()
            config.index.db_path = str(tmp / "docmancer.db")
            config.index.extracted_dir = str(tmp / "extracted")
            service = self_host_gate.LibraryDocsService(
                config=config,
                config_source="explicit",
                registry=self_host_gate.LibraryRegistry(config.index.db_path),
                agent=self_host_gate.DocmancerAgent(config=config),
                job_tracker=self_host_gate.DocsJobTracker(),
            )
            sync = service.sync_project_docs(str(project_root), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                raise RuntimeError(f"sync failed: {sync!r}")

            connection = sqlite3.connect(config.index.db_path)
            connection.row_factory = sqlite3.Row
            index_rows = [dict(row) for row in connection.execute(
                "SELECT stable_chunk_id, source_path, display_text, line_start, line_end "
                "FROM retrieval_children"
            ).fetchall()]
            by_id = {str(row["stable_chunk_id"]): row for row in index_rows}

            for case in corpus["cases"]:
                question = case["question"]
                payload, _snapshot = self_host_gate._call_with_snapshot(
                    {"question": question, "project_path": str(project_root), "scope": "all"},
                    service,
                )
                payload = dict(payload or {})
                diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
                raw_ids = [str(value) for value in diagnostics.get("retrieved_candidate_ids") or ()]
                qualified_ids = [str(value) for value in diagnostics.get("pre_projection_qualified_ids") or ()]
                ranked_ids = [str(value) for value in diagnostics.get("ranked_candidate_ids") or ()]
                selected_ids = [str(value) for value in diagnostics.get("selected_candidate_ids") or ()]
                public_sources = [row for row in payload.get("sources") or () if isinstance(row, dict)]

                def rows_for(ids: list[str]) -> list[dict]:
                    return [by_id[value] for value in ids if value in by_id]

                fact_rows = []
                for group in case["fact_groups"]:
                    available = [
                        witness for witness in group["witnesses"]
                        if witness["path"] in source_cache
                        and _contains(source_cache[witness["path"]], witness["text"])
                    ]
                    stages = {
                        "source_truth": bool(available),
                        "indexed": _fact_in_rows(index_rows, available) if available else False,
                        "retrieved": _fact_in_rows(rows_for(raw_ids), available) if available else False,
                        "qualified": _fact_in_rows(rows_for(qualified_ids), available) if available else False,
                        "ranked": _fact_in_rows(rows_for(ranked_ids), available) if available else False,
                        "selected": _fact_in_rows(rows_for(selected_ids), available) if available else False,
                        "visible": _fact_in_rows(public_sources, available) if available else False,
                    }
                    fact_rows.append({
                        "id": group["id"],
                        "source_truth_witnesses": available,
                        "stages": stages,
                        "first_loss": _first_loss(stages),
                    })

                aliases = build_project_retrieval_aliases(question)
                report["results"].append({
                    "id": case["id"],
                    "question": question,
                    "request": {"question": question, "project_path": str(project_root), "scope": "all"},
                    "query_intent": classify_project_query_intent(question).name,
                    "retrieval_aliases": [
                        {"intent_id": row.intent_id, "text": row.text} for row in aliases
                    ],
                    "status": payload.get("status"),
                    "kind": payload.get("kind"),
                    "estimated_tokens": payload.get("estimated_tokens"),
                    "sources": [
                        {
                            "path": source.get("path_or_url"),
                            "snippet": source.get("snippet"),
                            "line_start": source.get("line_start"),
                            "line_end": source.get("line_end"),
                        }
                        for source in public_sources
                    ],
                    "facts": fact_rows,
                    "visible_fact_count": sum(row["stages"]["visible"] for row in fact_rows),
                    "source_truth_fact_count": sum(row["stages"]["source_truth"] for row in fact_rows),
                    "diagnostic_stage_status": diagnostics.get("stage_status"),
                    "observer_counts": diagnostics.get("observer_counts"),
                })
            connection.close()
    finally:
        if previous_home is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous_home

    report["summary"] = {
        "questions": len(report["results"]),
        "good": sum(
            row["visible_fact_count"] == len(row["facts"])
            for row in report["results"]
        ),
        "source_truth_complete": sum(
            row["source_truth_fact_count"] == len(row["facts"])
            for row in report["results"]
        ),
        "first_loss_counts": {},
        "source_hashes": source_hashes,
    }
    for row in report["results"]:
        for fact in row["facts"]:
            label = fact["first_loss"]
            report["summary"]["first_loss_counts"][label] = report["summary"]["first_loss_counts"].get(label, 0) + 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.project_root, args.corpus, args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    for row in report["results"]:
        missing = [fact["id"] + ":" + fact["first_loss"] for fact in row["facts"] if not fact["stages"]["visible"]]
        print(f"{row['id']}: {row['visible_fact_count']}/{len(row['facts'])} visible; " + (", ".join(missing) if missing else "GOOD"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
