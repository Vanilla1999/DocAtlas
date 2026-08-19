#!/usr/bin/env python3
"""Provider-free self-hosting gate through the public Docs MCP routing path.

This intentionally syncs and queries through ``call_docs_tool_payload``. A
split harness that calls ``LibraryDocsService.sync_project_docs`` directly and
then enters the MCP boundary can populate a fallback index while the public
request correctly resolves a different project-local topology; that setup
measures the harness, not the product path.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


CASES = (
    (
        "How does evidence selection choose which candidates are selected?",
        ("evidence selection", "mandatory"),
    ),
    (
        "What is the storage mutation coordination contract for cleanup and refresh?",
        ("writer lease", "cleanup barrier"),
    ),
    (
        "How do I run the project answer quality v4 protocol?",
        ("project_answer_quality_v4_protocol.py", "--output"),
    ),
)
NEGATIVE_CONTROL = "What is the xyzzy self-hosting coordination contract?"


def _copy_repository(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", ".docmancer", ".pytest_cache", "__pycache__", "*.pyc",
            ".venv", "venv", "build", "dist",
        ),
    )


def _base_service(work: Path) -> LibraryDocsService:
    config = DocmancerConfig()
    config.index.db_path = str(work / "fallback.db")
    config.index.extracted_dir = str(work / "fallback-extracted")
    return LibraryDocsService(
        config=config,
        config_source="defaults",
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)


def main() -> int:
    source_root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="docatlas-self-host-gate-") as tmp_raw:
        work = Path(tmp_raw)
        project = work / "repo"
        _copy_repository(source_root, project)
        service = _base_service(work)

        sync = call_docs_tool_payload(
            "prepare_docs",
            {
                "action": "sync_project_docs",
                "project_path": str(project),
                "with_vectors": False,
            },
            service,
        )
        if sync.get("status") != "success":
            errors.append(
                "public prepare_docs sync failed: "
                f"status={sync.get('status')!r} reason={sync.get('reason_code')!r}"
            )
        project_db = project / ".docmancer" / "docmancer.db"
        if not project_db.exists():
            errors.append("public sync did not populate the project-local index topology")

        for question, required_terms in CASES:
            payload = call_docs_tool_payload(
                "get_docs_context",
                {
                    "question": question,
                    "project_path": str(project),
                    "mode": "project",
                    "delivery_strategy": "bounded_direct",
                    "packet_tokens": 800,
                },
                service,
            )
            if payload.get("status") != "ok" or payload.get("answer_supported") is not True:
                errors.append(
                    f"self-hosting public query failed: {question!r}; "
                    f"status={payload.get('status')!r} reason={payload.get('reason_code')!r} "
                    f"missing={payload.get('missing')!r}"
                )
                continue
            visible = "\n".join(
                [str(payload.get("answer") or "")]
                + [str(source.get("snippet") or "") for source in payload.get("sources") or []]
            ).casefold()
            missing_terms = [term for term in required_terms if term.casefold() not in visible]
            if missing_terms:
                errors.append(
                    f"self-hosting answer lost required visible semantics for {question!r}: "
                    f"{missing_terms!r}"
                )
            if not payload.get("sources"):
                errors.append(f"self-hosting answer has no cited source: {question!r}")

        negative = call_docs_tool_payload(
            "get_docs_context",
            {
                "question": NEGATIVE_CONTROL,
                "project_path": str(project),
                "mode": "project",
                "delivery_strategy": "bounded_direct",
                "packet_tokens": 800,
            },
            service,
        )
        if negative.get("status") == "ok" or negative.get("answer_supported") is True:
            errors.append("negative self-hosting control was incorrectly authorized")

    if errors:
        for error in errors:
            _fail(error)
        return 1
    print(
        "PASS: public prepare_docs -> get_docs_context self-hosting route closes "
        "3 canonical questions at 800 tokens; negative control remains fail-closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
