from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


NETWORK_PATTERNS = (r"\bcurl\b", r"\bwget\b", r"https?://", r"WebFetch", r"WebSearch", r"browser")
DOCATLAS_PATTERNS = ("docmancer", "docatlas", "get_docs_context", "docmancer-docs")
CONTEXT7_PATTERNS = ("context7", "resolve-library-id", "query-docs")


@dataclass(frozen=True)
class PolicyAudit:
    condition_id: str
    clean: bool
    docatlas_calls: int
    context7_calls: int
    web_calls: int
    network_shell_calls: int
    foreign_mcp_calls: int
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

    docatlas_calls = _count_patterns(text, DOCATLAS_PATTERNS)
    context7_calls = _count_patterns(text, CONTEXT7_PATTERNS)
    web_calls = sum(1 for pattern in NETWORK_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE))
    network_shell_calls = _count_network_shell(events, text)
    foreign_mcp_calls = 0
    violations: list[str] = []

    if condition_id == "repo_only":
        if docatlas_calls:
            violations.append("repo_only used DocAtlas tools")
        if context7_calls:
            violations.append("repo_only used Context7 tools")
        if web_calls or network_shell_calls:
            violations.append("repo_only used web or network shell tools")
    elif condition_id == "docatlas_snippet_first":
        if context7_calls:
            violations.append("docatlas condition used Context7 tools")
        if web_calls or network_shell_calls:
            violations.append("docatlas condition used web or network shell tools")
        if foreign_mcp_calls:
            violations.append("docatlas condition used foreign MCP tools")

    audit = PolicyAudit(
        condition_id=condition_id,
        clean=not violations,
        docatlas_calls=docatlas_calls,
        context7_calls=context7_calls,
        web_calls=web_calls,
        network_shell_calls=network_shell_calls,
        foreign_mcp_calls=foreign_mcp_calls,
        violations=violations,
    )
    if output_path is not None:
        output_path.write_text(json.dumps(audit.to_json(), indent=2, sort_keys=True), encoding="utf-8")
    return audit


def _count_patterns(text: str, patterns: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(lowered.count(pattern.lower()) for pattern in patterns)


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
