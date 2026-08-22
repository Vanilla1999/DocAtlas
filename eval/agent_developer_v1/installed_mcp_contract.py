from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import jsonschema
from jsonschema.validators import validator_for

import scripts.run_agent_developer_gate as oracle_gate


PROTOCOL = "installed-mcp-agent-v1"
EXPECTED_TOOLS = ("docs_status", "get_docs_context", "prepare_docs")
PROJECT_TOKEN = "$PROJECT_PATH"
REPORT_SCHEMA_VERSION = 1
MAX_RESULT_SUMMARY_BYTES = 12_000


class Planner(Protocol):
    provider_id: str
    model: str
    variant: str | None

    def choose(
        self,
        messages: list[dict[str, Any]],
        *,
        output_schema: dict[str, Any],
        purpose: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]: ...


class PlannerOutputError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        usage: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.usage = dict(usage or {})


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    origin: str
    distribution: str
    version: str
    artifact_filename: str
    artifact_sha256: str
    source_commit: str
    python_version: str
    cli_sha256: str
    public_release_verified: bool

    def to_report(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "distribution": self.distribution,
            "version": self.version,
            "artifact_filename": self.artifact_filename,
            "artifact_sha256": self.artifact_sha256,
            "source_commit": self.source_commit,
            "python_version": self.python_version,
            "cli_sha256": self.cli_sha256,
            "public_release_verified": self.public_release_verified,
        }


class ScriptedPlanner:
    provider_id = "scripted"
    model = "deterministic-script"
    variant = None

    def __init__(self, plans: dict[str, list[dict[str, Any]]]) -> None:
        self._plans = {
            str(task_id): [dict(action) for action in actions]
            for task_id, actions in plans.items()
        }
        self._positions: dict[str, int] = {}

    def choose(
        self,
        messages: list[dict[str, Any]],
        *,
        output_schema: dict[str, Any],
        purpose: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        del output_schema, purpose
        task_id = task_id_from_messages(messages)
        position = self._positions.get(task_id, 0)
        actions = self._plans.get(task_id) or []
        action = (
            dict(actions[position])
            if position < len(actions)
            else {
                "kind": "finish",
                "tool_name": "",
                "arguments": {},
                "reason": "script exhausted",
            }
        )
        self._positions[task_id] = position + 1
        return action, {
            "request_id": f"scripted-{task_id}-{position + 1}",
            "request_ids": {"scripted": f"{task_id}:{position + 1}"},
            "model": self.model,
            "variant": self.variant,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "request_payload_sha256": hashlib.sha256(
                json.dumps(messages, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }


def action_envelope_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "kind": {"type": "string", "enum": ["tool_call", "finish"]},
            "tool_name": {"type": "string"},
            "arguments": {"type": "object"},
            "reason": {"type": "string"},
        },
        "required": ["kind", "tool_name", "arguments", "reason"],
    }


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def task_id_from_messages(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("task_id"):
            return str(payload["task_id"])
    return "unknown"


class EventLog:
    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._previous = ""

    def add(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "seq": len(self._rows) + 1,
            "kind": str(kind),
            "previous_event_sha256": self._previous or None,
            "payload": payload,
        }
        digest = sha256_json(row)
        row["event_sha256"] = digest
        self._previous = digest
        self._rows.append(row)
        return row

    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]


def redact(value: Any, project: Path) -> Any:
    project_text = str(project)
    if isinstance(value, str):
        return value.replace(project_text, PROJECT_TOKEN)
    if isinstance(value, dict):
        return {str(key): redact(child, project) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(child, project) for child in value]
    return value


def materialize_project_token(value: Any, project: Path) -> Any:
    if isinstance(value, str):
        return value.replace(PROJECT_TOKEN, str(project))
    if isinstance(value, dict):
        return {
            str(key): materialize_project_token(child, project)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [materialize_project_token(child, project) for child in value]
    return value


def tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return dict(structured)
    content = getattr(result, "content", None)
    if not isinstance(content, list):
        return {}
    for item in content:
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def tool_catalog(response: Any) -> list[dict[str, Any]]:
    tools = []
    for tool in getattr(response, "tools", None) or []:
        schema = getattr(tool, "inputSchema", None)
        if not isinstance(schema, dict):
            schema = {}
        tools.append(
            {
                "name": str(getattr(tool, "name", "") or ""),
                "description": str(getattr(tool, "description", "") or ""),
                "input_schema": schema,
            }
        )
    tools.sort(key=lambda row: row["name"])
    return tools


def schema_digest(catalog: list[dict[str, Any]]) -> str:
    return sha256_json(catalog)


def validate_envelope(action: dict[str, Any]) -> None:
    jsonschema.validate(action, action_envelope_schema())
    kind = str(action["kind"])
    tool_name = str(action["tool_name"])
    arguments = action["arguments"]
    if kind == "finish":
        if tool_name or arguments:
            raise jsonschema.ValidationError(
                "finish requires empty tool_name and empty arguments"
            )
    elif not tool_name:
        raise jsonschema.ValidationError("tool_call requires tool_name")


def validate_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> None:
    tool = next((row for row in catalog if row["name"] == tool_name), None)
    if tool is None:
        raise jsonschema.ValidationError(f"unknown public tool: {tool_name}")
    schema = tool["input_schema"]
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(arguments)


def result_summary(payload: dict[str, Any], project: Path) -> dict[str, Any]:
    recommended = oracle_gate._recommended_action(payload)
    summary = {
        key: payload[key]
        for key in (
            "status",
            "kind",
            "support_status",
            "reason_code",
            "operational_reason_code",
            "answer_supported",
            "answer_available",
            "edit_ready",
            "requires_confirmation",
            "confirmation_reason",
            "module_candidates",
        )
        if key in payload
    }
    summary["sources"] = list(oracle_gate._source_paths(payload))
    if recommended:
        summary["next_action"] = {
            key: recommended[key]
            for key in (
                "tool",
                "action",
                "requires_confirmation",
                "auto_execute",
                "repeat_docs_context",
            )
            if key in recommended
        }
    redacted = redact(summary, project)
    if len(canonical_json(redacted)) > MAX_RESULT_SUMMARY_BYTES:
        return {
            "status": str(payload.get("status") or ""),
            "summary_truncated": True,
            "payload_sha256": sha256_json(redact(payload, project)),
        }
    return redacted


def safe_usage(usage: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "request_id",
        "request_ids",
        "session_id",
        "session_ids",
        "model",
        "variant",
        "reasoning_effort",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "estimated_input_tokens",
        "request_payload_sha256",
        "benchmark_contract_sha256",
        "model_output_valid",
        "model_output_error",
    }
    return {key: usage[key] for key in sorted(allowed) if key in usage}


def messages_for_task(
    task: dict[str, Any],
    catalog: list[dict[str, Any]],
    *,
    model_task_view: dict[str, Any],
) -> list[dict[str, Any]]:
    system = (
        "You are the evidence-planning component of a coding agent using an "
        "installed DocAtlas MCP server. The exact public tool catalog is embedded "
        "below. Choose one next action at a time. Use the literal $PROJECT_PATH "
        "for every project_path argument; the host replaces it with an isolated "
        "temporary path. Do not invent tools or arguments. Use finish only when "
        "the developer task is evidenced or the server has intentionally returned "
        "a reviewed recovery boundary. Do not request shell, source edits, web "
        "access, credentials, or hidden evaluator data."
    )
    tool_contract = {
        "project_path_token": PROJECT_TOKEN,
        "public_tools": catalog,
    }
    return [
        {
            "role": "system",
            "content": system
            + "\n\nPublic MCP tool catalog:\n"
            + json.dumps(tool_contract, ensure_ascii=False, sort_keys=True),
        },
        {
            "role": "user",
            "content": json.dumps(
                model_task_view,
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


def feedback_message(
    *,
    tool_name: str,
    payload: dict[str, Any],
    project: Path,
) -> dict[str, Any]:
    return {
        "role": "user",
        "content": (
            f"Observed installed MCP result from {tool_name}:\n"
            + json.dumps(
                result_summary(payload, project),
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
    }


def schema_error_message(exc: Exception) -> str:
    if isinstance(exc, jsonschema.ValidationError):
        path = ".".join(str(part) for part in exc.absolute_path)
        prefix = f"{path}: " if path else ""
        return (prefix + exc.message)[:600]
    return str(exc)[:600]


def model_action_record(
    tool_name: str,
    arguments: dict[str, Any],
    project: Path,
) -> dict[str, Any]:
    return {"action": tool_name, **redact(arguments, project)}


def benchmark_policy_error(
    tool_name: str,
    arguments: dict[str, Any],
) -> str | None:
    if tool_name != "prepare_docs":
        return None
    action = str(arguments.get("action") or "")
    if action != "sync_project_docs":
        return (
            "installed benchmark permits prepare_docs only for local "
            "sync_project_docs; network/dependency preparation remains a "
            "recovery boundary"
        )
    if arguments.get("with_vectors") not in {False, None}:
        return "installed benchmark requires with_vectors=false"
    return None
