import json
import sqlite3
from pathlib import Path

import pytest

from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload, _service_for_project_path, read_docs_resource
from tests.test_clean_git_auto_sync import _commit_project


@pytest.mark.parametrize("explicit", [False, True])
def test_cached_service_sync_clear_rebuild_without_restart(tmp_path, monkeypatch, explicit):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    readme = "# Local documentation\n\nTo prepare local project documentation, call prepare_docs(action=\"sync_project_docs\").\n"
    (project / "README.md").write_text(readme)
    catalog = "schema_version: 1\ndocuments:\n  - path: README.md\n    role: runbook\n    scope: project\n    authority: source_of_truth\n    status: active\n    description: Local documentation preparation\n"
    (project / "docatlas.project-docs.yaml").write_text(catalog)
    (project / ".gitignore").write_text(".docatlas/\n")
    config_path = project / "docatlas.yaml"
    config_path.write_text("index:\n  db_path: .docatlas/project.db\n  extracted_dir: .docatlas/extracted\n")
    _commit_project(project)
    if explicit:
        from docmancer.core.storage_topology import StorageTopologyResolver
        topology = StorageTopologyResolver().resolve(project)
        service = LibraryDocsService(config=topology.config, config_source="explicit", config_path=config_path)
    else:
        service = LibraryDocsService()

    def call(tool, **args):
        return call_docs_tool_payload(tool, {"project_path": str(project), **args}, service)

    assert call("prepare_docs", action="sync_project_docs", with_vectors=False)["status"] == "success"
    owner = _service_for_project_path(service, {"project_path": str(project)})
    assert owner._agent_instance() is owner._agent_instance()
    old_agent = owner._agent_instance()
    alias = LibraryDocsService(config=owner.config)
    alias_agent = alias._agent_instance()
    service._project_service_cache[("alias", "alias-config", "")] = alias
    other = tmp_path / "other"
    other.mkdir()
    (other / "README.md").write_text(readme)
    (other / "docatlas.project-docs.yaml").write_text(catalog)
    (other / "docatlas.yaml").write_text(config_path.read_text())
    # Even an explicitly configured router can own already-cached services
    # for another storage identity. They must not be discarded on cleanup.
    from docmancer.core.storage_topology import StorageTopologyResolver
    other_topology = StorageTopologyResolver().resolve(other)
    other_owner = LibraryDocsService(config=other_topology.config, config_source=other_topology.config_source,
                                    config_path=other_topology.config_path,
                                    library_index_root=other_topology.library_index_root)
    service._project_service_cache[(str(other), "other-config", "")] = other_owner
    assert other_owner.sync_project_docs(str(other), with_vectors=False).status == "success"
    other_agent = other_owner._agent_instance()
    question = "How do I prepare local project documentation?"
    before = call("get_docs_context", question=question)
    assert before["status"] == "ok", before
    other_before = call_docs_tool_payload("get_docs_context", {"question": question, "project_path": str(other)}, other_owner)
    assert other_before["status"] == "ok", other_before
    other_uri = other_before["sources"][0]["source_uri"]
    preview = call("prepare_docs", action="clear_index", scope="project-local")
    assert preview["status"] == "confirmation_required", preview
    assert not getattr(owner, "_storage_cleared", False)
    stale = {**preview["arguments_patch"], "plan_digest": "0" * 64}
    assert call_docs_tool_payload("prepare_docs", stale, service)["status"] == "failed"
    assert not getattr(owner, "_storage_cleared", False)
    from docmancer.docs.infrastructure.storage_mutation_lock import storage_writer_lease
    with storage_writer_lease(owner.config.index.db_path, operation="lifecycle control writer"):
        blocked = call_docs_tool_payload("prepare_docs", preview["arguments_patch"], service)
        assert blocked["status"] == "failed", blocked
        assert not getattr(owner, "_storage_cleared", False)
    applied = call_docs_tool_payload("prepare_docs", preview["arguments_patch"], service)
    assert applied["status"] == "applied", applied
    assert not Path(owner.config.index.db_path).exists()
    assert alias._storage_cleared is True
    assert json.loads(read_docs_resource(before["sources"][0]["source_uri"], service)["text"])["reason_code"] == "unknown_or_expired_reference"
    assert not getattr(other_owner, "_storage_cleared", False)
    assert other_owner._agent_instance() is other_agent
    reference_result = json.loads(read_docs_resource(other_uri, service)["text"])
    assert reference_result["status"] == "complete", reference_result
    rebuilt = call("prepare_docs", action="sync_project_docs", with_vectors=False)
    assert rebuilt["status"] == "success", rebuilt
    after = call("get_docs_context", question=question)
    assert after["status"] == "ok", after
    assert any(source["path_or_url"] == "README.md" and "sync_project_docs" in source["snippet"] for source in after["sources"])
    new_owner = _service_for_project_path(service, {"project_path": str(project)})
    assert new_owner._agent_instance() is not old_agent
    from docmancer.mcp._docs_server_part01 import _live_storage_service
    assert _live_storage_service(alias)._agent_instance() is not alias_agent
    with sqlite3.connect(new_owner.config.index.db_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sources", "sections"} <= tables
    other_after = call_docs_tool_payload("get_docs_context", {"question": question, "project_path": str(other)}, other_owner)
    assert other_after["status"] == "ok", other_after
    assert (project / "README.md").read_text() == readme
    # Repeated clear must also retire a prior replacement, not just the first
    # owner retained by the long-lived router.
    again = call("prepare_docs", action="clear_index", scope="project-local")
    assert call_docs_tool_payload("prepare_docs", again["arguments_patch"], service)["status"] == "applied"
    assert call("prepare_docs", action="sync_project_docs", with_vectors=False)["status"] == "success"
    assert call("get_docs_context", question=question)["status"] == "ok"
    assert other_owner._agent_instance() is other_agent
