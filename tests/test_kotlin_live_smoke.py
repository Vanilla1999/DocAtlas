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


def test_live_mode_requires_explicit_isolated_home(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCMANCER_HOME", raising=False)
    monkeypatch.setattr(
        SMOKE,
        "LibraryDocsService",
        lambda: (_ for _ in ()).throw(AssertionError("service must not start")),
    )

    with pytest.raises(SystemExit):
        SMOKE.main(
            [
                "--mode",
                "live",
                "--timeout",
                "5",
                "--output",
                str(tmp_path / "result.json"),
            ]
        )


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


def test_smoke_rejects_echoed_question_with_unrelated_citation():
    def call_tool(name, arguments):
        if name == "prepare_docs":
            return {"status": "pending", "job_id": "job-1"}
        if name == "docs_status":
            return {"status": "succeeded", "job_id": arguments["job_id"]}
        if name == "get_docs_context":
            return {
                "status": "success",
                "question": SMOKE.QUESTION,
                "resolved_version": SMOKE.VERSION,
                "canonical_source_identity": "https://example.com/unrelated",
                "results": [
                    {
                        "source": "https://example.com/unrelated",
                        "content": "This page contains no Kotlin example.",
                    }
                ],
            }
        raise AssertionError(name)

    with pytest.raises(RuntimeError, match="cited code-bearing"):
        SMOKE.run_smoke(
            call_tool,
            mode="live",
            timeout_seconds=5,
            command="kotlin_live_smoke.py --mode live",
        )


def test_smoke_requests_full_provenance_and_rejects_missing_identity():
    observed_context_arguments = None

    def call_tool(name, arguments):
        nonlocal observed_context_arguments
        if name == "prepare_docs":
            return {"status": "pending", "job_id": "job-1"}
        if name == "docs_status":
            return {"status": "partial", "job_id": arguments["job_id"]}
        if name == "get_docs_context":
            observed_context_arguments = dict(arguments)
            return {
                "status": "success",
                "results": [
                    {
                        "source": SMOKE.SOURCE_URL,
                        "content": "```kotlin\nrunBlocking { launch { println(1) } }\n```",
                    }
                ],
            }
        raise AssertionError(name)

    with pytest.raises(RuntimeError, match="resolved_version"):
        SMOKE.run_smoke(
            call_tool,
            mode="live",
            timeout_seconds=5,
            command="kotlin_live_smoke.py --mode live",
        )

    assert observed_context_arguments is not None
    assert observed_context_arguments["output_mode"] == "full"


def test_committed_fixture_artifact_matches_machine_schema():
    schema = json.loads((ROOT / "eval/kotlin_smoke/artifact.schema.json").read_text(encoding="utf-8"))
    artifact = json.loads((ROOT / "eval/kotlin_smoke/task14_fixture.json").read_text(encoding="utf-8"))

    jsonschema.validate(artifact, schema)
    assert SMOKE.validate_artifact(artifact) == []


def test_machine_schema_rejects_unpinned_source_and_version():
    schema = json.loads((ROOT / "eval/kotlin_smoke/artifact.schema.json").read_text(encoding="utf-8"))
    artifact = json.loads((ROOT / "eval/kotlin_smoke/task14_fixture.json").read_text(encoding="utf-8"))
    artifact.update(
        {
            "source_ref": "Kotlin/kotlinx.coroutines@master",
            "requested_version": "master",
            "resolved_version": "master",
            "canonical_source_identity": "https://example.com/unrelated",
            "citations": ["https://example.com/unrelated"],
        }
    )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(artifact, schema)


def test_task14_does_not_expand_public_docs_mcp_surface():
    from docmancer.mcp.docs_server import build_docs_surface, DocsServerConfig

    assert {tool.name for tool in build_docs_surface(DocsServerConfig()).tools} == {
        "get_docs_context", "prepare_docs", "docs_status"
    }
