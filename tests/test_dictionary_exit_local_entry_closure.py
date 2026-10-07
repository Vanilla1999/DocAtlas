"""Effect-free local entry denial and authorization-specific MCP guidance."""
import errno
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from docmancer.docs.application import _project_docs_service_part01 as ingest_shard
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.dart_package_config import resolve_dart_package_roots, _resolve_root_uri
from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload
from docmancer.docs.service import LibraryDocsService

pytestmark = pytest.mark.behavioral


def forbid_effects(monkeypatch):
    calls = []
    def deny(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unexpected local file/index effect")
    for name in ("open", "stat", "exists", "is_file", "is_dir", "resolve", "read_text", "read_bytes", "glob", "rglob", "iterdir"):
        monkeypatch.setattr(Path, name, deny)
    monkeypatch.setattr(os, "scandir", deny)
    return calls, deny


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


@pytest.mark.parametrize("held", [False, True])
@pytest.mark.parametrize("arguments", [
    {}, dict(skip_known=False), dict(with_vectors=True),
    dict(_candidate_paths={"README.md"}), dict(_candidate_paths=set()),
])
def test_direct_ingest_denies_before_probes_adapters_index_queue_lock_or_staging(tmp_path, monkeypatch, held, arguments):
    calls, deny = forbid_effects(monkeypatch)
    service = guarded_ingest_service(monkeypatch, deny)
    with pytest.raises(PermissionError, match="no explicit mutation grant and validated member transaction") as caught:
        service.ingest_project_docs(str(tmp_path), _coordination_held=held, **arguments)
    assert caught.value.errno is None
    assert "catalog membership does not authorize indexing, staging or ingestion" in str(caught.value)
    assert calls == []


def test_public_ingest_delegate_reaches_guard_without_storage_initialization(tmp_path, monkeypatch):
    calls, deny = forbid_effects(monkeypatch)
    delegate = guarded_ingest_service(monkeypatch, deny)
    facade = SimpleNamespace(project_docs=delegate)
    with pytest.raises(PermissionError, match="ingestion is unresolved"):
        LibraryDocsService.ingest_project_docs(facade, str(tmp_path), with_vectors=True)
    assert calls == []


@pytest.mark.parametrize("state", ["absent", "empty", "invalid"])
@pytest.mark.parametrize("export", ["direct", "shared", "part02", "facade"])
def test_public_dart_resolver_and_wildcard_exports_never_probe_or_read(tmp_path, monkeypatch, state, export):
    from docmancer.docs import _patch_plan_context_shared, _patch_plan_context_part02, patch_plan_context

    if state != "absent":
        (tmp_path / "docatlas.project-docs.yaml").write_text(
            "schema_version: 1\ndocuments: []\ncode_files: []\n" if state == "empty" else "schema_version: 900\n")
    config_dir = tmp_path / ".dart_tool"
    config_dir.mkdir()
    (config_dir / "package_config.json").write_text(
        '{"configVersion":2,"packages":[{"name":"foreign","rootUri":"file:///unselected/external/root","packageUri":"lib/"}]}')
    functions = {
        "direct": resolve_dart_package_roots,
        "shared": _patch_plan_context_shared.resolve_dart_package_roots,
        "part02": _patch_plan_context_part02.resolve_dart_package_roots,
        "facade": patch_plan_context.resolve_dart_package_roots,
    }
    calls, _deny = forbid_effects(monkeypatch)
    roots, warnings = functions[export](tmp_path)
    assert roots == {}
    assert warnings == [
        "Dart package roots unresolved: no explicit finite dependency metadata/source read contract; "
        "no package_config or imported source roots were inspected."
    ]
    assert calls == []


def test_dart_resolver_does_not_even_coerce_unknown_project_path(monkeypatch):
    class UnknownRoot:
        def __fspath__(self):
            raise AssertionError("path coercion before a finite read contract")
    calls, _deny = forbid_effects(monkeypatch)
    roots, warnings = resolve_dart_package_roots(UnknownRoot())
    assert roots == {} and "unresolved" in warnings[0]
    assert calls == []


def test_pure_uri_grammar_remains_without_filesystem_authorization(monkeypatch):
    calls, _deny = forbid_effects(monkeypatch)
    assert _resolve_root_uri("file:///unselected/a%20b", Path("config")) == Path("/unselected/a b")
    assert _resolve_root_uri("https://unselected.invalid/root", Path("config")) is None
    assert _resolve_root_uri("../literal", Path("config")) == Path("config/../literal")
    assert calls == []


@pytest.mark.parametrize("operation", ["ingest", "sync"])
def test_actual_local_denial_has_specific_guidance_without_protocol_changes(tmp_path, monkeypatch, operation):
    calls, deny = forbid_effects(monkeypatch)
    service = guarded_ingest_service(monkeypatch, deny)
    with pytest.raises(PermissionError) as caught:
        getattr(service, operation + "_project_docs")(str(tmp_path))
    payload = build_mcp_error_payload(
        reason_code="permission_denied", message="permission_denied: request failed",
        exception=caught.value, tool="prepare_docs", phase="execution", debug=True,
    )
    assert payload["status"] == "failed"
    error = payload["error"]
    assert error["reason_code"] == "permission_denied"
    assert error["retryable"] is False and error["exception_type"] == "PermissionError"
    assert error["message"] == "permission_denied: request failed"
    assert error["traceback"] == "<redacted traceback>"
    assert "mutation authorization is missing" in error["hints"][0]
    assert "Check filesystem permissions" not in error["hints"][0]
    assert calls == []


@pytest.mark.parametrize("exception", [
    PermissionError(errno.EACCES, "Permission denied", "/private/resource"),
    PermissionError(errno.EPERM, "Operation not permitted"),
    PermissionError("unrelated permission failure"),
])
def test_real_filesystem_and_unknown_permission_errors_keep_original_guidance(exception):
    payload = build_mcp_error_payload(reason_code="permission_denied", message="request failed", exception=exception)
    assert payload["error"]["hints"] == ["Check filesystem permissions or run with access to the requested resource."]
    assert payload["error"]["retryable"] is False


def test_known_message_without_permission_exception_does_not_reclassify_errors():
    message = (
        "Project docs ingestion is unresolved: this API has no explicit mutation grant and validated "
        "member transaction; catalog membership does not authorize indexing, staging or ingestion."
    )
    payload = build_mcp_error_payload(reason_code="permission_denied", message=message)
    assert payload["error"]["hints"] == ["Check filesystem permissions or run with access to the requested resource."]
    payload = build_mcp_error_payload(reason_code="handler_exception", message=message, exception=RuntimeError(message))
    assert payload["error"]["reason_code"] == "handler_exception"
    assert "handler issue" in payload["error"]["hints"][0]


def test_existing_prepare_sync_catch_returns_specific_nonretryable_denial(tmp_path, monkeypatch):
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, current_docs_surface

    surface = current_docs_surface({})
    calls, deny = forbid_effects(monkeypatch)
    project_docs = guarded_ingest_service(monkeypatch, deny)
    facade = SimpleNamespace(project_docs=project_docs)
    payload = call_docs_tool_payload(
        "prepare_docs", {"action": "sync_project_docs", "project_path": str(tmp_path)}, facade, surface=surface)
    assert payload["status"] == "failed"
    assert payload["error"]["reason_code"] == "permission_denied"
    assert payload["error"]["retryable"] is False
    assert "mutation authorization is missing" in payload["error"]["hints"][0]
    assert calls == []
