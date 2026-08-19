#!/usr/bin/env python3
"""Provider-free self-hosting gate for the Project Docs answer pipeline.

The gate indexes this repository into an isolated temporary SQLite store and then
runs canonical Project Docs questions through the public ``get_docs_context``
MCP handler. It proves the complete chain is closed:

question -> answer contract -> retrieval -> local proof -> selection -> projection.

The corpus intentionally covers the stable QuestionPlan families plus two
premise/condition cases that depend on the clear-index source of truth.
"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService


REPO_ROOT = Path(__file__).resolve().parents[1]

# question, allowed supporting source paths. Empty means status/source-backed
# closure is mandatory but the exact source identity is intentionally flexible.
GOLD_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Which source types are supported for indexing?", ("docs/modules/question-planning.md", "wiki/Supported-Sources.md")),
    ("Which command syncs project docs after file changes?", ("README.md", "docs/capabilities.md")),
    ("Which command starts the Docs MCP server?", ("README.md", "docs/project-docs-demo.md")),
    ("How do I run the offline test suite for DocAtlas?", ("docs/testing.md",)),
    ("How do I run the project answer quality v4 protocol?", ("eval/project_answer_quality_v4/README.md",)),
    ("How does the two-cell smoke procedure verify provider-call cardinality?", ("eval/task_level/README.md",)),
    ("Which docs files must stay under the 1000-line release limit?", ("docs/RELEASE_CHECKLIST.md",)),
    ("What is the storage mutation coordination contract for cleanup and refresh?", ("docs/index-cleanup.md", "docs/modules/storage-mutation-coordination.md")),
    ("What happens if remove_library_docs runs while a library refresh is in flight?", ("docs/index-cleanup.md", "docs/modules/storage-mutation-coordination.md")),
    ("What is the release checklist and what gates block release?", ("docs/RELEASE_CHECKLIST.md",)),
    ("What is the model-visible projection and how is the answer token-bounded?", ("docs/mcp-docs-server.md",)),
    ("What does clear-index do when a live process holds the index?", ("docs/index-cleanup.md",)),
    ("How do I configure a project in docmancer.yaml?", ("wiki/Configuration.md",)),
    ("How does evidence selection choose which candidates are selected?", ("docs/mcp-docs-server.md", "docs/modules/evidence-selection.md")),
    ("What is contamination protection in the eval protocols?", ("eval/project_answer_quality_v4/README.md",)),
    ("What is the two-cell smoke procedure for local Task 33 benchmarks?", ("eval/task_level/README.md",)),
    ("What does the two-cell smoke procedure require?", ("eval/task_level/README.md",)),
    ("How do I sync project docs after changing a file?", ("README.md", "docs/capabilities.md", "docs/modules/README.md")),
    ("How does indexing split documents into sections and chunks?", ("wiki/Architecture.md",)),
    ("What are the three public Docs MCP tools and when do I use each one?", ("docs/mcp-docs-server.md",)),
    ("How does evidence selection differ from question planning?", ("docs/modules/question-planning.md", "docs/modules/evidence-selection.md")),
    ("Where is the project answer contract documented?", ()),
    ("What happens when the preview plan is stale?", ("docs/index-cleanup.md",)),
    ("Why does clear-index always delete remote Qdrant collections?", ("docs/index-cleanup.md",)),
)


def _source_paths(payload: dict[str, object]) -> tuple[str, ...]:
    rows = payload.get("sources") or ()
    if not isinstance(rows, list):
        return ()
    result: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            value = str(row.get("path_or_url") or "").strip()
            if value:
                result.append(value)
    return tuple(result)


def main() -> int:
    previous_home = os.environ.get("DOCMANCER_HOME")
    errors: list[str] = []
    try:
        with TemporaryDirectory(prefix="docatlas-self-host-") as raw_tmp:
            tmp = Path(raw_tmp)
            os.environ["DOCMANCER_HOME"] = str(tmp / "home")
            config = DocmancerConfig()
            config.index.db_path = str(tmp / "docmancer.db")
            config.index.extracted_dir = str(tmp / "extracted")
            service = LibraryDocsService(
                config=config,
                registry=LibraryRegistry(config.index.db_path),
                agent=DocmancerAgent(config=config),
                job_tracker=DocsJobTracker(),
            )

            sync = service.sync_project_docs(str(REPO_ROOT), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                print(f"FAIL: self-host sync status={getattr(sync, 'status', None)!r}")
                return 1

            for index, (question, allowed_paths) in enumerate(GOLD_CASES, 1):
                payload = handle_context_tool(
                    "get_docs_context",
                    {
                        "question": question,
                        "project_path": str(REPO_ROOT),
                        "mode": "project",
                        "delivery_strategy": "bounded_direct",
                        "prepare_project_docs": False,
                    },
                    service,
                )
                if payload is None:
                    errors.append(f"{index:02d}: no payload: {question}")
                    continue
                status = str(payload.get("status") or "")
                paths = _source_paths(payload)
                if status != "ok":
                    errors.append(
                        f"{index:02d}: status={status!r} missing={payload.get('missing')!r}: {question}"
                    )
                    continue
                if not paths:
                    errors.append(f"{index:02d}: ok without source-backed evidence: {question}")
                    continue
                if allowed_paths and not any(path in allowed_paths for path in paths):
                    errors.append(
                        f"{index:02d}: wrong source paths={paths!r}, expected one of {allowed_paths!r}: {question}"
                    )
    finally:
        if previous_home is None:
            os.environ.pop("DOCMANCER_HOME", None)
        else:
            os.environ["DOCMANCER_HOME"] = previous_home

    if errors:
        print("FAIL: Project Docs self-hosting closure")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"PASS: {len(GOLD_CASES)} canonical Project Docs questions close "
        "retrieval -> proof -> selection -> projection with source-backed evidence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
