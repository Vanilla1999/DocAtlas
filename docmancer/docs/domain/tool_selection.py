from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


PUBLIC_DOCS_TOOLS = ("get_docs_context", "prepare_docs", "docs_status")

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
    "статус документации",
    "статус индекса",
    "статус задачи",
    "прогресс задачи",
    "здоров ли индекс",
    "документация устарела",
    "что проиндексировано",
    "какие документы проиндексированы",
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
