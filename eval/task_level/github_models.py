from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from docmancer.docs.application.action_packet import build_action_packet

from .isolated_delivery import (
    DelegationEnvelope,
    HostEvidenceSnapshot,
    IsolatedDeliveryError,
    IsolatedWorkerCapabilities,
    IsolatedWorkerOutput,
    WorkerUsage,
)
from .runners.base import AgentRunOutput, AgentRunRequest, RunnerCapabilities


GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_GITHUB_MODEL = "openai/gpt-4.1-mini"
_RUNNER_VERSION = "github-models-controlled-agent-v1"
_WORKER_PROMPT_REVISION = "task33c-evidence-selector-v1"
_MIN_REQUEST_INTERVAL_SECONDS = 4.2
_REQUEST_RATE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


@dataclass(frozen=True)
class GitHubModelsCompletion:
    content: str
    model: str
    request_id: str
    request_ids: dict[str, str]
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    raw_usage: dict[str, Any]


class GitHubModelsClient:
    """Small, auditable client for GitHub Models structured completions."""

    def __init__(self, token: str, *, endpoint: str = GITHUB_MODELS_ENDPOINT) -> None:
        if not token.strip():
            raise ValueError("GITHUB_TOKEN is required")
        self._token = token
        self.endpoint = endpoint

    def complete_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        timeout_seconds: float,
        max_tokens: int,
    ) -> tuple[dict[str, Any], GitHubModelsCompletion]:
        if timeout_seconds <= 0:
            raise TimeoutError("GitHub Models request deadline expired")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        _pace_github_models_request()
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer " + self._token,
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(4_000_001)
                if len(body) > 4_000_000:
                    raise RuntimeError("GitHub Models response exceeded 4 MB")
                request_ids = {
                    name: value
                    for name in ("x-github-request-id", "apim-request-id", "x-ms-request-id")
                    if (value := response.headers.get(name))
                }
        except urllib.error.HTTPError as exc:
            detail = exc.read(2_000).decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub Models HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub Models transport failure: {exc.reason}") from exc

        try:
            result = json.loads(body.decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            usage = result["usage"]
            value = json.loads(content)
        except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("GitHub Models returned an invalid structured completion") from exc
        if not isinstance(value, dict) or not isinstance(usage, dict):
            raise RuntimeError("GitHub Models structured completion contract failed")
        input_tokens = _strict_nonnegative_int(usage.get("prompt_tokens"), "prompt_tokens")
        output_tokens = _strict_nonnegative_int(usage.get("completion_tokens"), "completion_tokens")
        total_tokens = _strict_nonnegative_int(usage.get("total_tokens"), "total_tokens")
        if total_tokens != input_tokens + output_tokens:
            raise RuntimeError("GitHub Models usage totals are inconsistent")
        details = usage.get("completion_tokens_details")
        reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
        if reasoning is not None:
            reasoning = _strict_nonnegative_int(reasoning, "reasoning_tokens")
        if not request_ids:
            raise RuntimeError("GitHub Models response omitted provider request identity")
        request_id = request_ids.get("x-github-request-id") or request_ids.get("apim-request-id") or next(iter(request_ids.values()))
        completion = GitHubModelsCompletion(
            content=content,
            model=str(result.get("model") or model),
            request_id=request_id,
            request_ids=request_ids,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning,
            raw_usage=dict(usage),
        )
        return value, completion


@dataclass(frozen=True)
class GitHubModelsIsolatedWorker:
    """Tool-less hosted compressor over one immutable host evidence snapshot."""

    token: str
    model: str = DEFAULT_GITHUB_MODEL
    endpoint: str = GITHUB_MODELS_ENDPOINT
    compressor_identity: str = "github-models-task33c-selector-v1"
    usage_verifier_identity: str = "github-models-response-headers-and-usage-v1"

    @property
    def capability_evidence(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": "verified" if bool(self.token.strip()) else "unavailable",
            "boundary": "tool-less hosted inference request",
            "fresh_context": "one stateless request with no conversation reuse",
            "documentation_access": "only the serialized host-owned evidence snapshot",
            "tools": [],
            "network_tools": [],
            "local_process_execution": False,
            "recursive_delegation": False,
            "hard_timeout": "host urllib deadline plus broker wall-clock enforcement",
            "token_accounting": "provider response usage bound to provider request headers",
        }

    @property
    def capabilities(self) -> IsolatedWorkerCapabilities:
        available = self.capability_evidence["status"] == "verified"
        return IsolatedWorkerCapabilities(
            fresh_context=available,
            read_only_documentation=available,
            recursive_delegation_disabled=available,
            hard_timeout=available,
            token_accounting=available,
            host_owned_evidence=available,
            network_disabled=available,
            descendant_containment=available,
        )

    @property
    def command_fingerprint(self) -> str:
        return _json_sha256({
            "endpoint": self.endpoint,
            "model": self.model,
            "prompt_revision": _WORKER_PROMPT_REVISION,
            "response_schema": _evidence_selection_schema(),
        })

    @property
    def sandbox_identity(self) -> str:
        return "github-models:tool-less-hosted-inference-v1"

    def run(
        self,
        envelope: DelegationEnvelope,
        evidence: HostEvidenceSnapshot,
        *,
        timeout_seconds: int,
    ) -> IsolatedWorkerOutput:
        envelope.validate()
        evidence.validate(envelope)
        if not self.capabilities.verified:
            raise IsolatedDeliveryError("github_models_worker_unavailable")
        indexed = [
            {"index": index, "evidence": _compact_worker_evidence(item)}
            for index, item in enumerate(evidence.evidence_items)
        ]
        system = (
            "You are a one-shot evidence compressor. You have no tools, filesystem, network, "
            "or delegation. Select 3 to 6 evidence items that are most useful for implementing "
            "the objective. Prefer canonical project architecture and source evidence spanning "
            "all affected modules. Return only the required JSON object."
        )
        user = json.dumps({
            "prompt_revision": _WORKER_PROMPT_REVISION,
            "objective": envelope.task_objective,
            "required_evidence_categories": list(envelope.required_evidence_categories),
            "evidence_fingerprint": evidence.fingerprint,
            "evidence": indexed,
        }, ensure_ascii=False, sort_keys=True)
        started = time.monotonic()
        try:
            selection, completion = GitHubModelsClient(self.token, endpoint=self.endpoint).complete_json(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                schema_name="task33c_evidence_selection",
                schema=_evidence_selection_schema(),
                timeout_seconds=timeout_seconds,
                max_tokens=256,
            )
        except Exception as exc:
            raise IsolatedDeliveryError("github_models_worker_request_failed") from exc
        indices = selection.get("selected_indices")
        if (
            not isinstance(indices, list)
            or not 3 <= len(indices) <= min(6, len(evidence.evidence_items))
            or any(isinstance(index, bool) or not isinstance(index, int) for index in indices)
            or len(set(indices)) != len(indices)
            or any(index < 0 or index >= len(evidence.evidence_items) for index in indices)
        ):
            raise IsolatedDeliveryError("github_models_worker_invalid_evidence_selection")
        selected = tuple(evidence.evidence_items[index] for index in indices)
        packet = build_action_packet(
            question=envelope.task_objective,
            context_pack=selected,
            trust_contract=evidence.trust_contract,
            max_tokens=envelope.token_budget,
            retrieval_issues=evidence.retrieval_issues,
        )
        proof = {
            "schema_version": 1,
            "provider": "github-models",
            "model": completion.model,
            "request_id": completion.request_id,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "reasoning_tokens": completion.reasoning_tokens,
            "request_ids": completion.request_ids,
            "usage": completion.raw_usage,
            "evidence_fingerprint": evidence.fingerprint,
            "selected_indices": indices,
        }
        usage = WorkerUsage(
            provider="github-models",
            model=completion.model,
            request_id=completion.request_id,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            reasoning_tokens=completion.reasoning_tokens,
            proof=proof,
        )
        return IsolatedWorkerOutput(
            packet=packet,
            usage=usage,
            wall_time_seconds=round(time.monotonic() - started, 6),
        )


class GitHubModelsRunner:
    """Hard-turn controlled coding loop with a closed, host-owned tool surface."""

    runner_id = "github-models"
    hard_turn_limit_enforced = True

    def __init__(self, token: str, *, endpoint: str = GITHUB_MODELS_ENDPOINT) -> None:
        self._token = token
        self._endpoint = endpoint

    def verify(self) -> RunnerCapabilities:
        available = bool(self._token.strip())
        return RunnerCapabilities(
            runner_id=self.runner_id,
            version=_RUNNER_VERSION,
            structured_trajectory=available,
            patch_capture=available,
            tool_isolation=available,
            mcp_isolation=available,
            shell_network_isolation=available,
            token_usage=available,
            independent_process=available,
            verified=available,
            hard_turn_limit=True,
            verification_notes=[
                "Each model turn is a stateless GitHub Models request in a host-controlled loop.",
                "The runner exposes only bounded repository reads, exact text replacement, local tests, and condition-scoped DocAtlas retrieval.",
                "No arbitrary shell, network, MCP, recursive-agent, or generated-file editing tool is exposed.",
                "The Python loop enforces the requested maximum number of model turns and a monotonic wall-clock deadline.",
                "Provider token usage and request IDs are persisted per turn without persisting the bearer token.",
            ],
        )

    def run(self, request: AgentRunRequest) -> AgentRunOutput:
        request.output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = request.output_dir / "stdout.log"
        stderr_path = request.output_dir / "stderr.log"
        trajectory_path = request.output_dir / "trajectory.normalized.json"
        usage_path = request.output_dir / "github_models_usage.json"
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        deadline = started + request.timeout_seconds
        model = _normalize_model(request.model)
        inventory = _list_repository_files(request.workspace)
        base_messages: list[dict[str, str]] = [
            {"role": "system", "content": _runner_system_prompt(request)},
            {
                "role": "user",
                "content": request.prompt + "\n\nExact repository file inventory:\n" + inventory,
            },
        ]
        recent_messages: list[dict[str, str]] = []
        events: list[dict[str, Any]] = []
        usage_rows: list[dict[str, Any]] = []
        stdout_rows: list[str] = []
        stderr_rows: list[str] = []
        status = "max_turns_exhausted"
        exit_code = 2
        client = GitHubModelsClient(self._token, endpoint=self._endpoint)
        read_paths: set[str] = set()

        for turn in range(1, request.max_turns + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                status, exit_code = "timeout", 124
                break
            try:
                action, completion = client.complete_json(
                    model=model,
                    messages=[*base_messages, *recent_messages[-6:]],
                    schema_name="controlled_agent_action",
                    schema=_agent_action_schema(_docatlas_allowed(request.condition_id)),
                    timeout_seconds=min(remaining, 90),
                    max_tokens=900,
                )
            except Exception as exc:
                stderr_rows.append(f"turn {turn}: {exc.__class__.__name__}: {exc}")
                status, exit_code = "runner_failed", 1
                break
            usage_rows.append({
                "turn": turn,
                "provider": "github-models",
                "model": completion.model,
                "request_id": completion.request_id,
                "request_ids": completion.request_ids,
                "usage": completion.raw_usage,
            })
            stdout_rows.append(json.dumps({"turn": turn, "action": action}, ensure_ascii=False, sort_keys=True))
            tool = action.get("tool")
            if tool == "finish":
                summary = str(action.get("summary") or "")[:4_000]
                events.append(_event(len(events) + 1, "assistant", "", {}, summary))
                status, exit_code = "completed", 0
                break
            result = _execute_agent_tool(request, action, read_paths=read_paths)
            event = _event(
                len(events) + 1,
                "tool_call",
                _trajectory_tool_name(str(tool), result),
                _trajectory_arguments(action),
                result,
            )
            events.append(event)
            recent_messages.append({
                "role": "assistant",
                "content": json.dumps(_compact_action_history(action), ensure_ascii=False, sort_keys=True),
            })
            recent_messages.append({
                "role": "user",
                "content": "Observed tool output:\n" + result[:6_000],
            })

        finished_at = datetime.now(timezone.utc).isoformat()
        stdout_path.write_text("\n".join(stdout_rows) + ("\n" if stdout_rows else ""), encoding="utf-8")
        stderr_path.write_text("\n".join(stderr_rows) + ("\n" if stderr_rows else ""), encoding="utf-8")
        trajectory_path.write_text(json.dumps(events, indent=2, sort_keys=True), encoding="utf-8")
        usage_path.write_text(json.dumps({
            "schema_version": 1,
            "provider": "github-models",
            "model": model,
            "turns": usage_rows,
        }, indent=2, sort_keys=True), encoding="utf-8")
        input_tokens = sum(row["usage"]["prompt_tokens"] for row in usage_rows)
        output_tokens = sum(row["usage"]["completion_tokens"] for row in usage_rows)
        cached_input_tokens = sum(
            value
            for row in usage_rows
            if isinstance(row["usage"].get("prompt_tokens_details"), dict)
            for value in [row["usage"]["prompt_tokens_details"].get("cached_tokens")]
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        )
        reasoning_values = [
            row["usage"].get("completion_tokens_details", {}).get("reasoning_tokens")
            for row in usage_rows
            if isinstance(row["usage"].get("completion_tokens_details"), dict)
        ]
        reasoning_tokens = sum(value for value in reasoning_values if isinstance(value, int) and not isinstance(value, bool))
        return AgentRunOutput(
            status=status,
            exit_code=exit_code,
            started_at=started_at,
            finished_at=finished_at,
            wall_time_seconds=round(time.monotonic() - started, 6),
            raw_stdout_path=str(stdout_path),
            raw_stderr_path=str(stderr_path),
            trajectory_path=str(trajectory_path),
            patch_path=None,
            tool_calls=[event for event in events if event["event_type"] == "tool_call"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            runner_version=_RUNNER_VERSION,
            max_turns_enforced=True,
            token_usage={
                "cached_input_tokens": cached_input_tokens,
                "reasoning_tokens": reasoning_tokens,
                "completed_turn_events": len(usage_rows),
            },
            notes=["GitHub Models controlled tool loop; no arbitrary shell or network tools exposed."],
        )


def create_github_models_runner() -> GitHubModelsRunner:
    return GitHubModelsRunner(os.environ.get("GITHUB_TOKEN", ""))


def create_github_models_worker() -> GitHubModelsIsolatedWorker:
    return GitHubModelsIsolatedWorker(
        os.environ.get("GITHUB_TOKEN", ""),
        model=os.environ.get("TASK33C_GITHUB_MODEL", DEFAULT_GITHUB_MODEL),
    )


def _evidence_selection_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["selected_indices"],
        "properties": {
            "selected_indices": {
                "type": "array",
                "minItems": 3,
                "maxItems": 6,
                "uniqueItems": True,
                "items": {"type": "integer", "minimum": 0},
            },
        },
    }


def _agent_action_schema(docatlas_allowed: bool) -> dict[str, Any]:
    tools = ["list_files", "read_file", "search", "replace_text", "run_tests", "finish"]
    if docatlas_allowed:
        tools.insert(-1, "get_docs_context")
    nullable_string = {"type": ["string", "null"]}
    nullable_int = {"type": ["integer", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["tool", "path", "query", "old", "new", "start_line", "end_line", "summary"],
        "properties": {
            "tool": {"type": "string", "enum": tools},
            "path": nullable_string,
            "query": nullable_string,
            "old": nullable_string,
            "new": nullable_string,
            "start_line": nullable_int,
            "end_line": nullable_int,
            "summary": nullable_string,
        },
    }


def _runner_system_prompt(request: AgentRunRequest) -> str:
    tools = (
        "list_files; read_file(path,start_line,end_line); search(query,path); "
        "replace_text(path,old,new); run_tests; finish(summary)"
    )
    if _docatlas_allowed(request.condition_id):
        tools += "; get_docs_context(query)"
    return (
        "You are a controlled coding agent. Take exactly one action per turn using the JSON schema. "
        f"Available actions: {tools}. Inspect before editing, make the smallest source-code fix, run tests, "
        "then finish. Never edit tests, documentation, lockfiles, generated files, or files outside the repository. "
        "You have no internet or arbitrary shell. "
        "The user message contains the exact repository inventory; never invent a path outside it. "
        "You must read a source file before editing it. For exact replacement, old must match the current file "
        "byte-for-byte. If replacement fails, read the file again and do not repeat the same failed action. "
        f"The hard turn limit is {request.max_turns}."
    )


def _execute_agent_tool(
    request: AgentRunRequest,
    action: dict[str, Any],
    *,
    read_paths: set[str] | None = None,
) -> str:
    read_paths = read_paths if read_paths is not None else set()
    tool = action.get("tool")
    try:
        if tool == "list_files":
            return _list_repository_files(request.workspace)
        if tool == "read_file":
            path = _safe_path(request.workspace, action.get("path"), write=False)
            relative = path.relative_to(request.workspace.resolve()).as_posix()
            read_paths.add(relative)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            start = max(1, action.get("start_line") if isinstance(action.get("start_line"), int) else 1)
            end = min(len(lines), action.get("end_line") if isinstance(action.get("end_line"), int) else start + 300)
            return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))[:6_000]
        if tool == "search":
            query = action.get("query")
            if not isinstance(query, str) or not query or len(query) > 300:
                return "ERROR: invalid search query"
            base = _safe_path(request.workspace, action.get("path") or ".", write=False)
            paths = [base] if base.is_file() else sorted(path for path in base.rglob("*") if path.is_file())
            terms = [term.lower() for term in query.split() if len(term) >= 3]
            rows: list[tuple[int, str]] = []
            for path in paths:
                if ".git" in path.parts or "__pycache__" in path.parts:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    lowered = line.lower()
                    score = sum(term in lowered for term in terms) if terms else int(query.lower() in lowered)
                    if score:
                        rows.append((score, f"{path.relative_to(request.workspace).as_posix()}:{number}:{line}"))
            ranked = [row for _score, row in sorted(rows, key=lambda item: (-item[0], item[1]))[:80]]
            return "\n".join(ranked)[:6_000] or "NO MATCHES"
        if tool == "replace_text":
            path = _safe_path(request.workspace, action.get("path"), write=True)
            relative = path.relative_to(request.workspace.resolve()).as_posix()
            if relative not in read_paths:
                return "ERROR: read_file must successfully inspect this exact path before replace_text"
            old, new = action.get("old"), action.get("new")
            if not isinstance(old, str) or not old or not isinstance(new, str):
                return "ERROR: old and new must be strings and old must be non-empty"
            if len(old) > 50_000 or len(new) > 50_000:
                return "ERROR: replacement exceeds 50 KB"
            text = path.read_text(encoding="utf-8")
            count = text.count(old)
            if count != 1:
                lines = text.splitlines()
                start = max(1, action.get("start_line") if isinstance(action.get("start_line"), int) else 1)
                end = min(len(lines), action.get("end_line") if isinstance(action.get("end_line"), int) else start + 80)
                excerpt = "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))
                return (
                    f"ERROR: old text matched {count} times; expected exactly once. "
                    "Do not repeat this action. Current numbered excerpt:\n" + excerpt[:5_000]
                )
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            return f"UPDATED {path.relative_to(request.workspace).as_posix()}"
        if tool == "run_tests":
            if (request.workspace / "test_calc.py").is_file():
                command = ["python", "-m", "pytest", "test_calc.py", "-q"]
            elif (request.workspace / "tests/test_browser_permission_gate.py").is_file():
                command = ["uv", "run", "--offline", "pytest", "tests/test_browser_permission_gate.py", "-q"]
            else:
                command = ["python", "-m", "pytest", "-q"]
            completed = subprocess.run(
                command,
                cwd=request.workspace,
                env={**os.environ, **request.environment, "DOCMANCER_OFFLINE": "1"},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=min(180, request.timeout_seconds),
                check=False,
            )
            return f"exit_code={completed.returncode}\n{completed.stdout[-18_000:]}"
        if tool == "get_docs_context" and _docatlas_allowed(request.condition_id):
            query = action.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > 1_000:
                return "ERROR: invalid documentation query"
            from docmancer.docs.service import LibraryDocsService

            with _activated_environment(request.environment):
                result = LibraryDocsService().get_docs_context(
                    query,
                    project_path=str(request.workspace),
                    ecosystem=None,
                    mode="project",
                    response_style="snippet-first",
                    allow_network=False,
                    allow_latest_fallback=False,
                    tokens=2_500,
                    limit=6,
                )
            return json.dumps(_jsonable(result), ensure_ascii=False, sort_keys=True)[:6_000]
        return "ERROR: unavailable action"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return f"ERROR: {exc.__class__.__name__}: {str(exc)[:1_000]}"
    except Exception as exc:
        return f"ERROR: tool failed closed: {exc.__class__.__name__}: {str(exc)[:1_000]}"


def _safe_path(root: Path, value: Any, *, write: bool) -> Path:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("invalid repository path")
    candidate = (root / value).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("path escapes repository")
    relative = candidate.relative_to(resolved_root)
    if ".git" in relative.parts:
        raise ValueError("git metadata is not exposed")
    if write and (
        relative.parts[:1] in (("tests",), ("docs",))
        or candidate.name in {"README.md", "pubspec.lock", "pyproject.toml"}
        or candidate.name.endswith((".freezed.dart", ".g.dart"))
    ):
        raise ValueError("editing this path is forbidden by runner policy")
    if not candidate.exists() or not candidate.is_file() and value != ".":
        raise ValueError("path does not exist")
    return candidate


def _event(sequence: int, event_type: str, tool_name: str, arguments: dict[str, Any], result: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "tool_name": tool_name,
        "arguments": arguments,
        "result_summary": result[:4_000],
    }


def _trajectory_tool_name(tool: str, result: str) -> str:
    if tool == "replace_text" and not result.startswith("UPDATED "):
        return "Repo.replace_text_rejected"
    return {
        "replace_text": "Edit.replace_text",
        "run_tests": "Bash.pytest",
        "get_docs_context": "get_docs_context",
    }.get(tool, f"Repo.{tool}")


def _trajectory_arguments(action: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in action.items() if key != "summary" and value is not None}
    if action.get("tool") == "get_docs_context":
        result.update({"server": "docmancer-docs", "tool": "get_docs_context"})
    if action.get("tool") == "run_tests":
        result["command"] = "uv run --offline pytest"
    return result


def _docatlas_allowed(condition_id: str) -> bool:
    return condition_id in {
        "docatlas_tool_optional",
        "docatlas_tool_recommended",
        "docatlas_tool_required_once",
        "docatlas_tool_visibility_canary",
    }


def _normalize_model(model: str) -> str:
    return model if "/" in model else DEFAULT_GITHUB_MODEL


def _list_repository_files(workspace: Path) -> str:
    files = [
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts
    ]
    return "\n".join(sorted(files)[:500])[:12_000]


def _compact_action_history(action: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in action.items()
        if value is not None and key not in {"old", "new"}
    }


def _compact_worker_evidence(item: dict[str, Any]) -> dict[str, Any]:
    compact = {
        key: item.get(key)
        for key in (
            "evidence_id", "path", "heading_path", "section", "source_class",
            "authority", "instruction_trust", "scope", "version_binding", "symbols",
        )
        if item.get(key) is not None
    }
    content = str(item.get("content") or item.get("snippet") or "")
    compact["content_excerpt"] = content[:1_400]
    return compact


def _pace_github_models_request() -> None:
    global _LAST_REQUEST_AT
    with _REQUEST_RATE_LOCK:
        delay = _MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _LAST_REQUEST_AT)
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST_AT = time.monotonic()


def _strict_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"GitHub Models omitted valid {name}")
    return value


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return {key: _jsonable(item) for key, item in vars(value).items() if not key.startswith("_")}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@contextmanager
def _activated_environment(environment: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
