"""Public MCP lifecycle against a real isolated SQLite store, without vectors."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from tests._shared_test_docs_service import _flutter_project, _service_with_real_agent
from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface, call_docs_tool_payload
from docmancer.mcp._docs_server_part01 import _service_for_project_path


def _call(service, project, **delta):
    return call_docs_tool_payload(
        "prepare_docs",
        {"action": "sync_project_docs", "project_path": str(project), "with_vectors": False, **delta},
        service, surface=build_docs_surface(DocsServerConfig()),
    )


def _snapshot(service):
    with service._agent_instance().store._connect() as conn:
        return {
            table: sorted((tuple(row) for row in conn.execute(f"SELECT * FROM {table}")), key=repr)
            for table in ("sources", "sections")
        }


def _inventory(service, project):
    return {row["path"]: row["source"] for row in service._indexed_project_doc_sources(str(project))}


@pytest.fixture
def project_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_OFFLINE", "1")
    monkeypatch.setenv("DOCATLAS_AUTO_VECTORS", "0")
    project = _flutter_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    for name, needle in (("a", "AlphaBeforeNeedle"), ("b", "BetaBeforeNeedle"), ("keep", "UntouchedKeepNeedle")):
        (docs / f"{name}.md").write_text(f"# {name}\n\n{needle}.\n", encoding="utf-8")
    for args in (("init", "-q"), ("config", "user.name", "DocAtlas Test"),
                 ("config", "user.email", "docatlas-test@example.invalid"),
                 ("add", "."), ("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")):
        subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True)
    service = _service_with_real_agent(tmp_path, monkeypatch)
    result = _call(service, project)
    assert result["status"] == "success", result
    active = _service_for_project_path(service, {"project_path": str(project)})
    assert set(_inventory(active, project)) >= {"docs/a.md", "docs/b.md", "docs/keep.md"}
    return project, service, active


@pytest.mark.parametrize("operation", ["add", "change", "delete", "rename"])
def test_public_delta_changes_real_index_only_where_requested(project_state, operation):
    project, service, active = project_state
    store = active._agent_instance().store
    before = _inventory(active, project)
    keep_ids = store.section_ids_for_source(before["docs/keep.md"])
    assert keep_ids
    if operation == "add":
        (project / "docs/new.md").write_text("# Added\n\nAddedDeltaNeedle.\n", encoding="utf-8")
        delta = {"changed_paths": ["docs/new.md"]}
    elif operation == "change":
        (project / "docs/a.md").write_text("# Updated\n\nAlphaAfterNeedle.\n", encoding="utf-8")
        delta = {"changed_paths": ["docs/a.md"]}
    elif operation == "delete":
        (project / "docs/b.md").unlink()
        delta = {"deleted_paths": ["docs/b.md"]}
    else:
        (project / "docs/a.md").rename(project / "docs/renamed.md")
        delta = {"renamed_paths": [{"old_path": "docs/a.md", "new_path": "docs/renamed.md"}]}

    result = _call(service, project, **delta)
    assert result["status"] == "success", result
    after = _inventory(active, project)
    contents = json.dumps(_snapshot(active), ensure_ascii=False, default=str)
    assert after["docs/keep.md"] == before["docs/keep.md"]
    assert store.section_ids_for_source(after["docs/keep.md"]) == keep_ids
    assert "UntouchedKeepNeedle" in contents
    assert result["metrics"]["unrelated_files_reprocessed"] == 0
    if operation == "add":
        assert "docs/new.md" in after
        assert "AddedDeltaNeedle" in contents
    elif operation == "change":
        assert "AlphaAfterNeedle" in contents
        assert "AlphaBeforeNeedle" not in contents
    elif operation == "delete":
        assert "docs/b.md" not in after
        assert store.section_ids_for_source(before["docs/b.md"]) == []
        assert "BetaBeforeNeedle" not in contents
    else:
        assert "docs/a.md" not in after and "docs/renamed.md" in after
        assert store.section_ids_for_source(before["docs/a.md"]) == []
        assert store.section_ids_for_source(after["docs/renamed.md"])
        assert "AlphaBeforeNeedle" in contents


def test_public_unchanged_delta_is_idempotent(project_state):
    project, service, active = project_state
    before = _snapshot(active)
    result = _call(service, project, changed_paths=["docs/a.md"])
    assert result["status"] == "success", result
    assert result["metrics"]["files_reprocessed"] == 0
    assert _snapshot(active) == before


def test_public_existing_file_deletion_does_not_mutate_index(project_state):
    project, service, active = project_state
    before = _snapshot(active)
    result = _call(service, project, deleted_paths=["docs/a.md"])
    assert result["status"] == "failed", result
    assert "error" in result
    assert _snapshot(active) == before
    assert (project / "docs/a.md").is_file()


def test_public_symlink_escape_does_not_touch_index_or_external_file(project_state, tmp_path):
    project, service, active = project_state
    outside = tmp_path / "outside.md"
    outside.write_text("# External\n\nOutsideMustStayPrivateNeedle.\n", encoding="utf-8")
    before_bytes = outside.read_bytes()
    (project / "docs/external.md").symlink_to(outside)
    before = _snapshot(active)
    result = _call(service, project, changed_paths=["docs/external.md"])
    assert result["status"] == "failed", result
    assert outside.read_bytes() == before_bytes
    assert _snapshot(active) == before
