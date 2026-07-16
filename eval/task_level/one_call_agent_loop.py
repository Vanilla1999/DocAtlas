"""Provider-neutral, locally testable one-call DocAtlas agent loop."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from docmancer.docs.application.model_visible_projection import (
    FORBIDDEN_MODEL_KEYS,
    estimate_projection_tokens,
)
from eval.task_level.execution import shell_call_metrics


LOOP_AUDIT_SCHEMA_VERSION = 1
PROFILE_VERSION = "one-call-local-v1"
DOCATLAS_STATES = {"not_called", "accepted", "insufficient", "failed"}
_DOCATLAS_TOOL_MARKERS = ("get_docs_context", "docatlas", "doc-atlas", "docmancer")
_ACTION_ALIASES = {
    "docatlas": "docatlas",
    "get_docs_context": "docatlas",
    "finish": "finish",
    "edit": "edit",
    "repair": "repair",
    "shell": "shell",
    "bash": "shell",
    "command": "shell",
    "command_execution": "shell",
}


@dataclass(frozen=True)
class LoopBudgetProfile:
    profile_version: str = PROFILE_VERSION
    max_docatlas_calls: int = 1
    max_model_requests: int = 12
    max_serialized_input_tokens_per_request: int = 7_000
    max_repair_passes: int = 1
    max_test_invocations: int = 2
    max_tool_output_bytes_per_call: int = 32_768


@dataclass(frozen=True)
class LoopCapabilities:
    one_docatlas_call_enforced: bool = False
    dynamic_tool_exposure: bool = False
    hard_model_request_limit: bool = False
    hard_serialized_input_limit: bool = False
    bounded_tool_output_capture: bool = False
    bounded_repairs_and_tests: bool = False
    deterministic_history_compaction: bool = False
    provider_usage_available: bool = False

    @property
    def verified(self) -> bool:
        return all((
            self.one_docatlas_call_enforced,
            self.dynamic_tool_exposure,
            self.hard_model_request_limit,
            self.hard_serialized_input_limit,
            self.bounded_tool_output_capture,
            self.bounded_repairs_and_tests,
            self.deterministic_history_compaction,
        ))


@dataclass(frozen=True)
class HistoryBlock:
    block_id: str
    kind: str
    value: Any
    required: bool = False
    priority: int = 100


@dataclass
class ToolExecution:
    stdout: Iterable[str | bytes] = ()
    stderr: Iterable[str | bytes] = ()
    result: Iterable[str | bytes] = ()
    exit_code: int | None = None
    diff: str | None = None
    complete_hashes: dict[str, str] = field(default_factory=dict)


class ToolOutputLimitError(RuntimeError):
    """Raised by an adapter before returning oversized materialized output."""


class DocAtlasOutputLimitError(ToolOutputLimitError):
    """Raised specifically for an oversized materialized DocAtlas payload."""


class AgentLoopAdapter(Protocol):
    capabilities: LoopCapabilities

    def tool_catalog(self, *, docatlas_enabled: bool) -> list[dict[str, Any]]: ...
    def model_request(self, retained_state: dict[str, Any], *, docatlas_enabled: bool) -> dict[str, Any]: ...
    def call_docatlas(self, arguments: dict[str, Any], *, max_bytes: int) -> dict[str, Any]: ...
    def set_docatlas_enabled(self, enabled: bool) -> None: ...
    def execute_action(
        self, action: dict[str, Any], *, max_output_bytes: int
    ) -> ToolExecution: ...
    def provider_usage(self) -> dict[str, int] | None: ...


@dataclass
class LoopOutcome:
    status: str
    reason_code: str
    docatlas_state: str
    capability_verified: bool
    counts: dict[str, int]
    audit: dict[str, Any]


@dataclass
class _LoopState:
    docatlas_state: str = "not_called"
    model_requests: int = 0
    docatlas_calls: int = 0
    repair_passes: int = 0
    test_invocations: int = 0
    action_attempts: int = 0
    current_diff: dict[str, Any] | None = None
    docatlas_result: dict[str, Any] | None = None
    latest_failure: dict[str, Any] | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)
    omitted: list[dict[str, str]] = field(default_factory=list)
    shell_events: list[dict[str, Any]] = field(default_factory=list)
    dynamic_tool_exposure_verified: bool = False
    bounded_output_hashes_verified: bool = True


def canonical_loop_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def estimated_loop_tokens(value: Any) -> int:
    size = len(canonical_loop_bytes(value))
    return max(1, math.ceil(size / 4))


def compact_retained_history(
    blocks: Iterable[HistoryBlock], *, max_tokens: int
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Fit whole blocks deterministically and hash every omitted value."""

    ordered = list(blocks)
    retained = list(ordered)
    omitted: list[dict[str, str]] = []

    def payload() -> dict[str, Any]:
        return {"schema_version": 1, "blocks": [
            {"block_id": block.block_id, "kind": block.kind, "value": block.value}
            for block in retained
        ]}

    removable = sorted(
        (block for block in retained if not block.required),
        key=lambda block: (-block.priority, block.block_id),
    )
    while estimated_loop_tokens(payload()) > max_tokens and removable:
        block = removable.pop(0)
        retained.remove(block)
        omitted.append(_omitted_block(block, "request_input_budget"))
    if estimated_loop_tokens(payload()) > max_tokens:
        return None, omitted
    return payload(), sorted(omitted, key=lambda row: row["block_id"])


def capture_tool_execution(execution: ToolExecution, *, max_bytes: int) -> dict[str, Any]:
    """Capture each stream incrementally under one hard per-call byte ceiling."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    channel_values: tuple[tuple[str, Iterable[str | bytes]], ...] = (
        ("stdout", execution.stdout),
        ("stderr", execution.stderr),
        ("result", execution.result),
        ("diff", (() if execution.diff is None else (execution.diff,))),
    )
    base, remainder = divmod(max_bytes, len(channel_values))
    channels: dict[str, dict[str, Any]] = {}
    for index, (name, chunks) in enumerate(channel_values):
        channel_limit = base + (1 if index < remainder else 0)
        data = bytearray()
        truncated = False
        digest = hashlib.sha256()
        observed = 0
        for chunk in chunks:
            encoded = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8")
            observed += len(encoded)
            remaining = channel_limit - len(data)
            if remaining > 0:
                retained = encoded[:remaining]
                data.extend(retained)
                digest.update(retained)
            if len(encoded) > max(0, remaining):
                truncated = True
                if name == "diff":
                    digest = hashlib.sha256(encoded)
                break
        complete_digest = execution.complete_hashes.get(name)
        complete_hash_available = bool(
            isinstance(complete_digest, str)
            and len(complete_digest) == 64
            and all(char in "0123456789abcdef" for char in complete_digest.lower())
        )
        if truncated and complete_hash_available:
            digest_text = str(complete_digest)
            digest_scope = "complete"
        elif truncated and name == "diff":
            digest_text = digest.hexdigest()
            digest_scope = "complete"
        else:
            digest_text = digest.hexdigest()
            digest_scope = "captured_prefix" if truncated else "complete"
        channels[name] = {
            "text": bytes(data).decode("utf-8", errors="replace"),
            "captured_bytes": len(data),
            "observed_bytes": observed,
            "sha256": digest_text,
            "sha256_scope": digest_scope,
            "truncated": truncated,
        }
    channels["exit_code"] = execution.exit_code
    channel_names = tuple(name for name, _ in channel_values)
    channels["capture_bytes"] = sum(channels[name]["captured_bytes"] for name in channel_names)
    channels["truncated"] = any(channels[name]["truncated"] for name in channel_names)
    return channels


class OneCallAgentLoop:
    def __init__(self, adapter: AgentLoopAdapter, *, profile: LoopBudgetProfile | None = None):
        self.adapter = adapter
        self.profile = profile or LoopBudgetProfile()
        _validate_profile(self.profile)

    def run(
        self, *, objective: str, task_id: str | None = None, audit_path: Path | None = None
    ) -> LoopOutcome:
        state = _LoopState()
        objective_hash = hashlib.sha256(str(objective).encode("utf-8")).hexdigest()
        task_hash = hashlib.sha256(str(task_id or objective_hash).encode("utf-8")).hexdigest()
        terminal_status = "incomplete"
        terminal_reason = "model_ended_without_finish"

        while True:
            if state.model_requests >= self.profile.max_model_requests:
                terminal_status, terminal_reason = "budget_exhausted", "model_request_limit"
                break
            docatlas_enabled = state.docatlas_state == "not_called"
            tool_catalog = self.adapter.tool_catalog(docatlas_enabled=docatlas_enabled)
            if not isinstance(tool_catalog, list):
                terminal_status, terminal_reason = "failed", "invalid_tool_catalog"
                break
            if not docatlas_enabled:
                if _catalog_exposes_docatlas(tool_catalog):
                    terminal_status, terminal_reason = "failed", "dynamic_tool_exposure_violation"
                    break
                state.dynamic_tool_exposure_verified = True
            catalog_tokens = estimated_loop_tokens({"tools": tool_catalog})
            history_budget = self.profile.max_serialized_input_tokens_per_request - catalog_tokens
            if history_budget <= 0:
                terminal_status, terminal_reason = "budget_exhausted", "serialized_input_limit"
                break
            retained, omitted = compact_retained_history(
                self._history_blocks(objective, task_hash, state),
                max_tokens=history_budget,
            )
            state.omitted.extend(row for row in omitted if row not in state.omitted)
            if retained is None:
                terminal_status, terminal_reason = "budget_exhausted", "serialized_input_limit"
                break
            request = {"history": retained, "tools": tool_catalog}
            if estimated_loop_tokens(request) > self.profile.max_serialized_input_tokens_per_request:
                terminal_status, terminal_reason = "budget_exhausted", "serialized_input_limit"
                break
            state.model_requests += 1
            action = self.adapter.model_request(
                request,
                docatlas_enabled=docatlas_enabled,
            )
            if not isinstance(action, dict):
                terminal_status, terminal_reason = "failed", "invalid_model_action"
                break
            action_type = _normalize_action_type(action.get("type"))
            if action_type is None:
                terminal_status, terminal_reason = "failed", "invalid_model_action"
                break

            if action_type == "docatlas":
                if state.docatlas_state != "not_called" or state.docatlas_calls >= self.profile.max_docatlas_calls:
                    terminal_status, terminal_reason = "incomplete", "second_docatlas_call_rejected"
                    break
                state.docatlas_calls += 1
                try:
                    payload = self.adapter.call_docatlas(
                        dict(action.get("arguments") or {}),
                        max_bytes=self.profile.max_tool_output_bytes_per_call,
                    )
                except DocAtlasOutputLimitError:
                    state.docatlas_state = "failed"
                    terminal_status, terminal_reason = "budget_exhausted", "docatlas_output_limit"
                    break
                if not isinstance(payload, dict) or _json_exceeds_bytes(
                    payload, self.profile.max_tool_output_bytes_per_call
                ):
                    state.docatlas_state = "failed"
                    terminal_status, terminal_reason = "budget_exhausted", "docatlas_output_limit"
                    break
                if payload.get("status") == "insufficient_evidence":
                    state.docatlas_state = "insufficient"
                    state.docatlas_result = payload
                    terminal_status, terminal_reason = "incomplete", "insufficient_evidence"
                    break
                payload_errors = validate_docatlas_result(payload)
                if payload_errors:
                    state.docatlas_state = "failed"
                    terminal_status, terminal_reason = "failed", "invalid_docatlas_result"
                    break
                state.docatlas_state = "accepted"
                state.docatlas_result = payload
                if self.adapter.capabilities.dynamic_tool_exposure:
                    self.adapter.set_docatlas_enabled(False)
                state.completed.append({
                    "sequence": len(state.completed) + 1,
                    "kind": "docatlas", "status": "accepted", "sha256": _hash_value(payload),
                })
                continue

            if action_type == "finish":
                if state.docatlas_state != "accepted":
                    terminal_status, terminal_reason = "incomplete", "docatlas_not_accepted"
                elif state.docatlas_result and state.docatlas_result.get("kind") == "patch_context" and state.action_attempts == 0:
                    terminal_status, terminal_reason = "incomplete", "patch_not_attempted"
                else:
                    terminal_status, terminal_reason = "success", "completed"
                break

            if state.docatlas_state != "accepted":
                terminal_status, terminal_reason = "incomplete", "edit_before_docatlas_acceptance"
                break

            if action_type in {"edit", "repair"}:
                is_repair = state.action_attempts > 0
                if action_type == "repair" and not is_repair:
                    terminal_status, terminal_reason = "incomplete", "repair_before_initial_edit"
                    break
                if is_repair and state.repair_passes >= self.profile.max_repair_passes:
                    terminal_status, terminal_reason = "budget_exhausted", "repair_pass_limit"
                    break
                if is_repair:
                    state.repair_passes += 1
                state.action_attempts += 1

            command = str(action.get("command") or "")
            is_test = bool(shell_call_metrics([{
                "tool_name": "Shell", "arguments": {"command": command}, "status": "unknown",
            }])["test_runs"]) if action_type == "shell" else False
            if is_test and state.test_invocations >= self.profile.max_test_invocations:
                terminal_status, terminal_reason = "budget_exhausted", "test_invocation_limit"
                break
            if is_test:
                state.test_invocations += 1

            try:
                execution = self.adapter.execute_action(
                    action,
                    max_output_bytes=self.profile.max_tool_output_bytes_per_call,
                )
            except ToolOutputLimitError:
                terminal_status, terminal_reason = "budget_exhausted", "action_output_limit"
                break
            if not isinstance(execution, ToolExecution):
                terminal_status, terminal_reason = "failed", "invalid_tool_execution"
                break
            captured = capture_tool_execution(
                execution, max_bytes=self.profile.max_tool_output_bytes_per_call,
            )
            if captured["truncated"] and any(
                captured[name]["truncated"] and captured[name]["sha256_scope"] != "complete"
                for name in ("stdout", "stderr", "result", "diff")
            ):
                state.bounded_output_hashes_verified = False
            if execution.diff is not None:
                self._replace_diff(state, captured["diff"])
            if action_type == "shell":
                shell_event = {
                    "tool_name": "Shell",
                    "arguments": {"command": command},
                    "exit_code": execution.exit_code,
                }
                state.shell_events.append(shell_event)
            summary = {
                "kind": action_type or "tool",
                "exit_code": execution.exit_code,
                "output_sha256": _hash_value(captured),
                "truncated": bool(captured["truncated"]),
            }
            full_output_digest = hashlib.sha256(canonical_loop_bytes({
                name: captured[name]["sha256"] for name in ("stdout", "stderr", "result", "diff")
            })).hexdigest()
            if captured["truncated"]:
                state.omitted.append({
                    "block_id": f"request-{state.model_requests:03d}-tool-output",
                    "sha256": full_output_digest,
                    "reason": "tool_output_truncated",
                })
            if execution.exit_code not in (None, 0):
                if state.latest_failure is not None:
                    state.omitted.append(_omitted_value(
                        f"request-{state.model_requests:03d}-superseded-failure",
                        state.latest_failure, "superseded_failure",
                    ))
                state.latest_failure = {
                    "command_fingerprint": hashlib.sha256(command.strip().encode("utf-8")).hexdigest(),
                    "exit_code": execution.exit_code,
                    "stdout": captured["stdout"]["text"],
                    "stderr": captured["stderr"]["text"],
                    "truncated": captured["truncated"],
                }
            else:
                if any(captured[name]["observed_bytes"] for name in ("stdout", "stderr", "result", "diff")):
                    state.omitted.append({
                        "block_id": f"request-{state.model_requests:03d}-tool-output",
                        "sha256": full_output_digest,
                        "reason": "successful_tool_output_summarized",
                    })
                state.completed.append({"sequence": len(state.completed) + 1, **summary})

        audit = self._audit(
            state, objective_hash=objective_hash, task_hash=task_hash,
            terminal_status=terminal_status, terminal_reason=terminal_reason,
        )
        if audit_path is not None:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return LoopOutcome(
            terminal_status, terminal_reason, state.docatlas_state,
            self._capability_verified(state), self._counts(state), audit,
        )

    def _history_blocks(self, objective: str, task_hash: str, state: _LoopState) -> list[HistoryBlock]:
        blocks = [
            HistoryBlock("objective", "objective", {"task_hash": task_hash, "text": objective}, True, 0),
            HistoryBlock("action-state", "action_state", {
                "docatlas_state": state.docatlas_state,
                "model_requests": state.model_requests,
                "repairs": state.repair_passes,
                "tests": state.test_invocations,
            }, True, 0),
        ]
        if state.docatlas_result is not None:
            blocks.append(HistoryBlock("docatlas", "docatlas_result", state.docatlas_result, True, 0))
        if state.current_diff is not None:
            blocks.append(HistoryBlock("current-diff", "current_diff", state.current_diff, True, 0))
        if state.latest_failure is not None:
            blocks.append(HistoryBlock("latest-failure", "latest_failure", state.latest_failure, True, 0))
        for index, item in enumerate(state.completed[-8:]):
            sequence = int(item.get("sequence") or index)
            blocks.append(HistoryBlock(
                f"completed-{sequence:03d}", "completed_action", item, False, 200 + index,
            ))
        return blocks

    def _replace_diff(self, state: _LoopState, captured: dict[str, Any]) -> None:
        if state.current_diff is not None:
            state.omitted.append(_omitted_value(
                f"request-{state.model_requests:03d}-previous-diff", state.current_diff, "superseded_diff",
            ))
        state.current_diff = {
            "text": str(captured.get("text") or ""),
            "sha256": str(captured.get("sha256") or ""),
            "sha256_scope": str(captured.get("sha256_scope") or "captured_prefix"),
            "observed_bytes": int(captured.get("observed_bytes") or 0),
            "original_bytes": int(captured.get("observed_bytes") or 0),
            "truncated": bool(captured.get("truncated")),
        }
        if state.current_diff["truncated"]:
            state.omitted.append({
                "block_id": f"request-{state.model_requests:03d}-diff-tail",
                "sha256": state.current_diff["sha256"], "reason": "diff_summarized",
            })

    def _capability_verified(self, state: _LoopState) -> bool:
        return (
            self.adapter.capabilities.verified
            and state.dynamic_tool_exposure_verified
            and state.bounded_output_hashes_verified
        )

    def _counts(self, state: _LoopState) -> dict[str, int]:
        shell = shell_call_metrics(state.shell_events)
        return {
            "model_requests": state.model_requests,
            "docatlas_calls": state.docatlas_calls,
            "repair_passes": state.repair_passes,
            "test_invocations": state.test_invocations,
            "action_attempts": state.action_attempts,
            "failed_shell_calls": shell["failed_shell_calls"],
            "retried_command_count": shell["retried_command_count"],
        }

    def _audit(
        self, state: _LoopState, *, objective_hash: str, task_hash: str,
        terminal_status: str, terminal_reason: str,
    ) -> dict[str, Any]:
        usage = self.adapter.provider_usage() if self.adapter.capabilities.provider_usage_available else None
        sanitized_usage = {
            key: value for key, value in (usage or {}).items()
            if key in {"input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens"}
            and isinstance(value, int) and not isinstance(value, bool)
        } or None
        omitted = sorted(
            {(row["block_id"], row["sha256"], row["reason"]) for row in state.omitted}
        )
        return {
            "schema_version": LOOP_AUDIT_SCHEMA_VERSION,
            "profile": asdict(self.profile),
            "capabilities": {
                **asdict(self.adapter.capabilities),
                "dynamic_tool_exposure_canary": state.dynamic_tool_exposure_verified,
                "bounded_output_hashes_canary": state.bounded_output_hashes_verified,
                "verified": self._capability_verified(state),
            },
            "objective_sha256": objective_hash,
            "task_sha256": task_hash,
            "docatlas_state": state.docatlas_state,
            "terminal": {"status": terminal_status, "reason_code": terminal_reason},
            "counts": self._counts(state),
            "omitted_blocks": [
                {"block_id": block_id, "sha256": digest, "reason": reason}
                for block_id, digest, reason in omitted
            ],
            "provider_usage": sanitized_usage,
        }


def validate_docatlas_result(payload: dict[str, Any]) -> list[str]:
    """Validate the compact public result before retaining it in model history."""

    errors: list[str] = []
    status = payload.get("status")
    kind = payload.get("kind")
    if status not in {"ok", "truncated"}:
        errors.append("successful DocAtlas result has an invalid status")
    if kind not in {"docs_answer", "patch_context"}:
        errors.append("DocAtlas result has an invalid kind")
    forbidden = sorted(_find_forbidden_model_keys(payload))
    if forbidden:
        errors.append("forbidden model-visible fields: " + ", ".join(forbidden))
    try:
        actual_tokens = estimate_projection_tokens(payload)
    except (TypeError, ValueError):
        actual_tokens = -1
        errors.append("DocAtlas result must be JSON serializable")
    declared_tokens = payload.get("estimated_tokens")
    if (
        not isinstance(declared_tokens, int)
        or isinstance(declared_tokens, bool)
        or declared_tokens != actual_tokens
    ):
        errors.append("DocAtlas estimated_tokens does not match the canonical payload")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("successful DocAtlas result requires sources")
        source_ids: set[str] = set()
    else:
        source_ids = set()
        for source in sources:
            if not isinstance(source, dict):
                errors.append("DocAtlas source must be an object")
                continue
            evidence_id = source.get("evidence_id")
            digest = source.get("content_sha256")
            if not isinstance(evidence_id, str) or not evidence_id.startswith("ev-"):
                errors.append("DocAtlas source has an invalid evidence_id")
            elif evidence_id in source_ids:
                errors.append("DocAtlas sources contain a duplicate evidence_id")
            else:
                source_ids.add(evidence_id)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest.lower())
            ):
                errors.append("DocAtlas source has an invalid content_sha256")

    if kind == "docs_answer":
        allowed = {
            "status", "kind", "answer", "answer_evidence_ids", "sources",
            "omitted_counts", "estimated_tokens",
        }
        if not isinstance(payload.get("answer"), str) or not payload["answer"].strip():
            errors.append("docs_answer requires a non-empty answer")
        refs = payload.get("answer_evidence_ids")
        if not isinstance(refs, list) or not refs or any(ref not in source_ids for ref in refs):
            errors.append("docs_answer claims require returned evidence IDs")
    else:
        allowed = {
            "status", "kind", "schema_version", "objective", "acceptance_conditions",
            "sources", "targets", "invariants", "forbidden_changes",
            "implementation_guidance", "checks", "uncertainties", "omitted_counts",
            "estimated_tokens",
        }
        required = {
            "objective", "sources", "targets", "invariants", "forbidden_changes",
            "implementation_guidance", "checks", "uncertainties", "omitted_counts",
        }
        missing = sorted(required - set(payload))
        if missing:
            errors.append("patch_context is missing canonical fields: " + ", ".join(missing))
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        errors.append("unexpected DocAtlas result fields: " + ", ".join(unexpected))
    return errors


def _validate_profile(profile: LoopBudgetProfile) -> None:
    positive = (
        profile.max_model_requests,
        profile.max_serialized_input_tokens_per_request,
        profile.max_tool_output_bytes_per_call,
    )
    non_negative = (profile.max_repair_passes, profile.max_test_invocations)
    if profile.max_docatlas_calls != 1:
        raise ValueError("the one-call profile requires max_docatlas_calls=1")
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in positive):
        raise ValueError("request, input, and output limits must be positive integers")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in non_negative):
        raise ValueError("repair and test limits must be non-negative integers")


def _normalize_action_type(value: Any) -> str | None:
    return _ACTION_ALIASES.get(str(value or "").strip().lower())


def _catalog_exposes_docatlas(tools: list[dict[str, Any]]) -> bool:
    for tool in tools:
        if not isinstance(tool, dict):
            return True
        name = str(tool.get("name") or "").strip().lower()
        if any(marker in name for marker in _DOCATLAS_TOOL_MARKERS):
            return True
    return False


def _json_exceeds_bytes(value: Any, max_bytes: int) -> bool:
    encoder = json.JSONEncoder(
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    )
    observed = 0
    for chunk in encoder.iterencode(value):
        observed += len(chunk.encode("utf-8"))
        if observed > max_bytes:
            return True
    return False


def _find_forbidden_model_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_MODEL_KEYS:
                found.add(str(key))
            found.update(_find_forbidden_model_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_find_forbidden_model_keys(child))
    return found


class FakeLoopAdapter:
    """Deterministic provider-free adapter used by local contract tests."""

    def __init__(
        self, actions: Iterable[dict[str, Any]], *, docatlas_result: dict[str, Any],
        executions: Iterable[ToolExecution] = (), capabilities: LoopCapabilities | None = None,
        usage: dict[str, int] | None = None,
    ):
        self.actions = list(actions)
        self.docatlas_result = docatlas_result
        self.executions = list(executions)
        self.capabilities = capabilities or LoopCapabilities(
            one_docatlas_call_enforced=True,
            dynamic_tool_exposure=True,
            hard_model_request_limit=True,
            hard_serialized_input_limit=True,
            bounded_tool_output_capture=True,
            bounded_repairs_and_tests=True,
            deterministic_history_compaction=True,
            provider_usage_available=usage is not None,
        )
        self.usage = usage
        self.model_inputs: list[dict[str, Any]] = []
        self.docatlas_enabled_events: list[bool] = [True]
        self.action_output_limits: list[int] = []

    def model_request(self, retained_state: dict[str, Any], *, docatlas_enabled: bool) -> dict[str, Any]:
        self.model_inputs.append(retained_state)
        return self.actions.pop(0) if self.actions else {"type": "noop"}

    def tool_catalog(self, *, docatlas_enabled: bool) -> list[dict[str, Any]]:
        names = ["edit", "shell", "finish"]
        if docatlas_enabled:
            names.insert(0, "get_docs_context")
        return [{"name": name} for name in names]

    def call_docatlas(self, arguments: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
        payload = json.loads(json.dumps(self.docatlas_result))
        if _json_exceeds_bytes(payload, max_bytes):
            raise DocAtlasOutputLimitError("fake DocAtlas result exceeds host boundary")
        return payload

    def set_docatlas_enabled(self, enabled: bool) -> None:
        self.docatlas_enabled_events.append(enabled)

    def execute_action(
        self, action: dict[str, Any], *, max_output_bytes: int
    ) -> ToolExecution:
        self.action_output_limits.append(max_output_bytes)
        return self.executions.pop(0) if self.executions else ToolExecution(exit_code=0)

    def provider_usage(self) -> dict[str, int] | None:
        return self.usage


def _hash_value(value: Any) -> str:
    return hashlib.sha256(canonical_loop_bytes(value)).hexdigest()


def _omitted_block(block: HistoryBlock, reason: str) -> dict[str, str]:
    return _omitted_value(block.block_id, block.value, reason)


def _omitted_value(block_id: str, value: Any, reason: str) -> dict[str, str]:
    return {"block_id": block_id, "sha256": _hash_value(value), "reason": reason}
