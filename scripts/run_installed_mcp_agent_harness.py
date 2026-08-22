#!/usr/bin/env python3
"""Run one coding-agent trajectory against an installed DocAtlas Docs MCP.

The server under test is always installed into a fresh virtual environment.  The
provider-free ``scripted`` driver is an infrastructure positive control; a real
model is supplied through the bounded JSON command-driver protocol.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
import venv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SCHEMA_VERSION = 1
PROTOCOL = "installed_mcp_agent_v1"
EXPECTED_TOOLS = ("docs_status", "get_docs_context", "prepare_docs")
FAILURE_STAGES = {
    "adapter_protocol",
    "mcp_schema",
    "server_validation",
    "retrieval",
    "support",
    "recovery",
    "none",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users|tmp|var|private|workspace|work)/[^\s\"']+"),
    re.compile(r"(?i)(?<![A-Za-z0-9_])[A-Z]:\\[^\s\"']+"),
    re.compile(r"\\\\[^\s\\]+\\[^\s\"']+"),
)
SENSITIVE_KEY_RE = re.compile(r"(?i)(authorization|api[_-]?key|token|password|secret)")


class HarnessError(RuntimeError):
    """Raised when the installed-harness contract cannot be executed safely."""


@dataclass(frozen=True, slots=True)
class Case:
    case_id: str
    question: str
    mode: str
    files: dict[str, str]
    expected_source: str
    expected_contains: str
    max_tool_calls: int
    max_repairs: int


@dataclass(slots=True)
class DriverProvenance:
    driver: str
    provider: str
    model: str
    request_ids: list[str] = field(default_factory=list)
    usage: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RunState:
    trajectory: list[dict[str, Any]] = field(default_factory=list)
    ephemeral_history: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    repairs: int = 0
    first_divergence_stage: str = "none"
    first_divergence_reason: str = ""
    final_text: str = ""
    last_tool_payload: dict[str, Any] | None = None

    def divergence(self, stage: str, reason: str) -> None:
        if stage not in FAILURE_STAGES:
            raise HarnessError(f"unknown failure stage: {stage}")
        if self.first_divergence_stage == "none":
            self.first_divergence_stage = stage
            self.first_divergence_reason = reason[:240]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_checked(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        tail = completed.stdout[-4000:]
        raise HarnessError(
            f"command failed ({completed.returncode}): {command[0]}\n{tail}"
        )
    return completed


def safe_relative_path(value: Any) -> str:
    text = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or ".." in path.parts
        or (path.parts and path.parts[0].endswith(":"))
        or str(path) != text
    ):
        raise HarnessError(f"unsafe case file path: {value!r}")
    return text


def load_case(path: Path) -> Case:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"invalid case {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        raise HarnessError("case must be a schema_version=1 JSON object")
    required = {
        "schema_version",
        "case_id",
        "question",
        "mode",
        "files",
        "expected",
        "max_tool_calls",
        "max_repairs",
    }
    if set(raw) != required:
        raise HarnessError(
            f"case keys mismatch: expected={sorted(required)} actual={sorted(raw)}"
        )
    case_id = str(raw["case_id"] or "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,80}", case_id):
        raise HarnessError("case_id must be a bounded lowercase identifier")
    question = str(raw["question"] or "").strip()
    if not 1 <= len(question) <= 2000:
        raise HarnessError("question length must be 1..2000")
    mode = str(raw["mode"] or "")
    if mode not in {"project", "module", "auto"}:
        raise HarnessError("unsupported case mode")
    files_raw = raw["files"]
    if not isinstance(files_raw, dict) or not 1 <= len(files_raw) <= 20:
        raise HarnessError("files must contain 1..20 project files")
    files: dict[str, str] = {}
    for key, value in files_raw.items():
        relative = safe_relative_path(key)
        text = str(value)
        if len(text.encode("utf-8")) > 100_000:
            raise HarnessError(f"case file is too large: {relative}")
        files[relative] = text
    expected = raw["expected"]
    if not isinstance(expected, dict) or set(expected) != {"source_path", "contains"}:
        raise HarnessError("expected must contain source_path and contains")
    expected_source = safe_relative_path(expected["source_path"])
    expected_contains = str(expected["contains"] or "")
    if not expected_contains or len(expected_contains) > 1000:
        raise HarnessError("expected.contains must be bounded and non-empty")
    max_tool_calls = raw["max_tool_calls"]
    max_repairs = raw["max_repairs"]
    if not isinstance(max_tool_calls, int) or not 1 <= max_tool_calls <= 12:
        raise HarnessError("max_tool_calls must be 1..12")
    if not isinstance(max_repairs, int) or not 0 <= max_repairs <= 3:
        raise HarnessError("max_repairs must be 0..3")
    return Case(
        case_id=case_id,
        question=question,
        mode=mode,
        files=files,
        expected_source=expected_source,
        expected_contains=expected_contains,
        max_tool_calls=max_tool_calls,
        max_repairs=max_repairs,
    )


def venv_paths(root: Path) -> tuple[Path, Path, Path]:
    if os.name == "nt":
        bin_dir = root / "Scripts"
        return bin_dir / "python.exe", bin_dir / "pip.exe", bin_dir / "doc-atlas.exe"
    bin_dir = root / "bin"
    return bin_dir / "python", bin_dir / "pip", bin_dir / "doc-atlas"


def prepare_installed_package(
    *,
    work: Path,
    wheel: Path | None,
    package_spec: str | None,
) -> dict[str, Any]:
    if (wheel is None) == (package_spec is None):
        raise HarnessError("provide exactly one of --wheel or --package-spec")
    venv_root = work / "installed-venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
    python_exe, pip_exe, cli_exe = venv_paths(venv_root)
    if not python_exe.exists() or not pip_exe.exists():
        raise HarnessError("fresh virtual environment did not create Python/pip")

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    install_mode: str
    artifact: Path
    if wheel is not None:
        source = wheel.resolve()
        if not source.is_file() or source.suffix != ".whl":
            raise HarnessError(f"wheel does not exist: {source}")
        artifact = work / "package" / source.name
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(source.read_bytes())
        install_mode = "built_wheel"
    else:
        assert package_spec is not None
        if not re.fullmatch(r"doc-atlas==\d+\.\d+\.\d+", package_spec):
            raise HarnessError("--package-spec must be exact doc-atlas==MAJOR.MINOR.PATCH")
        download = work / "package"
        download.mkdir()
        run_checked(
            [
                str(pip_exe),
                "download",
                "--isolated",
                "--no-cache-dir",
                "--no-deps",
                "--only-binary=:all:",
                "--dest",
                str(download),
                package_spec,
            ],
            cwd=work,
            env=env,
        )
        wheels = sorted(download.glob("*.whl"))
        if len(wheels) != 1:
            raise HarnessError(
                f"expected one exact public wheel, found {[path.name for path in wheels]}"
            )
        artifact = wheels[0]
        install_mode = "public_package"

    run_checked(
        [
            str(pip_exe),
            "install",
            "--isolated",
            "--no-cache-dir",
            "--force-reinstall",
            str(artifact),
        ],
        cwd=work,
        env=env,
    )
    if not cli_exe.exists():
        raise HarnessError("installed wheel did not create the doc-atlas CLI")
    version_output = run_checked([str(cli_exe), "--version"], cwd=work, env=env).stdout.strip()
    match = re.fullmatch(r"doc-atlas (\d+\.\d+\.\d+)", version_output)
    if not match:
        raise HarnessError(f"unexpected installed version output: {version_output!r}")
    return {
        "install_mode": install_mode,
        "artifact_path": artifact,
        "artifact_filename": artifact.name,
        "artifact_sha256": sha256_file(artifact),
        "version": match.group(1),
        "cli": cli_exe,
        "python": python_exe,
        "venv": venv_root,
    }


def git_identity(root: Path) -> dict[str, Any]:
    try:
        commit = run_checked(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
        dirty = bool(run_checked(["git", "status", "--porcelain"], cwd=root).stdout.strip())
    except HarnessError:
        commit = "unknown"
        dirty = None
    return {"commit_sha": commit, "dirty": dirty}


def tool_schema(tool: Any) -> dict[str, Any]:
    input_schema = getattr(tool, "inputSchema", None)
    if input_schema is None:
        input_schema = getattr(tool, "input_schema", None)
    if not isinstance(input_schema, dict):
        input_schema = {}
    return {
        "name": str(getattr(tool, "name", "")),
        "description": str(getattr(tool, "description", "") or ""),
        "input_schema": input_schema,
    }


def tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", None) or []
    if content and hasattr(content[0], "text"):
        text = str(content[0].text)
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        return decoded if isinstance(decoded, dict) else {"value": decoded}
    return {"value": repr(result)[:1000]}


def bounded_result_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in (
        "status",
        "reason_code",
        "operational_status",
        "operational_reason_code",
        "support_status",
        "disposition",
        "source_search_status",
        "edit_ready",
        "requires_confirmation",
    ):
        value = payload.get(key)
        if isinstance(value, (str, bool, int, float)) or value is None:
            if key in payload:
                summary[key] = value
    sources: list[str] = []
    for collection_key in ("sources", "selected_sources", "context_pack"):
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            continue
        for item in collection[:12]:
            if not isinstance(item, dict):
                continue
            candidate = item.get("path_or_url") or item.get("path") or item.get("source")
            if not isinstance(candidate, str):
                continue
            normalized = candidate.replace("\\", "/")
            if not normalized.startswith("/") and not re.match(r"^[A-Za-z]:/", normalized):
                sources.append(normalized[:300])
    if sources:
        summary["relative_sources"] = sorted(set(sources))[:12]
    summary["payload_sha256"] = sha256_json(payload)
    return summary


def adapter_message(
    *,
    command: str,
    turn_payload: dict[str, Any],
    cwd: Path,
) -> dict[str, Any]:
    argv = shlex.split(command)
    if not argv:
        raise HarnessError("--driver-command is empty")
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=dict(os.environ),
        input=canonical_json(turn_payload),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    if completed.returncode != 0:
        raise HarnessError(
            f"driver command failed ({completed.returncode}): {completed.stderr[-2000:]}"
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError("driver command did not return one JSON object") from exc
    if not isinstance(value, dict):
        raise HarnessError("driver command response must be a JSON object")
    return value


def record_model_provenance(response: dict[str, Any], provenance: DriverProvenance) -> None:
    provider = response.get("provider")
    model = response.get("model")
    request_id = response.get("request_id")
    usage = response.get("usage")
    if isinstance(provider, str) and provider.strip():
        provenance.provider = provider.strip()[:120]
    if isinstance(model, str) and model.strip():
        provenance.model = model.strip()[:160]
    if isinstance(request_id, str) and request_id.strip():
        provenance.request_ids.append(request_id.strip()[:200])
    if isinstance(usage, dict):
        bounded = {
            key: value
            for key, value in usage.items()
            if key in {"input_tokens", "output_tokens", "total_tokens", "source"}
            and isinstance(value, (str, int, float, type(None)))
        }
        provenance.usage.append(bounded)


def scripted_response(turn: int, *, case: Case, project: Path, state: RunState) -> dict[str, Any]:
    request_id = f"scripted-turn-{turn}"
    metadata = {
        "provider": "scripted",
        "model": "deterministic-positive-control",
        "request_id": request_id,
        "usage": {"source": "not_applicable"},
    }
    if turn == 0:
        return {
            **metadata,
            "type": "tool_call",
            "name": "get_docs_context",
            "arguments": {
                "question": case.question,
                "project_path": str(project),
                "mode": case.mode,
            },
        }
    if turn == 1:
        return {
            **metadata,
            "type": "tool_call",
            "name": "prepare_docs",
            "arguments": {
                "action": "sync_project_docs",
                "project_path": str(project),
                "with_vectors": False,
            },
        }
    if turn == 2:
        return {
            **metadata,
            "type": "tool_call",
            "name": "get_docs_context",
            "arguments": {
                "question": case.question,
                "project_path": str(project),
                "mode": case.mode,
            },
        }
    evidence = canonical_json(state.last_tool_payload or {})
    final = case.expected_contains if case.expected_contains in evidence else "evidence missing"
    return {**metadata, "type": "final", "text": final}


def validate_driver_response(value: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    message_type = value.get("type")
    if message_type == "tool_call":
        name = value.get("name")
        arguments = value.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise HarnessError("tool_call requires string name and object arguments")
        return "tool_call", {"name": name, "arguments": arguments}
    if message_type == "final":
        text = value.get("text")
        if not isinstance(text, str) or len(text) > 20_000:
            raise HarnessError("final requires bounded string text")
        return "final", {"text": text}
    raise HarnessError("driver response type must be tool_call or final")


def evidence_present(payload: dict[str, Any] | None, case: Case) -> tuple[bool, bool]:
    rendered = canonical_json(payload or {})
    source = case.expected_source in rendered
    marker = case.expected_contains in rendered
    return source, marker


def report_privacy_scan(report: dict[str, Any], *, secret_values: Sequence[str]) -> None:
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)
    lowered = rendered.lower()
    forbidden_fields = ("raw_prompt", "raw_result", "raw_environment", "authorization")
    for field in forbidden_fields:
        if field in lowered:
            raise HarnessError(f"privacy scan rejected forbidden field: {field}")
    for pattern in ABSOLUTE_PATH_PATTERNS:
        match = pattern.search(rendered)
        if match:
            raise HarnessError(f"privacy scan found absolute path: {match.group(0)[:160]}")
    for value in secret_values:
        if len(value) >= 8 and value in rendered:
            raise HarnessError("privacy scan found a credential value")
    if any(SENSITIVE_KEY_RE.fullmatch(str(key)) for key in report):
        raise HarnessError("privacy scan found a top-level sensitive key")


def secret_environment_values() -> list[str]:
    values: list[str] = []
    for key, value in os.environ.items():
        if value and SENSITIVE_KEY_RE.search(key):
            values.append(value)
    return values


async def execute_case(
    *,
    root: Path,
    work: Path,
    package: dict[str, Any],
    case: Case,
    driver: str,
    driver_command: str | None,
    provider: str,
    model: str,
) -> dict[str, Any]:
    project = work / "project"
    project.mkdir()
    for relative, text in case.files.items():
        target = project / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    user_home = work / "user-home"
    docatlas_home = work / "docatlas-home"
    user_home.mkdir()
    docatlas_home.mkdir()
    child_env = dict(os.environ)
    for key in list(child_env):
        if key in {"PYTHONPATH", "DOCMANCER_HOME"}:
            child_env.pop(key, None)
    child_env.update(
        {
            "HOME": str(user_home),
            "USERPROFILE": str(user_home),
            "DOCATLAS_HOME": str(docatlas_home),
            "NO_PROXY": "*",
            "PIP_NO_CACHE_DIR": "1",
        }
    )

    params = StdioServerParameters(
        command=str(package["cli"]),
        args=["mcp", "docs-serve"],
        env=child_env,
        cwd=str(work),
    )
    state = RunState()
    provenance = DriverProvenance(
        driver=driver,
        provider=("scripted" if driver == "scripted" else provider),
        model=("deterministic-positive-control" if driver == "scripted" else model),
    )
    tool_rows: list[dict[str, Any]] = []

    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            listed = await session.list_tools()
            schemas = sorted((tool_schema(tool) for tool in listed.tools), key=lambda row: row["name"])
            names = tuple(row["name"] for row in schemas)
            if names != EXPECTED_TOOLS:
                raise HarnessError(
                    f"installed MCP tool inventory mismatch: expected={EXPECTED_TOOLS} actual={names}"
                )
            schema_map = {row["name"]: row["input_schema"] for row in schemas}

            max_turns = case.max_tool_calls + case.max_repairs + 3
            for turn in range(max_turns):
                turn_payload = {
                    "protocol": PROTOCOL,
                    "schema_version": SCHEMA_VERSION,
                    "turn": turn,
                    "case": {
                        "case_id": case.case_id,
                        "question": case.question,
                        "mode": case.mode,
                        "max_tool_calls": case.max_tool_calls,
                        "max_repairs": case.max_repairs,
                    },
                    "tools": schemas,
                    "history": state.ephemeral_history[-12:],
                }
                try:
                    response = (
                        scripted_response(turn, case=case, project=project, state=state)
                        if driver == "scripted"
                        else adapter_message(
                            command=str(driver_command),
                            turn_payload=turn_payload,
                            cwd=root,
                        )
                    )
                    record_model_provenance(response, provenance)
                    message_type, message = validate_driver_response(response)
                except HarnessError as exc:
                    state.divergence("adapter_protocol", str(exc))
                    if state.repairs >= case.max_repairs:
                        break
                    state.repairs += 1
                    state.ephemeral_history.append(
                        {
                            "type": "repair",
                            "stage": "adapter_protocol",
                            "message": str(exc)[:500],
                        }
                    )
                    continue

                if message_type == "final":
                    state.final_text = message["text"]
                    state.ephemeral_history.append(
                        {"type": "final", "text": message["text"][:2000]}
                    )
                    break

                name = message["name"]
                arguments = message["arguments"]
                state.tool_calls += 1
                attempt: dict[str, Any] = {
                    "attempt": state.tool_calls,
                    "turn": turn,
                    "tool": name[:120],
                    "arguments_sha256": sha256_json(arguments),
                    "schema_valid": False,
                    "server_ok": False,
                    "repair_count_before": state.repairs,
                }
                if state.tool_calls > case.max_tool_calls:
                    attempt["failure_stage"] = "recovery"
                    attempt["reason"] = "tool_call_budget_exceeded"
                    state.trajectory.append(attempt)
                    state.divergence("recovery", "tool call budget exceeded")
                    break
                schema = schema_map.get(name)
                if schema is None:
                    errors = [f"unknown installed tool: {name}"]
                else:
                    errors = [
                        error.message
                        for error in Draft202012Validator(schema).iter_errors(arguments)
                    ]
                if errors:
                    attempt["failure_stage"] = "mcp_schema"
                    attempt["reason"] = "; ".join(errors)[:500]
                    state.trajectory.append(attempt)
                    state.divergence("mcp_schema", attempt["reason"])
                    if state.repairs >= case.max_repairs:
                        break
                    state.repairs += 1
                    state.ephemeral_history.append(
                        {
                            "type": "tool_error",
                            "stage": "mcp_schema",
                            "tool": name,
                            "message": attempt["reason"],
                        }
                    )
                    continue
                attempt["schema_valid"] = True

                try:
                    result = await session.call_tool(name, arguments)
                    payload = tool_payload(result)
                    is_error = bool(getattr(result, "isError", False))
                except Exception as exc:  # MCP/client boundary must be recorded.
                    payload = {"exception_type": type(exc).__name__}
                    is_error = True
                attempt["result_sha256"] = sha256_json(payload)
                summary = bounded_result_summary(payload)
                attempt["result_summary"] = summary
                if is_error or payload.get("status") in {"error", "failed"}:
                    attempt["failure_stage"] = "server_validation"
                    attempt["reason"] = str(
                        payload.get("reason_code")
                        or payload.get("message")
                        or "server returned an error"
                    )[:500]
                    state.trajectory.append(attempt)
                    state.divergence("server_validation", attempt["reason"])
                    if state.repairs >= case.max_repairs:
                        break
                    state.repairs += 1
                    state.ephemeral_history.append(
                        {
                            "type": "tool_error",
                            "stage": "server_validation",
                            "tool": name,
                            "summary": summary,
                        }
                    )
                    continue
                attempt["server_ok"] = True
                attempt["failure_stage"] = "none"
                attempt["reason"] = ""
                state.trajectory.append(attempt)
                state.last_tool_payload = payload
                state.ephemeral_history.append(
                    {
                        "type": "tool_result",
                        "tool": name,
                        "arguments": arguments,
                        "result": payload,
                    }
                )

    source_found, marker_found = evidence_present(state.last_tool_payload, case)
    final_contains_marker = case.expected_contains in state.final_text
    success = bool(source_found and marker_found and final_contains_marker)
    if not success and state.first_divergence_stage == "none":
        if not source_found or not marker_found:
            state.divergence("retrieval", "expected source/marker not present in tool result")
        else:
            state.divergence("support", "final response did not preserve supported marker")

    source = git_identity(root)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "package": {
            "distribution": "doc-atlas",
            "install_mode": package["install_mode"],
            "version": package["version"],
            "artifact_filename": package["artifact_filename"],
            "artifact_sha256": package["artifact_sha256"],
            "server_from_fresh_venv": True,
            "editable_server_import": False,
        },
        "mcp": {
            "transport": "stdio",
            "server_command": "doc-atlas mcp docs-serve",
            "tool_names": list(names),
            "tool_count": len(names),
            "tool_schemas_sha256": sha256_json(schemas),
        },
        "model": {
            "driver": provenance.driver,
            "provider": provenance.provider,
            "model": provenance.model,
            "request_ids": provenance.request_ids,
            "usage": provenance.usage,
            "real_model": provenance.driver == "command",
        },
        "case": {
            "case_id": case.case_id,
            "question_sha256": sha256_bytes(case.question.encode("utf-8")),
            "expected_source": case.expected_source,
            "expected_marker_sha256": sha256_bytes(case.expected_contains.encode("utf-8")),
            "max_tool_calls": case.max_tool_calls,
            "max_repairs": case.max_repairs,
        },
        "trajectory": state.trajectory,
        "budgets": {
            "tool_calls_used": state.tool_calls,
            "repairs_used": state.repairs,
        },
        "first_divergence": {
            "stage": state.first_divergence_stage,
            "reason": state.first_divergence_reason,
        },
        "outcome": {
            "success": success,
            "expected_source_found": source_found,
            "expected_marker_found": marker_found,
            "final_preserved_marker": final_contains_marker,
        },
        "privacy": {
            "raw_prompt_stored": False,
            "raw_tool_result_stored": False,
            "raw_environment_stored": False,
            "absolute_path_scan": "pass",
            "credential_value_scan": "pass",
        },
        "claim_boundary": {
            "agent_truth_closed": False,
            "public_release_proven": package["install_mode"] == "public_package",
            "scripted_positive_control": driver == "scripted",
        },
    }
    report_privacy_scan(report, secret_values=secret_environment_values())
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--wheel", type=Path)
    source.add_argument("--package-spec")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--driver", choices=("scripted", "command"), default="scripted")
    parser.add_argument("--driver-command")
    parser.add_argument("--provider", default="unspecified")
    parser.add_argument("--model", default="unspecified")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.driver == "command" and not args.driver_command:
        raise SystemExit("--driver=command requires --driver-command")
    if args.driver == "scripted" and args.driver_command:
        raise SystemExit("--driver-command is only valid with --driver=command")
    root = Path(__file__).resolve().parents[1]
    case = load_case(args.case.resolve())
    with tempfile.TemporaryDirectory(prefix="docatlas-installed-mcp-agent-") as raw:
        work = Path(raw)
        package = prepare_installed_package(
            work=work,
            wheel=args.wheel,
            package_spec=args.package_spec,
        )
        report = asyncio.run(
            execute_case(
                root=root,
                work=work,
                package=package,
                case=case,
                driver=args.driver,
                driver_command=args.driver_command,
                provider=args.provider,
                model=args.model,
            )
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Installed MCP Agent v1: {'PASS' if report['outcome']['success'] else 'FAIL'} "
        f"case={case.case_id} mode={report['package']['install_mode']} "
        f"schema={report['mcp']['tool_schemas_sha256']}"
    )
    return 0 if report["outcome"]["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
