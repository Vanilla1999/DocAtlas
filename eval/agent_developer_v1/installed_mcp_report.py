from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from eval.agent_developer_v1.installed_mcp_contract import (
    EXPECTED_TOOLS,
    PROTOCOL,
    REPORT_SCHEMA_VERSION,
    canonical_json,
)


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ABSOLUTE_PATH_MARKERS = (
    "/home/",
    "/Users/",
    "/tmp/",
    "\\Users\\",
    ":\\",
)
FORBIDDEN_KEYS = {
    "api_key",
    "authorization",
    "raw_prompt",
    "raw_result",
    "raw_environment",
    "stderr",
    "stdout",
}
ALLOWED_ORIGINS = {"reviewed-wheel", "public-pypi"}
ALLOWED_FAILURE_STAGES = {
    "model_format",
    "mcp_schema",
    "harness_policy",
    "server_validation",
    "retrieval",
    "support",
    "recovery",
    "budget",
}


class InstalledMCPReportError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InstalledMCPReportError(message)


def _walk(value: Any, *, path: str = "$"):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path=f"{path}[{index}]")


def _validate_privacy(report: dict[str, Any]) -> None:
    for path, value in _walk(report):
        key = path.rsplit(".", 1)[-1].lower()
        if key in FORBIDDEN_KEYS:
            raise InstalledMCPReportError(
                f"forbidden persisted field at {path}"
            )
        if not isinstance(value, str):
            continue
        if any(marker in value for marker in ABSOLUTE_PATH_MARKERS):
            raise InstalledMCPReportError(
                f"absolute local path leaked at {path}"
            )
        lowered = value.lower()
        if lowered.startswith(("sk-", "bearer ")):
            raise InstalledMCPReportError(
                f"credential-like value leaked at {path}"
            )


def _event_digest(event: dict[str, Any]) -> str:
    unsigned = {
        key: value
        for key, value in event.items()
        if key != "event_sha256"
    }
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


def _validate_event_chain(events: list[dict[str, Any]], task_id: str) -> None:
    previous: str | None = None
    for index, event in enumerate(events, start=1):
        _require(isinstance(event, dict), f"{task_id}: event is not an object")
        _require(
            event.get("seq") == index,
            f"{task_id}: event sequence is not contiguous",
        )
        _require(
            event.get("previous_event_sha256") == previous,
            f"{task_id}: event chain predecessor mismatch",
        )
        digest = str(event.get("event_sha256") or "")
        _require(
            SHA256_RE.fullmatch(digest) is not None,
            f"{task_id}: invalid event digest",
        )
        _require(
            digest == _event_digest(event),
            f"{task_id}: event digest mismatch",
        )
        previous = digest


def _validate_usage(
    usage_rows: list[dict[str, Any]],
    *,
    provider_id: str,
    task_id: str,
) -> None:
    for row in usage_rows:
        _require(isinstance(row, dict), f"{task_id}: usage row is not an object")
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            value = row.get(key)
            if value is None:
                continue
            _require(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0,
                f"{task_id}: invalid {key}",
            )
        if provider_id != "scripted":
            request_ids = row.get("request_ids")
            request_id = str(row.get("request_id") or "")
            session_ids = row.get("session_ids")
            _require(
                bool(request_id)
                or isinstance(request_ids, dict)
                and bool(request_ids)
                or isinstance(session_ids, list)
                and bool(session_ids),
                f"{task_id}: live usage lacks provider request/session identity",
            )


def verify_report(
    report: dict[str, Any],
    *,
    expected_origin: str | None = None,
    require_public: bool = False,
    min_task_count: int = 1,
    min_pass_rate: float = 0.0,
    require_schema_repair: bool = False,
) -> dict[str, Any]:
    _require(
        report.get("schema_version") == REPORT_SCHEMA_VERSION,
        "installed MCP report schema_version mismatch",
    )
    _require(
        report.get("protocol") == PROTOCOL,
        "installed MCP report protocol mismatch",
    )
    artifact = report.get("artifact")
    _require(isinstance(artifact, dict), "artifact identity is missing")
    origin = str(artifact.get("origin") or "")
    _require(origin in ALLOWED_ORIGINS, "unsupported artifact origin")
    if expected_origin is not None:
        _require(origin == expected_origin, "artifact origin mismatch")
    _require(
        artifact.get("distribution") == "doc-atlas",
        "distribution identity mismatch",
    )
    _require(bool(str(artifact.get("version") or "")), "version is missing")
    for key in ("artifact_sha256", "cli_sha256"):
        _require(
            SHA256_RE.fullmatch(str(artifact.get(key) or "")) is not None,
            f"invalid artifact identity field: {key}",
        )
    _require(
        COMMIT_RE.fullmatch(str(artifact.get("source_commit") or ""))
        is not None,
        "invalid source commit",
    )

    claim_boundary = str(report.get("claim_boundary") or "")
    if require_public:
        _require(origin == "public-pypi", "public evidence requires PyPI origin")
        _require(
            artifact.get("public_release_verified") is True,
            "public evidence requires verified public release identity",
        )
        _require(
            claim_boundary == "public-installed-agent-evidence",
            "public claim boundary mismatch",
        )
    else:
        _require(
            claim_boundary
            in {
                "pre-public-installed-harness",
                "public-installed-agent-evidence",
            },
            "unsupported claim boundary",
        )

    mcp = report.get("mcp")
    _require(isinstance(mcp, dict), "MCP identity is missing")
    _require(mcp.get("transport") == "stdio", "MCP transport must be stdio")
    _require(
        tuple(mcp.get("tool_inventory") or ()) == EXPECTED_TOOLS,
        "public MCP inventory mismatch",
    )
    _require(
        mcp.get("schema_digest_count") == 1,
        "all tasks must observe one exact MCP schema digest",
    )
    _require(
        SHA256_RE.fullmatch(str(mcp.get("schema_sha256") or "")) is not None,
        "MCP schema digest is missing",
    )

    provider = report.get("provider")
    _require(isinstance(provider, dict), "provider identity is missing")
    provider_id = str(provider.get("provider_id") or "")
    _require(bool(provider_id), "provider id is missing")
    _require(bool(str(provider.get("model") or "")), "model identity is missing")

    task_count = report.get("task_count")
    executed = report.get("executed_task_count")
    tasks = report.get("tasks")
    _require(
        isinstance(task_count, int) and task_count >= min_task_count,
        "task_count is below the required minimum",
    )
    _require(isinstance(tasks, list), "tasks must be a list")
    _require(
        executed == len(tasks),
        "executed_task_count does not match task rows",
    )
    _require(
        not report.get("infrastructure_errors"),
        "report contains infrastructure errors",
    )
    _require(
        report.get("false_supported") == 0,
        "false-supported outcomes are forbidden",
    )
    _require(
        report.get("forbidden_source_contamination") == 0,
        "forbidden-source contamination is forbidden",
    )
    pass_rate = report.get("pass_rate")
    _require(
        isinstance(pass_rate, (int, float))
        and not isinstance(pass_rate, bool)
        and 0.0 <= float(pass_rate) <= 1.0,
        "pass_rate is invalid",
    )
    _require(
        float(pass_rate) >= min_pass_rate,
        "pass_rate is below the requested threshold",
    )

    seen: set[str] = set()
    schema_failures = 0
    attempted_calls = 0
    for row in tasks:
        _require(isinstance(row, dict), "task row is not an object")
        task_id = str(row.get("task_id") or "")
        _require(task_id and task_id not in seen, "duplicate/empty task id")
        seen.add(task_id)
        events = row.get("events")
        _require(isinstance(events, list) and events, f"{task_id}: events missing")
        _validate_event_chain(events, task_id)
        _validate_usage(
            list(row.get("usage") or ()),
            provider_id=provider_id,
            task_id=task_id,
        )
        kinds = [str(event.get("kind") or "") for event in events]
        _require("mcp_tools_list" in kinds, f"{task_id}: tools/list not recorded")
        _require("task_complete" in kinds, f"{task_id}: completion not recorded")
        attempted_calls += kinds.count("tool_attempt")
        schema_failures += kinds.count("mcp_schema_failure")
        stages = row.get("failure_stages")
        _require(
            isinstance(stages, list)
            and stages == sorted(set(stages))
            and set(stages) <= ALLOWED_FAILURE_STAGES,
            f"{task_id}: invalid failure-stage attribution",
        )
        _require(
            row.get("mcp_schema_sha256") == mcp.get("schema_sha256"),
            f"{task_id}: task schema digest differs from report",
        )
    if require_schema_repair:
        _require(
            schema_failures > 0,
            "deterministic harness proof did not exercise bounded schema repair",
        )

    privacy = report.get("privacy")
    _require(isinstance(privacy, dict), "privacy contract is missing")
    _require(privacy.get("raw_prompts_persisted") is False, "raw prompts persisted")
    _require(
        privacy.get("raw_tool_results_persisted") is False,
        "raw tool results persisted",
    )
    _require(
        privacy.get("absolute_project_paths_persisted") is False,
        "absolute project paths persisted",
    )
    _require(privacy.get("event_hash_chain") is True, "event hash chain disabled")
    _validate_privacy(report)

    return {
        "protocol": PROTOCOL,
        "artifact_origin": origin,
        "version": artifact["version"],
        "source_commit": artifact["source_commit"],
        "schema_sha256": mcp["schema_sha256"],
        "provider_id": provider_id,
        "model": provider["model"],
        "task_count": task_count,
        "passed_tasks": report.get("passed_tasks"),
        "pass_rate": float(pass_rate),
        "tool_attempts": attempted_calls,
        "schema_failures": schema_failures,
        "claim_boundary": claim_boundary,
        "report_sha256": hashlib.sha256(canonical_json(report)).hexdigest(),
    }


def load_and_verify(
    path: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstalledMCPReportError(f"cannot read report: {exc}") from exc
    if not isinstance(report, dict):
        raise InstalledMCPReportError("report root must be an object")
    return verify_report(report, **kwargs)
