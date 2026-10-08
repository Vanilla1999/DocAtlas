from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.core.config_resolution import ResolvedConfig
from docmancer.core.member_storage_policy import MemberStoragePolicy
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash, local_project_identity
from docmancer.docs.application.source_continuation import SourceReference
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import LocalMemberService, call_docs_tool_payload, read_docs_resource
from docmancer.mcp._docs_server_resources import MCP_RESOURCES


GUIDANCE_URIS = [resource["uri"] for resource in MCP_RESOURCES] + [
    "docmancer://workflow/project-docs//repo",
    "docmancer://library/python/sample/1.2.3",
]
UNKNOWN_URIS = ["docmancer://missing", "docmancer://library/python"]


def forbidden(*args, **kwargs):
    pytest.fail("guidance must not access services, tools, or storage")


@pytest.mark.parametrize("uri", GUIDANCE_URIS + UNKNOWN_URIS)
def test_guidance_and_unknown_resources_never_inspect_service(monkeypatch, uri):
    import docmancer.mcp._docs_server_part01 as implementation

    class NoServiceAccess:
        def __getattribute__(self, name):
            pytest.fail(f"service accessor executed: {name}")

    monkeypatch.setattr(implementation, "call_docs_tool_payload", forbidden)
    result = read_docs_resource(uri, NoServiceAccess())
    if uri in UNKNOWN_URIS:
        assert result is None
    else:
        assert result == read_docs_resource(uri)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    # pytest's private temporary root is outside /tmp/opencode, whose writable
    # ancestor is intentionally rejected by the unchanged storage policy.
    root = tmp_path / "project"
    root.mkdir()
    source = root / "README.md"
    source.write_text("# Guide\n\n" + "\n".join(f"Exact bounded line {i}." for i in range(100)) + "\n")
    catalog = root / "docatlas.project-docs.yaml"
    catalog.write_text(yaml.safe_dump({
        "schema_version": 1, "code_files": [], "documents": [{
            "path": "README.md", "role": "overview", "scope": "project",
            "authority": "source_of_truth", "status": "active", "description": "Guide",
        }],
    }))
    home = tmp_path / "app-home"
    monkeypatch.setenv("DOCATLAS_HOME", str(home))
    config = DocmancerConfig()
    config.index.provider = "sqlite"
    config.index.db_path = str(home / "mcp" / "members.db")
    config.index.extracted_dir = str(home / "mcp" / "extracted")
    service = LocalMemberService(ResolvedConfig(config, "explicit", None))
    entry = read_project_docs_catalog(root).entries[0]
    mutation = {
        "operation": "sync_project_docs", "confirm": True,
        "storage_path": config.index.db_path,
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "expected_generation_id": None, "documents": [{
            "path": entry.path, "content_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "catalog_entry_hash": catalog_entry_hash(entry),
        }],
    }
    result = call_docs_tool_payload("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(root), "mutation": mutation,
    }, service)
    assert result["status"] == "success"
    assert service._service is None
    assert service.member_storage_policy.validate()
    return service, root, source, mutation


@pytest.mark.parametrize("uri", GUIDANCE_URIS + UNKNOWN_URIS)
@pytest.mark.parametrize("barrier", ["validate", "materialize"])
def test_real_cold_service_guidance_skips_storage_and_materialization(prepared, monkeypatch, uri, barrier):
    service, _, _, _ = prepared
    if barrier == "validate":
        monkeypatch.setattr(MemberStoragePolicy, "validate", forbidden)
    else:
        monkeypatch.setattr(LocalMemberService, "materialize", forbidden)
    result = read_docs_resource(uri, service)
    assert result == read_docs_resource(uri)
    assert service._service is None


@pytest.fixture
def registered(prepared, monkeypatch):
    service, root, source, mutation = prepared
    owner = service.materialize()
    store = SQLiteStore(service.member_storage_policy.db_path)
    # Use the real fixture-owned store without constructing a provider agent.
    monkeypatch.setattr(owner.source_reader.gateway, "store_factory", lambda: store)
    ref = SourceReference(
        str(root), local_project_identity(root), "README.md",
        "sha256:" + mutation["documents"][0]["content_sha256"],
        mutation["documents"][0]["catalog_entry_hash"],
        "source_of_truth", "project", None, 2,
    )
    uri = owner.source_reader.issue(ref)
    assert uri is not None
    return service, owner.source_reader, ref, uri, source, mutation


def read_source(service, uri):
    return json.loads(read_docs_resource(uri, service)["text"])


def test_source_dispatch_validates_storage_and_preserves_bounded_identity(registered, monkeypatch):
    service, reader, ref, uri, source, _ = registered
    validate = MemberStoragePolicy.validate
    validations = []

    def observed(policy, *args, **kwargs):
        validations.append(policy)
        return validate(policy, *args, **kwargs)

    monkeypatch.setattr(MemberStoragePolicy, "validate", observed)
    first = read_source(service, uri)
    assert len(validations) >= 2  # dispatch plus materialize's target-bound check
    assert first["project_identity"] == ref.project_identity
    assert first["path"] == ref.path
    assert first["content_sha256"] == ref.content_sha256
    assert first["line_start"] == 3
    assert first["line_end"] - first["line_start"] + 1 <= reader.max_lines
    assert first["snippet"] == "\n".join(source.read_text().splitlines()[2:first["line_end"]])
    second = read_source(service, first["continuation"])
    assert second["line_start"] == first["line_end"] + 1
    assert second["continuation"] is None
    assert second["reason_code"] == "read_limit_reached"
    assert all(docs_context_budget_tokens(result) <= 600 for result in (first, second))
    assert read_source(service, uri) == {
        "status": "source_unavailable", "reason_code": "unknown_or_expired_reference",
    }


@pytest.mark.parametrize("change", ["storage", "identity", "snapshot", "generation", "unknown", "expired"])
def test_source_dispatch_still_denies_invalid_bindings(registered, monkeypatch, change):
    service, reader, ref, uri, source, mutation = registered
    if change == "storage":
        service.member_storage_policy.marker.unlink()
        monkeypatch.setattr(reader, "read", forbidden)
        with pytest.raises(PermissionError, match="adoption is forbidden"):
            read_source(service, uri)
        return
    if change == "identity":
        monkeypatch.setattr(reader.gateway, "identity_for_root", lambda root: "project:other")
    elif change == "snapshot":
        source.write_text(source.read_text() + "Changed snapshot.\n")
    elif change == "generation":
        source.write_text(source.read_text() + "New indexed generation.\n")
        next_mutation = {**mutation, "expected_generation_id": service.member_storage_policy.generation(),
                         "documents": [{**mutation["documents"][0],
                                        "content_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
        result = call_docs_tool_payload("prepare_docs", {
            "action": "sync_project_docs", "project_path": ref.project_root, "mutation": next_mutation,
        }, service)
        assert result["status"] == "success"
        assert service.member_storage_policy.generation() != next_mutation["expected_generation_id"]
    elif change == "unknown":
        uri = "docatlas://source/" + "0" * 24
    else:
        now = [0]
        monkeypatch.setattr(reader, "clock", lambda: now[0])
        uri = reader.issue(replace(ref, line_end=3))
        assert uri is not None
        now[0] = reader.retention_seconds + 1
    if change != "snapshot":
        monkeypatch.setattr(reader.gateway, "read_snapshot", forbidden)
    result = read_source(service, uri)
    assert result["status"] in {"source_unavailable", "source_changed"}
    assert "snippet" not in result
    assert result["reason_code"] == (
        "unknown_or_expired_reference" if change in {"unknown", "expired"}
        else "snapshot_digest_mismatch" if change == "snapshot"
        else "source_policy_or_snapshot_changed"
    )
