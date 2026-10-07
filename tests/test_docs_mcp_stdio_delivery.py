"""Delivery validation and isolation; real retrieval runs in installed smoke."""
import hashlib
import os
from types import SimpleNamespace

import pytest

from scripts.docs_mcp_stdio_smoke import (
    bootstrap_library_fixture, bootstrap_ready_fixture, evidence_sizes,
    fixture_database_state, initialize_fixture_members, isolated_environment, payload, text_payload,
    validate_blocked_preparation, validate_patch_payload,
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
    blocked = {"status": "blocked", "reason_code": "unsafe_sqlite_path_mutation",
               "retryable": False, "mutation_performed": False}
    validate_blocked_preparation(blocked)
    with pytest.raises(AssertionError):
        validate_blocked_preparation({**blocked, "mutation_performed": True})


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


def test_ready_fixture_bootstrap_uses_real_store_and_local_catalog_binding(tmp_path):
    project = tmp_path / "ready"
    project.mkdir()
    (project / "README.md").write_text("# Docs\n\nStart with `doc-atlas mcp docs-serve`.\n")
    store, _mutation = initialize_fixture_members(project)
    bootstrap = bootstrap_ready_fixture(project)
    assert bootstrap["generation_id"].startswith("gen-")
    assert set(bootstrap["files"]) == {"README.md", "protocols.md", "packages/alpha/README.md", "packages/beta/README.md"}
    assert bootstrap["files"]["packages/alpha/README.md"]["scope"] == "module"
    with store._connect() as conn:
        assert store._active_generation_id(conn) == bootstrap["generation_id"]
        assert conn.execute("SELECT count(*) FROM generation_sources WHERE generation_id=?",
                            (bootstrap["generation_id"],)).fetchone()[0] == 4
        assert conn.execute("SELECT count(*) FROM retrieval_children_fts WHERE retrieval_children_fts MATCH 'alpha'").fetchone()[0] > 0


def test_evidence_byte_measurement_unions_overlapping_unicode_source_spans(tmp_path):
    raw = "αβγδε source"
    (tmp_path / "source.md").write_text(raw, encoding="utf-8")
    rows = [{"path": "source.md", "text": raw[start:end], "char_start": start, "char_end": end,
             "content_sha256": hashlib.sha256(raw[start:end].encode()).hexdigest(), "evidence_id": str(index)}
            for index, (start, end) in enumerate(((0, 4), (2, 7)))]
    report = evidence_sizes({"sources": rows}, tmp_path)
    assert report["source_text_utf8_bytes"] == sum(len(row["text"].encode()) for row in rows)
    assert report["unique_nonoverlap_utf8_bytes"] == len(raw[:7].encode())
    assert report["unique_nonoverlap_utf8_bytes"] < report["source_text_utf8_bytes"]
    docs = evidence_sizes({"sources": [{"path_or_url": "source.md", "snippet": raw[:4]}]}, tmp_path)
    assert docs["unique_nonoverlap_utf8_bytes"] == len(raw[:4].encode())
    rows[0]["text"] = "forged"
    with pytest.raises(AssertionError):
        evidence_sizes({"sources": rows}, tmp_path)


def test_library_fixture_versions_have_real_local_provenance_and_distinct_bytes(tmp_path):
    from pathlib import Path
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    project = tmp_path / "project"
    project.mkdir()
    libraries = bootstrap_library_fixture(project, tmp_path / "owned-home" / "docs-indexes")
    assert set(libraries) == {"1.0.0", "2.0.0"}
    assert libraries["1.0.0"]["content_sha256"] != libraries["2.0.0"]["content_sha256"]
    for version, fixture in libraries.items():
        source = Path(url2pathname(urlparse(fixture["source"]).path))
        assert source.is_relative_to(project) and source.is_file()
        assert version in source.read_text()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fixture["content_sha256"]
        assert fixture["generation_id"].startswith("gen-")
