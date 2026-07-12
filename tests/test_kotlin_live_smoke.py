from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import jsonschema


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kotlin_live_smoke.py"
ROOT = SCRIPT.parents[1]
SPEC = importlib.util.spec_from_file_location("kotlin_live_smoke", SCRIPT)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


def test_fixture_mode_writes_valid_sanitized_artifact(tmp_path):
    output = tmp_path / "kotlin-smoke.json"

    assert SMOKE.main(["--mode", "fixture", "--timeout", "5", "--output", str(output)]) == 0

    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert SMOKE.validate_artifact(artifact) == []
    assert artifact["terminal_status"] == "partial"
    assert artifact["query"] == SMOKE.QUESTION
    assert artifact["citations"] == [SMOKE.SOURCE_URL]
    assert "content" not in artifact


def test_smoke_rejects_timeout_above_protocol_bound(tmp_path):
    with pytest.raises(ValueError, match="at most 180"):
        SMOKE.main([
            "--mode", "fixture", "--timeout", "181", "--output", str(tmp_path / "result.json")
        ])


def test_artifact_schema_rejects_network_failure_as_closure():
    artifact = {
        "schema_version": "kotlin-smoke-1.0",
        "mode": "live",
        "command": "smoke",
        "docatlas_commit": "abc",
        "source_ref": "Kotlin/kotlinx.coroutines@1.8.1",
        "elapsed_ms": 10,
        "terminal_status": "failed",
        "citations": [],
        "requested_version": "1.8.1",
        "resolved_version": "1.8.1",
        "canonical_source_identity": "github:Kotlin/kotlinx.coroutines@1.8.1",
        "query": SMOKE.QUESTION,
        "code_match": False,
        "recorded_at": "2026-07-12T00:00:00+00:00",
    }

    errors = SMOKE.validate_artifact(artifact)
    assert "terminal_status must be succeeded or partial" in errors
    assert "code_match must be true" in errors


def test_committed_fixture_artifact_matches_machine_schema():
    schema = json.loads((ROOT / "eval/kotlin_smoke/artifact.schema.json").read_text(encoding="utf-8"))
    artifact = json.loads((ROOT / "eval/kotlin_smoke/task14_fixture.json").read_text(encoding="utf-8"))

    jsonschema.validate(artifact, schema)
    assert SMOKE.validate_artifact(artifact) == []


def test_task14_does_not_expand_public_docs_mcp_surface():
    from docmancer.mcp.docs_server import build_docs_surface, DocsServerConfig

    assert {tool.name for tool in build_docs_surface(DocsServerConfig()).tools} == {
        "get_docs_context", "prepare_docs", "docs_status"
    }
