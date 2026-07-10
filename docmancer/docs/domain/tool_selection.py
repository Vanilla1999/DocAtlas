from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


PUBLIC_DOCS_TOOLS = ("get_docs_context", "prepare_docs", "docs_status")
_PREPARE_ACTION_BY_TOOL = {
    "sync_project_docs": "sync_project_docs",
    "ingest_project_docs": "sync_project_docs",
    "bootstrap_project_docs": "sync_project_docs",
    "prefetch_project_docs": "prefetch_project_dependency_docs",
    "prefetch_project_dependency_docs": "prefetch_project_dependency_docs",
    "prefetch_library_docs": "prefetch_library_docs",
    "prefetch_docs_targets": "prefetch_docs_targets",
    "prefetch_docs_manifest": "prefetch_docs_manifest",
    "validate_docs_manifest": "validate_docs_manifest",
    "refresh_library_docs": "refresh_library_docs",
    "prune_library_docs": "prune_library_docs",
    "remove_library_docs": "remove_library_docs",
    "cancel_docs_job": "cancel_docs_job",
}
_CONTEXT_ACTION_TOOLS = {
    "get_project_docs",
    "get_project_context",
    "get_library_docs",
}
_STATUS_ACTION_BY_TOOL = {
    "inspect_project_docs": "project",
    "get_docs_job_status": "job",
    "list_docs_jobs": "jobs",
}
_HIDDEN_DOCS_ACTION_TOOLS = {
    "docs_job",
    "get_code_context",
    "get_patch_plan_context",
    "get_patch_constraints",
    "validate_patch_against_constraints",
    "resolve_library_id",
    "inspect_library_docs",
    "list_library_docs",
    "list_docs_sources",
    "prune_library_docs",
    "remove_library_docs",
}

_TOKEN_RE = re.compile(r"[a-zа-яё0-9_-]+", re.IGNORECASE)
_STATUS_PHRASES = (
    "docs status",
    "documentation status",
    "index status",
    "job status",
    "job progress",
    "index health",
    "docs health",
    "is documentation stale",
    "are docs stale",
    "what is indexed",
    "which docs are indexed",
    "docs index is healthy",
    "documentation jobs",
    "running docs jobs",
    "статус документации",
    "статус индекса",
    "статус задачи",
    "прогресс задачи",
    "здоров ли индекс",
    "документация устарела",
    "что проиндексировано",
    "какие документы проиндексированы",
    "задачи документации",
)
_QUESTION_PREFIXES = (
    "how ",
    "why ",
    "explain ",
    "show how ",
    "what does ",
    "как ",
    "почему ",
    "объясни как ",
    "расскажи как ",
)
_PREPARE_TERMS = {
    "sync",
    "synchronize",
    "reindex",
    "index",
    "refresh",
    "prefetch",
    "prune",
    "remove",
    "delete",
    "синхронизируй",
    "синхронизировать",
    "переиндексируй",
    "переиндексировать",
    "проиндексируй",
    "проиндексировать",
    "обнови",
    "обновить",
    "загрузи",
    "загрузить",
    "удали",
    "удалить",
}
_DOC_TARGET_TERMS = {
    "doc",
    "docs",
    "documentation",
    "index",
    "library",
    "dependencies",
    "dependency",
    "документацию",
    "документация",
    "документы",
    "индекс",
    "библиотеки",
    "зависимости",
}


@dataclass(frozen=True)
class ToolSelectionDecision:
    tool: str
    reason_code: str
    confidence: float
    allowed_tools: tuple[str, ...] = PUBLIC_DOCS_TOOLS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_public_docs_action(action: Any) -> dict[str, Any] | None:
    """Map DocAtlas-internal next actions onto the public three-tool surface.

    Host actions such as code_search remain untouched. Hidden DocAtlas actions
    are removed unless they have an equivalent prepare_docs lifecycle action.
    """

    if not isinstance(action, dict):
        return None
    normalized = dict(action)
    tool = str(normalized.get("tool") or "").strip()
    if not tool or tool in PUBLIC_DOCS_TOOLS:
        return normalized
    if tool in _CONTEXT_ACTION_TOOLS:
        arguments = dict(normalized.get("arguments_patch") or {})
        if "query" in arguments and "question" not in arguments:
            arguments["question"] = arguments.pop("query")
        normalized.update({
            "type": "get_docs_context",
            "tool": "get_docs_context",
            "arguments_patch": arguments,
        })
        return normalized
    status_action = _STATUS_ACTION_BY_TOOL.get(tool)
    if status_action:
        arguments = dict(normalized.get("arguments_patch") or {})
        arguments["action"] = status_action
        normalized.update({
            "type": "docs_status",
            "tool": "docs_status",
            "arguments_patch": arguments,
        })
        return normalized
    prepare_action = _PREPARE_ACTION_BY_TOOL.get(tool)
    if prepare_action:
        arguments = dict(normalized.get("arguments_patch") or {})
        arguments["action"] = prepare_action
        normalized.update({
            "type": "prepare_docs",
            "tool": "prepare_docs",
            "arguments_patch": arguments,
        })
        return normalized
    if tool in _HIDDEN_DOCS_ACTION_TOOLS:
        return None
    return normalized


def normalize_public_docs_actions(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure top-level DocAtlas next actions are callable on the public surface."""

    normalized = dict(payload)
    primary = normalize_public_docs_action(normalized.get("next_action"))
    actions: list[dict[str, Any]] = []
    for action in normalized.get("next_actions") or []:
        candidate = normalize_public_docs_action(action)
        if candidate is not None and candidate not in actions:
            actions.append(candidate)
    if primary is not None and primary not in actions:
        actions.insert(0, primary)
    if primary is None and actions:
        primary = actions[0]
    normalized["next_action"] = primary
    normalized["next_actions"] = actions
    return normalized


def select_public_docs_tool(
    user_text: str,
    *,
    next_action_tool: str | None = None,
) -> ToolSelectionDecision:
    """Select one public Docs MCP tool using the documented first-call policy.

    Natural questions always enter through get_docs_context. Lifecycle mutation
    is selected only for an explicit docs operation or a returned next_action.
    Status is read-only and reserved for explicit health/progress requests.
    """

    if next_action_tool == "prepare_docs":
        return ToolSelectionDecision(
            tool="prepare_docs",
            reason_code="returned_next_action",
            confidence=1.0,
        )

    normalized = " ".join(_TOKEN_RE.findall((user_text or "").lower()))
    if normalized.startswith(_QUESTION_PREFIXES):
        return ToolSelectionDecision(
            tool="get_docs_context",
            reason_code="natural_question_entrypoint",
            confidence=0.99,
        )
    if any(phrase in normalized for phrase in _STATUS_PHRASES):
        return ToolSelectionDecision(
            tool="docs_status",
            reason_code="explicit_status_request",
            confidence=0.98,
        )

    tokens = set(normalized.split())
    if tokens & _PREPARE_TERMS and tokens & _DOC_TARGET_TERMS:
        return ToolSelectionDecision(
            tool="prepare_docs",
            reason_code="explicit_lifecycle_request",
            confidence=0.96,
        )

    return ToolSelectionDecision(
        tool="get_docs_context",
        reason_code="default_question_entrypoint",
        confidence=0.99,
    )
