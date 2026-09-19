#!/usr/bin/env python3
"""Capture the frozen V13/V15 development set through the real public boundary.

This records evidence only. It does not assign semantic sufficiency scores and it
never supplies lookup_queries from the expected answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean_corpus(root: Path) -> dict[str, str]:
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError(f"corpus checkout is not clean: {status[:500]}")
    return {"sha": _git(root, "rev-parse", "HEAD")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    corpus = args.project_root.resolve(strict=True)
    questions = args.questions.resolve(strict=True)
    output = args.output.resolve()
    data = json.loads(questions.read_text(encoding="utf-8"))
    cases = data.get("cases") or []
    if len(cases) != 30 or len({row.get("id") for row in cases}) != 30:
        raise RuntimeError("expected exactly 30 unique diagnostic questions")
    if any(row.get("lookup_queries") for row in cases):
        raise RuntimeError("root-only capture refuses supplied lookup queries")
    if output == corpus or corpus in output.parents:
        raise RuntimeError("output must be outside the frozen corpus")

    runtime = Path.cwd().resolve()
    baseline_corpus = _clean_corpus(corpus)
    runtime_sha = _git(runtime, "rev-parse", "HEAD")
    lock = runtime / "uv.lock"

    os.environ["DOCATLAS_OFFLINE"] = "1"
    os.environ["DOCATLAS_AUTO_VECTORS"] = "0"

    from docmancer.agent import DocmancerAgent
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.registry import LibraryRegistry
    from docmancer.docs.service import DocsJobTracker, LibraryDocsService
    from eval.project_context_quality.capture_public_context import capture_public_call

    result: dict[str, Any] = {
        "schema_version": 1,
        "measurement": "public_capture_only_no_semantic_score",
        "runtime_sha": runtime_sha,
        "runtime_status": _git(runtime, "status", "--porcelain", "--untracked-files=all"),
        "lock_sha256": _sha(lock.read_bytes()),
        "questions_sha256": _sha(questions.read_bytes()),
        "corpus": baseline_corpus,
        "strategy": "original_root_only",
        "cases": [],
    }

    with tempfile.TemporaryDirectory(prefix="docatlas-v13-v15-") as raw:
        tmp = Path(raw)
        os.environ["DOCATLAS_HOME"] = str(tmp / "home")
        cfg = DocmancerConfig()
        cfg.index.db_path = str(tmp / "docs.sqlite")
        cfg.index.extracted_dir = str(tmp / "extracted")
        service = LibraryDocsService(
            config=cfg,
            config_source="explicit",
            registry=LibraryRegistry(cfg.index.db_path),
            agent=DocmancerAgent(config=cfg),
            job_tracker=DocsJobTracker(),
        )
        sync = service.sync_project_docs(str(corpus), with_vectors=False)
        if sync.status != "success":
            raise RuntimeError(f"project sync failed: {sync.status}")

        for case in cases:
            request = {
                "project_path": str(corpus),
                "scope": "project",
                "question": case["question"],
            }
            started = time.perf_counter()
            row: dict[str, Any] = {
                "id": case["id"],
                "legacy_id": case.get("legacy_id"),
                "request": request,
                "semantic_assessment": "not_assessed",
            }
            try:
                row["capture"] = capture_public_call(service, request)
                row["execution_status"] = "captured"
            except Exception as exc:
                row["execution_status"] = "error"
                row["error"] = {"type": type(exc).__name__, "message": str(exc)}
            row["elapsed_seconds"] = time.perf_counter() - started
            result["cases"].append(row)
            print(f"{case['id']}: {row['execution_status']}", flush=True)

    final_corpus = _clean_corpus(corpus)
    if final_corpus != baseline_corpus:
        raise RuntimeError("frozen corpus changed during capture")
    errors = sum(row["execution_status"] == "error" for row in result["cases"])
    result["execution_errors"] = errors
    result["status"] = "captured_with_errors" if errors else "captured_not_evaluated"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
