"""Reusable semantic frames for bounded project-documentation questions.

This module deliberately does not construct proof obligations.  It recognizes
small, reusable language frames and resolves them to canonical identities.  The
QuestionPlan layer owns composition and fail-closed coverage of the full user
question.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

InventoryKind = Literal["source", "format", "marker"]


@dataclass(frozen=True, slots=True)
class InventoryFrame:
    subject: str
    attribute: str
    item_kind: InventoryKind
    context: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementsFrame:
    subject: str


@dataclass(frozen=True, slots=True)
class ActionFrame:
    operation: str
    surface: str


_QUESTION_START = (
    r"(?:what|which|how|when|where|why|who|can|could|does|do|is|are|should|"
    r"list|name|show|tell|calculate|prescribe|"
    r"что|какие|как|когда|где|почему|перечисли|назови)\b"
)
_ACTION_START = (
    r"(?:rebuild|calculate|prescribe|tell|show|list|name|sync|synchronize|"
    r"update|refresh|reindex|run|verify|audit|check|compare|configure|install|"
    r"delete|remove|start|launch|fetch|explain|"
    r"пересобери|расскажи|покажи|перечисли|синхронизируй|обнови|"
    r"переиндексируй|запусти|проверь|удали)\b"
)

# Strong punctuation is an explicit user boundary.  Periods split only when
# followed by another question/action-like sentence so paths and dotted
# identifiers are not treated as multiple clauses.
_STRONG_CLAUSE_SPLIT_RE = re.compile(
    rf"\s*(?:;|[!?])\s*|\r?\n+|\.\s+(?=(?:{_QUESTION_START}|{_ACTION_START}|[A-ZА-ЯЁ]))",
    re.I,
)

# Conjunctions split only when the right side is itself question-like or starts
# with an action plus an argument.  This avoids turning noun coordination such
# as ``sections and chunks`` or ``cleanup and refresh`` into separate clauses.
_CLAUSE_CONNECTOR_RE = re.compile(
    rf"\s*(?:,\s*)?(?:(?:\b(?:and|but|plus|then)\b)|"
    rf"(?:\bas\s+well\s+as\b)|(?:\balong\s+with\b)|"
    rf"(?:\b(?:и|но|плюс|затем)\b)|(?:\bа\s+также\b))\s+"
    rf"(?!when\s+should\s+it\s+be\s+used\b)"
    rf"(?=(?:{_QUESTION_START}|{_ACTION_START}\s+\S))",
    re.I,
)


def clean_phrase(value: str) -> str:
    value = " ".join(str(value or "").strip(" ?!.,:;").split())
    return re.sub(r"^(?:the|a|an|этот|эта|это)\s+", "", value, flags=re.I)[:180]


def split_question_clauses(question: str) -> tuple[str, ...]:
    """Split explicit independent clauses while preserving noun coordination."""

    value = str(question or "").strip()
    if not value:
        return ()
    strong_parts = [part for part in _STRONG_CLAUSE_SPLIT_RE.split(value) if part.strip()]
    parts: list[str] = []
    for strong_part in strong_parts:
        parts.extend(
            part for part in _CLAUSE_CONNECTOR_RE.split(strong_part) if part.strip()
        )
    cleaned = [clean_phrase(part) for part in parts]
    return tuple(part for part in cleaned if part)


def _inventory_frame(items: str, context: str | None) -> InventoryFrame:
    raw = items.casefold()
    if "marker" in raw or "маркер" in raw:
        return InventoryFrame("test suite", "marker", "marker", context)
    if "format" in raw or "формат" in raw:
        return InventoryFrame("file formats", "file format", "format", context or "indexing")
    return InventoryFrame("source types", "source", "source", context or "indexing")


def match_inventory_frame(question: str) -> InventoryFrame | None:
    q = clean_phrase(question)
    patterns = (
        re.compile(
            r"^(?:what|which)\s+(?P<items>source\s+types?)\s+"
            r"(?:are\s+)?(?:available|supported)(?:\s+for\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:list|name|show)\s+(?:the\s+)?(?P<items>source\s+types?)"
            r"(?:\s+(?:supported\s+)?for\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:what|which)\s+(?P<items>(?:document|file)\s+formats?)\s+"
            r"(?:are\s+)?(?:available|supported)(?:\s+for\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:list|name|show)\s+(?:the\s+)?(?P<items>(?:document|file)\s+formats?)"
            r"(?:\s+(?:supported\s+)?for\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:what|which)\s+(?P<items>(?:test|pytest|suite)\s+markers?)\s+"
            r"(?:are\s+)?(?:available|defined|registered|supported)(?:\s+(?:in|for|by)\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:list|name|show)\s+(?:the\s+)?(?P<items>(?:test|pytest|suite)\s+markers?)"
            r"(?:\s+(?:in|for|used\s+by)\s+(?P<context>.+))?$",
            re.I,
        ),
    )
    for pattern in patterns:
        match = pattern.match(q)
        if match is None:
            continue
        context = clean_phrase(match.groupdict().get("context") or "") or None
        return _inventory_frame(match.group("items"), context)

    russian = re.match(
        r"^(?:какие|перечисли|назови)\s+(?P<items>типы\s+источников|форматы\s+(?:документов|файлов)|"
        r"pytest[- ]?маркеры|тестовые\s+маркеры|маркеры\s+тестов)"
        r"(?:\s+(?:поддерживаются|доступны|зарегистрированы)(?:\s+для\s+(?P<context>.+))?)?$",
        q,
        re.I,
    )
    if russian is not None:
        context = clean_phrase(russian.group("context") or "") or None
        return _inventory_frame(russian.group("items"), context)
    return None


def match_requirements_frame(question: str) -> RequirementsFrame | None:
    q = clean_phrase(question)
    patterns = (
        r"^what\s+does\s+(?:the\s+)?(.+?)\s+require$",
        r"^what\s+is\s+required\s+by\s+(?:the\s+)?(.+)$",
        r"^what\s+are\s+the\s+requirements\s+for\s+(?:the\s+)?(.+)$",
        r"^what\s+must\s+(?:the\s+)?(.+?)\s+(?:include|contain|do)$",
        r"^что\s+требуется\s+для\s+(.+)$",
        r"^какие\s+требования\s+(?:есть\s+)?для\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, q, re.I)
        if match is not None:
            subject = clean_phrase(match.group(1))
            if subject:
                return RequirementsFrame(subject)
    return None


_SYNC_ACTION_RE = re.compile(
    r"\b(?:sync|synchronize|refresh|update|reindex)\s+(?:the\s+)?"
    r"(?:project\s+docs?(?:\s+index)?|project\s+documentation(?:\s+index)?)\b"
    r"|\b(?:синхронизир(?:овать|уй)|обновить|обнови|переиндексир(?:овать|уй))\b[^?]{0,60}"
    r"\b(?:документац(?:ию|ия|ии)\s+проекта|проектн(?:ую|ой)\s+документац(?:ию|ии))\b",
    re.I,
)


def match_action_frame(question: str) -> ActionFrame | None:
    q = clean_phrase(question)
    english = re.match(
        r"^(?:how\s+(?:do|should|can)\s+i|what\s+(?:command|call)\s+should\s+i\s+use\s+to)\s+(.+)$",
        q,
        re.I,
    )
    russian = re.match(r"^как\s+(?:мне\s+)?(.+)$", q, re.I)
    action = english or russian
    if action is None:
        return None
    surface = clean_phrase(action.group(1))
    if _SYNC_ACTION_RE.search(surface):
        return ActionFrame("sync_project_docs", surface)
    return None


def ambiguous_frame_reason(question: str) -> str | None:
    """Return a fail-closed reason for intentionally ambiguous surface forms."""

    q = clean_phrase(question)
    if re.match(
        r"^(?:(?:what|which)\s+markers?\b|(?:list|name|show)\s+(?:the\s+)?markers?\b)",
        q,
        re.I,
    ):
        return "unresolved_inventory_category:markers"
    if re.match(
        r"^(?:(?:what|which)\s+formats?\b|(?:list|name|show)\s+(?:the\s+)?formats?\b)",
        q,
        re.I,
    ):
        return "unresolved_inventory_category:formats"

    action_prefix = re.match(
        r"^(?:how\s+(?:do|should|can)\s+i|what\s+(?:command|call)\s+should\s+i\s+use\s+to)\s+(.+)$",
        q,
        re.I,
    )
    if action_prefix is not None:
        surface = clean_phrase(action_prefix.group(1)).casefold()
        if re.search(r"\bdocs?\s+index\b", surface) and not re.search(
            r"\bproject\s+(?:docs?|documentation)(?:\s+index)?\b",
            surface,
        ):
            return "unresolved_requested_operation"
    return None


__all__ = [
    "ActionFrame", "InventoryFrame", "RequirementsFrame", "ambiguous_frame_reason",
    "clean_phrase", "match_action_frame", "match_inventory_frame",
    "match_requirements_frame", "split_question_clauses",
]
