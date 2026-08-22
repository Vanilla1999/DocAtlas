#!/usr/bin/env python3
from __future__ import annotations

import copy

from eval.agent_developer_v1.installed_mcp_contract import EventLog, EXPECTED_TOOLS
from eval.agent_developer_v1.installed_mcp_report import (
    InstalledMCPReportError,
    verify_report,
)


SCHEMA_SHA = "1" * 64
ARTIFACT_SHA = "2" * 64
CLI_SHA = "3" * 64
COMMIT_SHA = "4" * 40


def _events() -> list[dict]:
    events = EventLog()
    events.add(
        "server_start",
        {
            "command": "doc-atlas",
            "args": ["mcp", "docs-serve"],
            "artifact_sha256": ARTIFACT_SHA,
            "source_commit": COMMIT_SHA,
        },
    )
    events.add(
        "mcp_tools_list",
        {
            "tool_names": list(EXPECTED_TOOLS),
            "schema_sha256": SCHEMA_SHA,
            "tool_count": 3,
        },
    )
    events.add(
        "model_request",
        {
            "turn": 1,
            "provider_id": "scripted",
            "model": "deterministic-script",
            "variant": None,
            "request_payload_sha256": "5" * 64,
            "tool_schema_sha256": SCHEMA_SHA,
        },
    )
    events.add(
        "model_format_failure",
        {"turn": 1, "error": "synthetic invalid action"},
    )
    events.add(
        "task_complete",
        {
            "passed": False,
            "context_call_count": 0,
            "false_supported": 0,
            "forbidden_source_contamination": 0,
            "failure_stages": ["model_format"],
        },
    )
    return events.rows()


def _report() -> dict:
    return {
        "schema_version": 1,
        "protocol": "installed-mcp-agent-v1",
        "claim_boundary": "pre-public-installed-harness",
        "artifact": {
            "origin": "reviewed-wheel",
            "distribution": "doc-atlas",
            "version": "1.3.1",
            "artifact_filename": "doc_atlas-1.3.1-py3-none-any.whl",
            "artifact_sha256": ARTIFACT_SHA,
            "source_commit": COMMIT_SHA,
            "python_version": "3.12.14",
            "cli_sha256": CLI_SHA,
            "public_release_verified": False,
        },
        "mcp": {
            "transport": "stdio",
            "server": ["doc-atlas", "mcp", "docs-serve"],
            "tool_inventory": list(EXPECTED_TOOLS),
            "schema_sha256": SCHEMA_SHA,
            "schema_digest_count": 1,
        },
        "provider": {
            "provider_id": "scripted",
            "model": "deterministic-script",
            "variant": None,
        },
        "limits": {"max_schema_repairs": 1, "public_task_count": 1},
        "task_count": 1,
        "executed_task_count": 1,
        "passed_tasks": 0,
        "pass_rate": 0.0,
        "false_supported": 0,
        "forbidden_source_contamination": 0,
        "infrastructure_errors": [],
        "tasks": [
            {
                "task_id": "synthetic-zero-call-failure",
                "passed": False,
                "score": {
                    "passed": False,
                    "scope_contract_ok": False,
                    "recovery_contract_ok": True,
                    "context_call_count": 0,
                    "false_supported": 0,
                    "forbidden_source_contamination": 0,
                    "errors": ["model output failed the outer action contract"],
                },
                "trajectory": [],
                "usage": [
                    {
                        "turn": 1,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                    }
                ],
                "events": _events(),
                "failure_stages": ["model_format"],
                "schema_repair_count": 0,
                "mcp_schema_sha256": SCHEMA_SHA,
            }
        ],
        "privacy": {
            "raw_prompts_persisted": False,
            "raw_tool_results_persisted": False,
            "absolute_project_paths_persisted": False,
            "event_hash_chain": True,
        },
    }


def _expect_error(fragment: str, report: dict, **kwargs) -> None:
    try:
        verify_report(report, **kwargs)
    except InstalledMCPReportError as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"expected error containing {fragment!r}, got {str(exc)!r}"
            ) from exc
    else:
        raise AssertionError(f"expected verifier failure containing {fragment!r}")


def test_zero_call_model_failure_is_valid_agent_evidence() -> None:
    summary = verify_report(
        _report(),
        expected_origin="reviewed-wheel",
        min_task_count=1,
        min_pass_rate=0.0,
    )
    assert summary["tool_attempts"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["claim_boundary"] == "pre-public-installed-harness"


def test_event_chain_tamper_fails_closed() -> None:
    report = _report()
    report["tasks"][0]["events"][1]["payload"]["tool_count"] = 4
    _expect_error("event digest mismatch", report)


def test_privacy_path_and_raw_prompt_fail_closed() -> None:
    report = _report()
    report["tasks"][0]["raw_prompt"] = "hidden"
    _expect_error("forbidden persisted field", report)

    report = _report()
    report["tasks"][0]["score"]["errors"] = ["leaked /home/user/project"]
    _expect_error("absolute local path leaked", report)


def test_public_claim_requires_public_origin_and_verification() -> None:
    _expect_error("public evidence requires PyPI origin", _report(), require_public=True)

    report = _report()
    report["artifact"]["origin"] = "public-pypi"
    _expect_error(
        "public evidence requires verified public release identity",
        report,
        require_public=True,
    )


def test_live_usage_requires_provider_identity() -> None:
    report = _report()
    report["provider"] = {
        "provider_id": "openai-api",
        "model": "gpt-5.6-luna",
        "variant": "medium",
    }
    _expect_error("lacks provider request/session identity", report)


def test_unknown_origin_and_failure_stage_fail_closed() -> None:
    report = _report()
    report["artifact"]["origin"] = "editable-checkout"
    _expect_error("unsupported artifact origin", report)

    report = _report()
    report["tasks"][0]["failure_stages"] = ["unknown"]
    _expect_error("invalid failure-stage attribution", report)


def main() -> int:
    checks = (
        test_zero_call_model_failure_is_valid_agent_evidence,
        test_event_chain_tamper_fails_closed,
        test_privacy_path_and_raw_prompt_fail_closed,
        test_public_claim_requires_public_origin_and_verification,
        test_live_usage_requires_provider_identity,
        test_unknown_origin_and_failure_stage_fail_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    print(f"Installed MCP contract self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
