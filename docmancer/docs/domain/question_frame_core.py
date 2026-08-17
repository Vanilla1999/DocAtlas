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

InventoryKind = Literal["source", "marker"]


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


_CLAUSE_START = (
    r"(?:what|which|how|when|where|why|who|can|could|does|do|is|are|should|"
    r"list|name|show|tell|calculate|prescribe|"
    r"что|какие|как|когда|где|почему|перечисли|назови)\b"
)
_CLAUSE_SPLIT_RE = re.compile(
    rf"\s*(?:,\s*)?(?:and|but|и|но)\s+(?={_CLAUSE_START})",
    re.I,
)


def clean_phrase(value: str) -> str:
    value = " ".join(str(value or "").strip(" ?!.,:").split())
    return re.sub(r"^(?:the|a|an|этот|эта|это)\s+", "", value, flags=re.I)[:180]


def split_question_clauses(question: str) -> tuple[str, ...]:
    """Split only explicit conjunctions that start a new question-like clause."""

    value = " ".join(str(question or "").split()).strip()
    if not value:
        return ()
    parts = [clean_phrase(part) for part in _CLAUSE_SPLIT_RE.split(value)]
    return tuple(part for part in parts if part)


def match_inventory_frame(question: str) -> InventoryFrame | None:
    q = clean_phrase(question)
    patterns = (
        re.compile(
            r"^(?:what|which)\s+(?P<items>source\s+types?|document\s+formats?|file\s+formats?)\s+"
            r"(?:are\s+)?(?:available|supported)(?:\s+for\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:list|name|show)\s+(?:the\s+)?(?P<items>source\s+types?|document\s+formats?|file\s+formats?)"
            r"(?:\s+(?:supported\s+)?for\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:what|which)\s+(?P<items>(?:test|pytest|suite)\s+markers?|markers?)\s+"
            r"(?:are\s+)?(?:available|defined|registered|supported)(?:\s+(?:in|for|by)\s+(?P<context>.+))?$",
            re.I,
        ),
        re.compile(
            r"^(?:list|name|show)\s+(?:the\s+)?(?P<items>(?:test|pytest|suite)\s+markers?|markers?)"
            r"(?:\s+(?:in|for|used\s+by)\s+(?P<context>.+))?$",
            re.I,
        ),
    )
    for pattern in patterns:
        match = pattern.match(q)
        if match is None:
            continue
        raw = match.group("items").casefold()
        context = clean_phrase(match.groupdict().get("context") or "") or None
        if "marker" in raw:
            return InventoryFrame("test suite", "marker", "marker", context)
        return InventoryFrame("source types", "source", "source", context or "indexing")

    russian = re.match(
        r"^(?:какие|перечисли|назови)\s+(?P<items>типы\s+источников|форматы\s+(?:документов|файлов)|"
        r"pytest[- ]?маркеры|тестовые\s+маркеры|маркеры\s+тестов)"
        r"(?:\s+(?:поддерживаются|доступны|зарегистрированы)(?:\s+для\s+(?P<context>.+))?)?$",
        q,
        re.I,
    )
    if russian is not None:
        raw = russian.group("items").casefold()
        context = clean_phrase(russian.group("context") or "") or None
        if "маркер" in raw:
            return InventoryFrame("test suite", "marker", "marker", context)
        return InventoryFrame("source types", "source", "source", context or "indexing")
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
    r"\b(?:sync|synchronize|refresh|update|reindex)\s+(?:the\s+)?(?:project\s+docs?|project\s+documentation|docs?\s+index)\b"
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
    action = (english or russian)
    if action is None:
        return None
    surface = clean_phrase(action.group(1))
    if _SYNC_ACTION_RE.search(surface):
        return ActionFrame("sync_project_docs", surface)
    return None


__all__ = [
    "ActionFrame", "InventoryFrame", "RequirementsFrame", "clean_phrase",
    "match_action_frame", "match_inventory_frame", "match_requirements_frame",
    "split_question_clauses",
]
