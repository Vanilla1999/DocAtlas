"""Delivery validation and isolation; real retrieval runs in installed smoke."""
import hashlib
import os
from types import SimpleNamespace

import pytest

from scripts.docs_mcp_stdio_smoke import (
    fixture_database_state, initialize_fixture_members, isolated_environment, payload, text_payload, validate_patch_payload,
)
from docmancer.docs.application.action_packet import build_action_packet, refresh_action_packet_estimate


def test_patch_validator_preserves_large_utf8_evidence_and_checks_hash():
    text = "必要な unique evidence\n" * 3000
    value = build_action_packet(question="Inspect evidence", context_pack=[{
        "path": "docs/evidence.md", "content": text, "display_text": text,
        "source_class": "project_doc", "doc_scope": "project", "authority": "canonical",
        "stable_chunk_id": "unique-window", "parent_logical_id": "unique-parent",
        "char_start": 13, "char_end": 13 + len(text),
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }], required_target_paths=["missing.py"])
    value["kind"] = "patch_context"
    refresh_action_packet_estimate(value)
    validate_patch_payload(value, completeness="partial")
    assert len(text.encode()) > 32768
    value["sources"][0]["content_sha256"] = "0" * 64
    refresh_action_packet_estimate(value)
    with pytest.raises(AssertionError):
        validate_patch_payload(value)


def test_fixture_environment_does_not_inherit_configuration_or_credentials(tmp_path, monkeypatch):
    for key in ("PYTHONPATH", "OPENCODE_CONFIG", "OPENAI_API_KEY", "DOCATLAS_CONFIG"):
        monkeypatch.setenv(key, "foreign")
    env = isolated_environment(tmp_path)
    assert all(key not in env for key in ("PYTHONPATH", "OPENCODE_CONFIG", "OPENAI_API_KEY", "DOCATLAS_CONFIG"))
    assert env["DOCATLAS_HOME"] == str(tmp_path / "docatlas-home")
    assert env["HOME"] == env["USERPROFILE"]
    assert os.environ["OPENAI_API_KEY"] == "foreign"


def test_strict_validator_accepts_failure_and_rejects_unknown_authority():
    value = {"schema_version": 4, "kind": "patch_context", "result": "failure",
             "completeness": "unavailable", "edit_ready": False,
             "missing": ["no_evidence"], "estimated_tokens": 1}
    refresh_action_packet_estimate(value)
    validate_patch_payload(value, completeness="unavailable")
    value["consent"] = True
    refresh_action_packet_estimate(value)
    with pytest.raises(AssertionError, match="Additional properties"):
        validate_patch_payload(value)
    terminal = {"status": "failed", "retryable": False}
    result = SimpleNamespace(isError=True, structuredContent=terminal, content=[])
    with pytest.raises(AssertionError):
        payload(result)
    assert payload(result, allow_error=True) == terminal
    result.structuredContent = None
    result.content = [SimpleNamespace(text='{"status":"failed","retryable":false}')]
    assert text_payload(result, allow_error=True) == terminal


def test_explicit_fixture_grant_binds_actual_catalog_members_and_empty_storage(tmp_path):
    from docmancer.docs.application.project_docs_member_transaction import MemberTransaction

    project = tmp_path / "fixture"
    project.mkdir()
    (project / "README.md").write_text("# Fixture\n\nDocumentation evidence.\n")
    store, mutation = initialize_fixture_members(project)
    parsed = MemberTransaction.parse(mutation, operation="sync_project_docs")
    assert parsed.storage_path == str(project / ".docatlas" / "docatlas.db")
    assert parsed.expected_generation_id is None
    assert {document.path for document in parsed.documents} == {"README.md", "protocols.md"}
    assert all(document.catalog_entry_hash.startswith("sha256:") for document in parsed.documents)
    assert (project / "protocols.md").stat().st_size > 32768
    for document in parsed.documents:
        assert document.content_sha256 == hashlib.sha256((project / document.path).read_bytes()).hexdigest()
    state = fixture_database_state(store.db_path)
    assert all(not rows for rows in state.values())
