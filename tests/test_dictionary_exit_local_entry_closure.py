"""Effect-free local entry denial and authorization-specific MCP guidance."""
import errno
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from docmancer.docs.application import _project_docs_service_part01 as ingest_shard
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.dart_package_config import resolve_dart_package_roots, _resolve_root_uri
from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload
from docmancer.docs.service import LibraryDocsService

pytestmark = pytest.mark.behavioral


@contextmanager
def forbid_effects(monkeypatch):
    calls = []
    def deny(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unexpected local file/index effect")
    # Restore process-global filesystem methods before pytest formats a failure,
    # rather than waiting for the monkeypatch fixture's teardown.
    with monkeypatch.context() as effects:
        for name in ("open", "stat", "exists", "is_file", "is_dir", "resolve", "read_text", "read_bytes", "glob", "rglob", "iterdir"):
            effects.setattr(Path, name, deny)
        effects.setattr(os, "scandir", deny)
        yield calls, deny


def guarded_ingest_service(monkeypatch, deny):
    facade = SimpleNamespace(
        config=SimpleNamespace(index=SimpleNamespace(db_path="must-not-create.db")),
        _project_ingest_project_docs_impl=deny,
    )
    service = ProjectDocsService(facade)
    for name in ("_agent_instance", "_indexed_project_doc_sources", "read_project_metadata", "_repository_identity"):
        monkeypatch.setattr(service, name, deny, raising=False)
    for name in ("validate_project_path", "storage_writer_lease", "storage_mutation_lock", "extract_section_metadata_result"):
        monkeypatch.setattr(ingest_shard, name, deny)
    return service




def test_public_ingest_delegate_reaches_guard_without_storage_initialization(tmp_path, monkeypatch):
    with forbid_effects(monkeypatch) as (calls, deny):
        delegate = guarded_ingest_service(monkeypatch, deny)
        facade = SimpleNamespace(project_docs=delegate)
        with pytest.raises(PermissionError, match="ingestion is unresolved"):
            LibraryDocsService.ingest_project_docs(facade, str(tmp_path), with_vectors=True)
        assert calls == []














def test_existing_prepare_sync_catch_returns_specific_nonretryable_denial(tmp_path, monkeypatch):
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, current_docs_surface

    surface = current_docs_surface({})
    with forbid_effects(monkeypatch) as (calls, deny):
        project_docs = guarded_ingest_service(monkeypatch, deny)
        facade = SimpleNamespace(project_docs=project_docs)
        payload = call_docs_tool_payload(
            "prepare_docs", {"action": "sync_project_docs", "project_path": str(tmp_path)}, facade, surface=surface)
        assert payload["status"] == "failed"
        assert payload["error"]["reason_code"] == "permission_denied"
        assert payload["error"]["retryable"] is False
        assert "mutation authorization is missing" in payload["error"]["hints"][0]
        assert "explicit complete member mutation grant" in payload["error"]["hints"][0]
        assert calls == []
