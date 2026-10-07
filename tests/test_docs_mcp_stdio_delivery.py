"""Delivery validation and isolation; real retrieval runs in installed smoke."""
import hashlib
import os

import pytest

from scripts.docs_mcp_stdio_smoke import isolated_environment, validate_patch_payload
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
