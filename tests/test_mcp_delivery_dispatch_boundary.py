"""Project mutation validation must precede project-facade initialization."""
from types import SimpleNamespace

import pytest

from docmancer.mcp import _docs_server_part01 as dispatch
from docmancer.docs.application.project_docs_service import ProjectDocsService


def _request():
    return {"action": "sync_project_docs", "project_path": "/fixture/project",
        "mutation": {"operation": "sync_project_docs", "confirm": True,
            "storage_path": "/fixture/project/.docatlas/docatlas.db",
            "catalog_sha256": "a" * 64, "expected_generation_id": None,
            "documents": [{"path": "README.md", "content_sha256": "b" * 64,
                "catalog_entry_hash": "sha256:" + "c" * 64}]}}


def test_bound_member_lane_does_not_construct_project_service(monkeypatch):
    calls = []

    def reject(project_path, *, mutation):
        calls.append((project_path, mutation))
        raise PermissionError("fixture member binding is invalid")

    def forbidden(*args, **kwargs):
        pytest.fail("project facade initialized before member validation")

    monkeypatch.setattr(dispatch, "_service_for_project_path", forbidden)
    service = SimpleNamespace(project_docs=SimpleNamespace(sync_project_docs=reject))
    result = dispatch.call_docs_tool_payload("prepare_docs", _request(), service)
    assert result["error"]["reason_code"] == "permission_denied"
    assert calls == [("/fixture/project", _request()["mutation"])]


def test_missing_grant_has_no_project_service_initialization(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("missing grant reached project service initialization")

    monkeypatch.setattr(dispatch, "_service_for_project_path", forbidden)
    service = SimpleNamespace(project_docs=ProjectDocsService(SimpleNamespace()))
    result = dispatch.call_docs_tool_payload("prepare_docs", {
        "action": "sync_project_docs", "project_path": "/fixture/project",
    }, service)
    assert result["error"]["reason_code"] in {"validation_error", "permission_denied"}


def test_other_project_tools_keep_existing_routing(monkeypatch):
    calls = []

    def refuse(service, args, *, read_only_startup):
        assert read_only_startup is True
        calls.append(args)
        raise PermissionError("fixture read topology denied")

    monkeypatch.setattr(dispatch, "_service_for_project_path", refuse)
    result = dispatch.call_docs_tool_payload("get_docs_context", {
        "question": "Fixture evidence", "project_path": "/fixture/project",
    }, SimpleNamespace())
    assert result["error"]["reason_code"] == "permission_denied"
    assert len(calls) == 1
