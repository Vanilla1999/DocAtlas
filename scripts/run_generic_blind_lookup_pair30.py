#!/usr/bin/env python3
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


def _clean(root: Path) -> dict[str, str]:
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError(f"checkout is not clean: {status[:500]}")
    return {"sha": _git(root, "rev-parse", "HEAD")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    corpus = args.project_root.resolve(strict=True)
    questions = args.questions.resolve(strict=True)
    output = args.output.resolve()
    data = json.loads(questions.read_text(encoding="utf-8"))
    cases = data.get("cases") or []
    if len(cases) != 30 or len({row.get("id") for row in cases}) != 30:
        raise RuntimeError("expected exactly 30 unique questions")
    if not all(row.get("lookup_queries") for row in cases):
        raise RuntimeError("every paired case must provide lookup queries")
    if output == corpus or corpus in output.parents:
        raise RuntimeError("output must be outside frozen corpus")

    runtime = Path.cwd().resolve()
    baseline_corpus = _clean(corpus)
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
        "measurement": "paired_public_capture_only_no_semantic_score",
        "runtime_sha": runtime_sha,
        "runtime_status": _git(runtime, "status", "--porcelain", "--untracked-files=all"),
        "lock_sha256": _sha(lock.read_bytes()),
        "questions_sha256": _sha(questions.read_bytes()),
        "corpus": baseline_corpus,
        "strategies": ["root_only", "root_plus_project_blind_lookups"],
        "cases": [],
    }

    with tempfile.TemporaryDirectory(prefix="docatlas-generic-lookup-pair-") as raw:
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
            row: dict[str, Any] = {"id": case["id"], "question": case["question"], "lookup_queries": case["lookup_queries"]}
            for label, lookups in (("root_only", []), ("with_lookups", case["lookup_queries"])):
                request = {
                    "project_path": str(corpus),
                    "scope": "project",
                    "question": case["question"],
                }
                if lookups:
                    request["lookup_queries"] = lookups
                started = time.perf_counter()
                try:
                    row[label] = {
                        "request": request,
                        "capture": capture_public_call(service, request),
                        "execution_status": "captured",
                    }
                except Exception as exc:
                    row[label] = {
                        "request": request,
                        "execution_status": "error",
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                    }
                row[label]["elapsed_seconds"] = time.perf_counter() - started
                print(f"{case['id']} {label}: {row[label]['execution_status']}", flush=True)
            result["cases"].append(row)

    if _clean(corpus) != baseline_corpus:
        raise RuntimeError("frozen corpus changed during capture")
    errors = sum(
        variant["execution_status"] == "error"
        for row in result["cases"]
        for variant in (row["root_only"], row["with_lookups"])
    )
    result["execution_errors"] = errors
    result["status"] = "captured_with_errors" if errors else "captured_not_evaluated"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
