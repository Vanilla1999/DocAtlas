"""Delivery validation and isolation; real retrieval runs in installed smoke."""
import hashlib
import os

import pytest

from scripts.docs_mcp_stdio_smoke import isolated_environment, validate_patch_payload


def test_patch_validator_preserves_large_utf8_evidence_and_checks_hash():
    text = "必要な unique evidence\n" * 3000
    source = {"text": text, "char_start": 13, "char_end": 13 + len(text),
              "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "instruction_trust": "untrusted_data"}
    value = {"kind": "patch_context", "schema_version": 4, "edit_ready": False,
             "result": "data", "completeness": "partial", "sources": [source]}
    validate_patch_payload(value, completeness="partial")
    assert len(text.encode()) > 32768
    source["content_sha256"] = "0" * 64
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
