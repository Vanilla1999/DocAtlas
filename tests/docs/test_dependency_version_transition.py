"""Stateful version isolation through real storage, selection and the public handler.

The documentation below is synthetic, not a claim about an external package.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.mcp.docs_server import call_docs_tool_payload
from tests._shared_test_docs_service import _service_with_real_agent

PACKAGE = "nav_kit"
QUESTION = "What is NavigationRegistry?"


def _project(root: Path, version: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pubspec.yaml").write_text(
        f"name: example\ndependencies:\n  {PACKAGE}: any\n", encoding="utf-8"
    )
    (root / "README.md").write_text(
        "# NavigationRegistry\n\nNavigationRegistry is the route registry interface used by this project.\n",
        encoding="utf-8",
    )
    _lock(root, version)
    return root


def _lock(root: Path, version: str) -> None:
    (root / "pubspec.lock").write_text(
        f"packages:\n  {PACKAGE}:\n    dependency: direct main\n"
        f"    description: {{name: {PACKAGE}, url: https://pub.dev}}\n"
        f"    source: hosted\n    version: '{version}'\n", encoding="utf-8"
    )


def _seed(service, version: str, marker: str):
    record = service.registry.upsert(
        library=PACKAGE, ecosystem="pub", version=version, source_type="api",
        docs_url=f"https://pub.dev/documentation/{PACKAGE}/{version}/",
        now=service._now(), status="available", last_refreshed_at=service._now(),
        docs_snapshot_exact=True,
    )
    config = service._index_config_for(record)
    SQLiteStore(config.index.db_path, config.index.extracted_dir).add_documents([
        Document(
            source=record.docs_url + "nav_kit/NavigationRegistry-class.html",
            content=("# NavigationRegistry\n\nNavigationRegistry is a route registry "
                     f"using {marker} dispatch in version {version}.\n"),
            metadata={
                "library_id": record.library_id, "canonical_id": record.canonical_id,
                "resolved_version": version, "docs_snapshot_exact": True,
                "source_type": "api", "title": "NavigationRegistry",
            },
        ),
    ])
    return record


def _read(service, project: Path):
    return call_docs_tool_payload("get_docs_context", {
        "question": QUESTION, "library": PACKAGE, "project_path": str(project),
    }, service)


def _sources(payload):
    return json.dumps(payload.get("sources", []), ensure_ascii=False)


