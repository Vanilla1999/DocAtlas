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


@pytest.mark.parametrize("new_available", [False, True])
def test_lockfile_transition_never_reuses_old_snapshot(tmp_path, monkeypatch, new_available):
    monkeypatch.setenv("DOCATLAS_OFFLINE", "1")
    monkeypatch.setenv("DOCATLAS_AUTO_VECTORS", "0")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    project = _project(tmp_path / "project", "1.0.0")
    old = _seed(service, "1.0.0", "ALPHA")
    if new_available:
        _seed(service, "2.0.0", "BETA")
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    before = service.get_docs(PACKAGE, project_path=str(project), topic=QUESTION)
    assert before.resolved_version == "1.0.0"
    assert before.results and "ALPHA" in before.results[0].content
    _read(service, project)  # warm the public/application path using the same instance

    _lock(project, "2.0.0")
    after = _read(service, project)
    assert "ALPHA" not in _sources(after)
    assert "/1.0.0/" not in _sources(after)
    assert service.registry.get(old.library_id) is not None
    assert Path(service._index_config_for(old).index.db_path).exists()
    if new_available:
        current = service.get_docs(PACKAGE, project_path=str(project), topic=QUESTION)
        assert current.resolved_version == "2.0.0"
        assert current.results and all("BETA" in row.content for row in current.results)
    else:
        assert after["status"] == "insufficient_evidence"
        assert after["recommended_next_action"]["tool"] == "prepare_docs"


def test_shared_cache_rollback_and_explicit_historical_read(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_OFFLINE", "1")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    p1 = _project(tmp_path / "one", "1.0.0")
    p2 = _project(tmp_path / "two", "2.0.0")
    _seed(service, "1.0.0", "ALPHA")
    _seed(service, "2.0.0", "BETA")
    for project, version, marker in [(p1,"1.0.0","ALPHA"),(p2,"2.0.0","BETA")]:
        result = service.get_docs(PACKAGE, project_path=str(project), topic=QUESTION)
        assert result.resolved_version == version
        assert result.results and marker in result.results[0].content
    _lock(p1, "2.0.0")
    assert service.get_docs(PACKAGE, project_path=str(p1), topic=QUESTION).resolved_version == "2.0.0"
    _lock(p1, "1.0.0")
    assert service.get_docs(PACKAGE, project_path=str(p1), topic=QUESTION).resolved_version == "1.0.0"
    historical = call_docs_tool_payload("get_docs_context", {
        "question": QUESTION, "library": PACKAGE, "version": "1.0.0",
    }, service)
    assert "ALPHA" in _sources(historical)
    assert "BETA" not in _sources(historical)


def test_public_mixed_transition_has_nonempty_current_version_evidence(tmp_path, monkeypatch):
    """Positive control: rejecting every source is not version-correct delivery."""
    monkeypatch.setenv("DOCATLAS_OFFLINE", "1")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    project = _project(tmp_path / "project", "1.0.0")
    _seed(service, "1.0.0", "ALPHA")
    _seed(service, "2.0.0", "BETA")
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    for version, marker, forbidden in [("1.0.0","ALPHA","BETA"),("2.0.0","BETA","ALPHA")]:
        _lock(project, version)
        result = _read(service, project)
        assert marker in _sources(result), result
        assert forbidden not in _sources(result)
        assert result["estimated_tokens"] <= 800
