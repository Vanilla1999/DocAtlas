from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


NETWORK_PATTERNS = (r"\bcurl\b", r"\bwget\b", r"https?://", r"WebFetch", r"WebSearch", r"browser")
DOCATLAS_PATTERNS = ("docmancer", "doc-atlas", "get_docs_context", "docmancer-docs")
GET_DOCS_CONTEXT_PATTERNS = ("get_docs_context",)
PREPARE_DOCS_PATTERNS = ("prepare_docs",)
CONTEXT7_PATTERNS = ("context7", "resolve-library-id", "query-docs")


@dataclass(frozen=True)
class PolicyAudit:
    condition_id: str
    clean: bool
    docatlas_calls: int
    get_docs_context_calls: int
    prepare_docs_calls: int
    context7_calls: int
    web_calls: int
    network_shell_calls: int
    network_attempts: int
    foreign_mcp_calls: int
    first_docatlas_call_before_first_edit: bool | None
    first_docatlas_sequence: int | None
    first_edit_sequence: int | None
    docatlas_tool_name_seen: str | None
    violations: list[str]

    def to_json(self) -> dict[str, Any]:
        return self.__dict__.copy()


def audit_trajectory(condition_id: str, trajectory_path: Path | None, output_path: Path | None = None) -> PolicyAudit:
    text = ""
    events: list[dict[str, Any]] = []
    if trajectory_path and trajectory_path.exists():
        raw = trajectory_path.read_text(encoding="utf-8")
        text = raw
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                events = [x for x in loaded if isinstance(x, dict)]
        except json.JSONDecodeError:
            events = []

    docatlas_calls = _count_tool_patterns(events, DOCATLAS_PATTERNS)
    get_docs_context_calls = _count_tool_patterns(events, GET_DOCS_CONTEXT_PATTERNS)
    prepare_docs_calls = _count_tool_patterns(events, PREPARE_DOCS_PATTERNS)
    context7_calls = _count_tool_patterns(events, CONTEXT7_PATTERNS)
    web_calls = _count_web_tool_calls(events)
    network_shell_calls = _count_network_shell(events, text)
    foreign_mcp_calls = _count_foreign_mcp_calls(events)
    first_docatlas_sequence = _first_tool_sequence(events, GET_DOCS_CONTEXT_PATTERNS)
    first_edit_sequence = _first_edit_sequence(events)
    before_edit = None
    if first_docatlas_sequence is not None or first_edit_sequence is not None:
        before_edit = first_docatlas_sequence is not None and (first_edit_sequence is None or first_docatlas_sequence < first_edit_sequence)
    tool_name_seen = _first_tool_name(events, GET_DOCS_CONTEXT_PATTERNS)
    violations: list[str] = []

    network_attempts = web_calls + network_shell_calls

    if condition_id in {"repo_only", "repo_only_strict_offline", "repo_plus_audited_external_context"}:
        if docatlas_calls:
            violations.append(f"{condition_id} used DocAtlas tools")
        if context7_calls:
            violations.append(f"{condition_id} used Context7 tools")
        if web_calls or network_shell_calls:
            violations.append(f"{condition_id} used web or network shell tools")
    elif condition_id == "repo_only_web_audited":
        if docatlas_calls:
            violations.append("repo_only_web_audited used DocAtlas tools")
        if context7_calls:
            violations.append("repo_only_web_audited used Context7 tools")
    elif condition_id in {"docatlas_bounded_direct", "docatlas_bounded_subagent"}:
        if docatlas_calls:
            violations.append("bounded delivery exposed a parent-visible DocAtlas tool call")
        if context7_calls:
            violations.append("docatlas condition used Context7 tools")
        if web_calls or network_shell_calls:
            violations.append("docatlas condition used web or network shell tools")
        if foreign_mcp_calls:
            violations.append("docatlas condition used foreign MCP tools")
    elif condition_id in {"docatlas_snippet_first", "docatlas_tool_optional", "docatlas_tool_recommended", "docatlas_context_injected", "docatlas_tool_required_once", "docatlas_action_checklist_injected", "docatlas_patch_constraints_injected", "docatlas_patch_constraints_workflow", "docatlas_action_checklist_only"}:
        if context7_calls:
            violations.append("docatlas condition used Context7 tools")
        if web_calls or network_shell_calls:
            violations.append("docatlas condition used web or network shell tools")
        if foreign_mcp_calls:
            violations.append("docatlas condition used foreign MCP tools")
        if condition_id == "docatlas_tool_required_once":
            if get_docs_context_calls != 1:
                violations.append(f"required_get_docs_context_call_count:{get_docs_context_calls}")
            if get_docs_context_calls == 1 and not before_edit:
                violations.append("required_docatlas_call_missing")
            if prepare_docs_calls:
                violations.append("prepare_docs_forbidden")
            required_events = [
                event for event in events
                if _matches_patterns(event, GET_DOCS_CONTEXT_PATTERNS)
            ]
            if len(required_events) == 1:
                arguments = required_events[0].get("arguments", {})
                arguments = arguments if isinstance(arguments, dict) else {}
                if arguments.get("question_matches_task_objective") is not True:
                    violations.append("required_docatlas_objective_mismatch")
                if arguments.get("retrieval_succeeded") is not True:
                    violations.append("required_docatlas_retrieval_unsuccessful")
                if arguments.get("delivery_strategy") != "bounded_direct":
                    violations.append("required_docatlas_delivery_strategy_mismatch")
                if arguments.get("action_packet_status") not in {"ok", "truncated"}:
                    violations.append("required_docatlas_action_packet_invalid")

    audit = PolicyAudit(
        condition_id=condition_id,
        clean=not violations,
        docatlas_calls=docatlas_calls,
        get_docs_context_calls=get_docs_context_calls,
        prepare_docs_calls=prepare_docs_calls,
        context7_calls=context7_calls,
        web_calls=web_calls,
        network_shell_calls=network_shell_calls,
        network_attempts=network_attempts,
        foreign_mcp_calls=foreign_mcp_calls,
        first_docatlas_call_before_first_edit=before_edit,
        first_docatlas_sequence=first_docatlas_sequence,
        first_edit_sequence=first_edit_sequence,
        docatlas_tool_name_seen=tool_name_seen,
        violations=violations,
    )
    if output_path is not None:
        output_path.write_text(json.dumps(audit.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    return audit


def _count_patterns(text: str, patterns: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(pattern.lower()) for pattern in patterns)


def _count_tool_patterns(events: list[dict[str, Any]], patterns: tuple[str, ...]) -> int:
    count = 0
    for event in events:
        tool_name = str(event.get("tool_name", "")).lower()
        args = event.get("arguments", {}) if isinstance(event.get("arguments"), dict) else {}
        server = str(args.get("server", "")).lower()
        tool = str(args.get("tool", "")).lower()
        haystack = " ".join((tool_name, server, tool))
        if any(pattern.lower() in haystack for pattern in patterns):
            count += 1
    return count


def _event_tool_haystack(event: dict[str, Any]) -> str:
    tool_name = str(event.get("tool_name", "")).lower()
    args = event.get("arguments", {}) if isinstance(event.get("arguments"), dict) else {}
    server = str(args.get("server", "")).lower()
    tool = str(args.get("tool", "")).lower()
    return " ".join((tool_name, server, tool))


def _matches_patterns(event: dict[str, Any], patterns: tuple[str, ...]) -> bool:
    haystack = _event_tool_haystack(event)
    return any(pattern.lower() in haystack for pattern in patterns)


def _first_tool_sequence(events: list[dict[str, Any]], patterns: tuple[str, ...]) -> int | None:
    for event in events:
        if _matches_patterns(event, patterns):
            sequence = event.get("sequence")
            return sequence if isinstance(sequence, int) else None
    return None


def _first_tool_name(events: list[dict[str, Any]], patterns: tuple[str, ...]) -> str | None:
    for event in events:
        if _matches_patterns(event, patterns):
            args = event.get("arguments", {}) if isinstance(event.get("arguments"), dict) else {}
            return str(args.get("tool") or event.get("tool_name") or "get_docs_context")
    return None


def _first_edit_sequence(events: list[dict[str, Any]]) -> int | None:
    for event in events:
        tool_name = str(event.get("tool_name", "")).lower()
        args = json.dumps(event.get("arguments", {}), sort_keys=True).lower()
        if "edit" in tool_name or "file_change" in args or "changes" in args:
            sequence = event.get("sequence")
            return sequence if isinstance(sequence, int) else None
    return None


def _count_foreign_mcp_calls(events: list[dict[str, Any]]) -> int:
    count = 0
    for event in events:
        args = event.get("arguments", {}) if isinstance(event.get("arguments"), dict) else {}
        server = str(args.get("server", "")).lower()
        if server and server not in {"docmancer-docs", ""}:
            count += 1
    return count


def _count_network_shell(events: list[dict[str, Any]], text: str) -> int:
    count = 0
    for event in events:
        tool_name = str(event.get("tool_name", "")).lower()
        args = json.dumps(event.get("arguments", {}), sort_keys=True).lower()
        if "bash" in tool_name and any(marker in args for marker in ("curl", "wget", "http://", "https://")):
            count += 1
    if re.search(r"\b(curl|wget)\b", text, flags=re.IGNORECASE):
        count += 1
    return count


def _count_web_tool_calls(events: list[dict[str, Any]]) -> int:
    count = 0
    for event in events:
        tool_name = str(event.get("tool_name", "")).lower()
        args = json.dumps(event.get("arguments", {}), sort_keys=True).lower()
        if any(marker in tool_name for marker in ("webfetch", "websearch", "web_fetch", "web_search", "browser")):
            count += 1
        elif any(marker in args for marker in ("webfetch", "websearch", "web_fetch", "web_search")):
            count += 1
    return count
