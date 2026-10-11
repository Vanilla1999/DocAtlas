"""Fixture-host infrastructure; no answer oracle or live provider changes."""
from contextlib import contextmanager
import asyncio
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from eval.agent_developer_v1 import installed_mcp_benchmark as benchmark
from eval.agent_developer_v1.installed_mcp_contract import ArtifactIdentity, EventLog, ScriptedPlanner, sha256_json
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_tool_data import PUBLIC_ADVERTISED_INPUT_SCHEMAS
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, create_local_mcp_service


@pytest.fixture
def fixture_host(monkeypatch):
    with benchmark._fixture_workspace("contract-test") as root:
        project = root / "project"
        project.mkdir(mode=0o700)
        home = root / "docatlas-home"
        home.mkdir(mode=0o700)
        (project / "README.md").write_bytes(b"# Fixture\r\n\r\nAuthored documentation.\r\n")
        (project / "docatlas.project-docs.yaml").write_text(json.dumps({
            "schema_version": 1, "documents": [{"path": "README.md", "role": "overview",
            "scope": "project", "description": "Fixture"}], "code_files": []}))
        monkeypatch.setenv("DOCATLAS_HOME", str(home))
        monkeypatch.delenv("DOCATLAS_INDEX_DB_PATH", raising=False)
        monkeypatch.setenv("DOCATLAS_OFFLINE", "1")
        yield project, home


def test_bootstrap_exact_schema_and_authored_byte_hashes(fixture_host):
    project, home = fixture_host
    request = benchmark._fixture_bootstrap(project, home, fixture_author_confirm=True)
    jsonschema.validate(request, PUBLIC_ADVERTISED_INPUT_SCHEMAS["prepare_docs"])
    mutation = request["mutation"]
    assert set(request) == {"action", "project_path", "mutation"}
    assert mutation["confirm"] is True
    assert mutation["expected_generation_id"] is None
    assert mutation["storage_path"] == str(home / "mcp-members" / "members.db")
    assert mutation["catalog_sha256"] == hashlib.sha256((project / "docatlas.project-docs.yaml").read_bytes()).hexdigest()
    entry = read_project_docs_catalog(project).entries[0]
    assert mutation["documents"] == [{"path": "README.md",
        "content_sha256": hashlib.sha256((project / "README.md").read_bytes()).hexdigest(),
        "catalog_entry_hash": catalog_entry_hash(entry)}]
    assert not (home / "mcp-members").exists()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**request, "with_vectors": False}, PUBLIC_ADVERTISED_INPUT_SCHEMAS["prepare_docs"])




def test_missing_or_invalid_finite_catalog_denied(fixture_host):
    project, home = fixture_host
    (project / "docatlas.project-docs.yaml").write_text('{"schema_version":1,"roots":[{"path":"."}]}')
    with pytest.raises(ValueError):
        benchmark._fixture_bootstrap(project, home, fixture_author_confirm=True)
    assert not (home / "mcp-members").exists()


def test_cold_service_no_index_before_confirmation_and_real_cas(fixture_host):
    project, home = fixture_host
    service = create_local_mcp_service()
    database = home / "mcp-members" / "members.db"
    assert not database.exists()
    denied = call_docs_tool_payload("prepare_docs", {"action": "sync_project_docs", "project_path": str(project)}, service)
    assert denied.get("status") != "success"
    assert not database.exists()
    request = benchmark._fixture_bootstrap(project, home, fixture_author_confirm=True)
    prepared = call_docs_tool_payload("prepare_docs", request, service)
    assert prepared["status"] == "success", prepared
    generation = prepared["metrics"]["generation_id"]
    assert generation == service.member_storage_policy.generation()
    assert call_docs_tool_payload("prepare_docs", request, service).get("status") != "success"
    request["mutation"]["expected_generation_id"] = generation
    repeat = call_docs_tool_payload("prepare_docs", request, service)
    assert repeat["status"] == "success", repeat
    assert repeat["metrics"]["generation_id"] == generation


def test_private_workspace_ignores_temp_alias_and_rejects_foreign_ancestor(monkeypatch, tmp_path):
    monkeypatch.setenv("TMPDIR", str(tmp_path / "untrusted-alias"))
    with benchmark._fixture_workspace("private-test") as root:
        assert root.parent == Path.home()
        assert root.stat().st_mode & 0o777 == 0o700
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: unsafe))
    with pytest.raises(PermissionError):
        with benchmark._fixture_workspace("denied"):
            pytest.fail("unsafe ancestor accepted")




