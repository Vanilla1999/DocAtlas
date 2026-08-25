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
class QuestionClause:
    """An exact, non-empty source span that may contain one semantic clause."""

    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if (
            self.start < 0
            or self.end <= self.start
            or len(self.text) != self.end - self.start
        ):
            raise ValueError("invalid question clause span")


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
    context: str | None = None


_STRONG_QUESTION_START = (
    r"(?:what|which|how|when|where|why|who|list|name|show|tell|"
    r"calculate|prescribe|что|какие|как|когда|где|почему|кто|"
    r"перечисли|назови|расскажи)\b"
)
_QUESTION_START = (
    r"(?:what|which|how|when|where|why|who|can|could|does|do|is|are|should|"
    r"list|name|show|tell|calculate|prescribe|"
    r"что|какие|как|когда|где|почему|кто|перечисли|назови|расскажи)\b"
)
_ACTION_START = (
    r"(?:rebuild|calculate|prescribe|tell(?:ing)?|show(?:ing)?|list(?:ing)?|name|"
    r"sync|synchronize|update|refresh|reindex|run|verify|audit|check|compare|"
    r"configure|install|delete|remove|start|launch|fetch|explain|"
    r"пересобери|расскажи|покажи|перечисли|синхронизируй|обнови|"
    r"переиндексируй|запусти|проверь|удали)\b"
)
_REQUEST_WRAPPER_RE = re.compile(
    r"^\s*(?:"
    r"according\s+to\s+the\s+project\s+documentation\s*[,;:]?\s*|"
    r"(?:please|пожалуйста)\s*[,;:]?\s*|"
    r"(?:(?:could|can|would)\s+you(?:\s+please)?|"
    r"(?:можешь|могли\s+бы\s+вы)(?:\s+пожалуйста)?)"
    r"\s*[,;:]?\s*(?:(?:tell|show)\s+me\s+|"
    r"(?:расскажи|покажи)\s+)?"
    r")",
    re.I,
)

# A boundary is recognized only when its right-hand side starts another
# question/action-like unit.  This keeps noun coordination (``sections and
# chunks``) intact while making punctuation choice irrelevant for compound
# safety.  The exact source offsets are retained instead of returning cleaned
# strings and attempting to reconstruct their location later.
_CLAUSE_BOUNDARY_RE = re.compile(
    rf"(?P<separator>"
    rf"(?:\r?\n{{2,}}|(?:\r?\n+)(?=(?:{_STRONG_QUESTION_START}|{_ACTION_START})))|"
    rf"(?:\s*[;!?]+\s*)|"
    rf"(?:\s*[,/:\u2013\u2014]+\s*)|"
    rf"(?:\.\s+)|"
    rf"(?:\s+\b(?:and\s+also|while\s+also|as\s+well\s+as|along\s+with|"
    rf"and|but|plus|then|also|и\s+также|а\s+также|и|но|плюс|затем)\b\s+)"
    rf")(?P<head>(?:{_QUESTION_START})|(?:{_ACTION_START})(?=\s+\S))",
    re.I,
)


def clean_phrase(value: str) -> str:
    value = " ".join(str(value or "").strip(" ?!.,:;").split())
    return re.sub(r"^(?:the|a|an|этот|эта|это)\s+", "", value, flags=re.I)[:180]


def strip_request_wrapper(value: str) -> str:
    """Remove one bounded politeness wrapper without changing intent text."""

    return _REQUEST_WRAPPER_RE.sub("", str(value or ""), count=1)


def _trim_clause(question: str, start: int, end: int) -> QuestionClause | None:
    while start < end and question[start].isspace():
        start += 1
    while end > start and question[end - 1].isspace():
        end -= 1
    if start >= end:
        return None
    return QuestionClause(question[start:end], start, end)


def split_question_clause_spans(question: str) -> tuple[QuestionClause, ...]:
    """Return exact clause candidates without losing source coordinates."""

    value = str(question or "")
    if not value.strip():
        return ()

    clauses: list[QuestionClause] = []
    cursor = 0
    for match in _CLAUSE_BOUNDARY_RE.finditer(value):
        wrapper_prefix = value[cursor:match.start("head")]
        if wrapper_prefix and not strip_request_wrapper(wrapper_prefix).strip():
            continue
        clause = _trim_clause(value, cursor, match.start("separator"))
        if clause is not None:
            clauses.append(clause)
        cursor = match.start("head")
    final = _trim_clause(value, cursor, len(value))
    if final is not None:
        clauses.append(final)
    return tuple(clauses)


def split_question_clauses(question: str) -> tuple[str, ...]:
    """Compatibility wrapper returning normalized clause text only."""

    return tuple(
        cleaned
        for clause in split_question_clause_spans(question)
        if (cleaned := clean_phrase(clause.text))
    )


def _inventory_frame(items: str, context: str | None) -> InventoryFrame:
    raw = items.casefold()
    if "marker" in raw or "маркер" in raw:
        return InventoryFrame("test suite", "marker", "marker", context)
    if "format" in raw or "формат" in raw:
        return InventoryFrame("file formats", "file format", "format", context or "indexing")
    return InventoryFrame("source types", "source", "source", context or "indexing")


_INDEXING_CONTEXT = (
    r"(?:indexing|project\s+indexing|document\s+indexing|"
    r"the\s+(?:project\s+|document\s+)?index|"
    r"индексац(?:ии|ия|ию)|индексации\s+(?:проекта|документов))"
)
_MARKER_CONTEXT = (
    r"(?:pytest|docatlas|the\s+(?:project\s+|offline\s+)?(?:test\s+)?suite|"
    r"(?:project\s+|offline\s+)?(?:test\s+)?suite|"
    r"pytest[- ]?suite|набор(?:а|е)?\s+тестов|тестов(?:ого|ой)?\s+набора)"
)
_STRONG_REQUEST_HEAD_RE = re.compile(
    r"\b(?:what|which|how|when|where|why|who|tell(?:ing)?|show(?:ing)?|"
    r"list(?:ing)?|name|calculate|prescribe|can\s+you|could\s+you|"
    r"do\s+you|is\s+there|are\s+there|should\s+i|"
    r"что|какие|как|когда|где|почему|кто|расскажи|покажи|перечисли|"
    r"посчитай)\b",
    re.I,
)
_DISCOURSE_SWITCH_RE = re.compile(
    r"\b(?:by\s+the\s+way|besides\s+that|another\s+thing|one\s+more\s+"
    r"question|also\s+tell|and\s+also|while\s+also|plus\s+also|"
    r"кстати|ещ[её]\s+один\s+вопрос|а\s+также|помимо\s+этого)\b",
    re.I,
)
_COORDINATED_DESTRUCTIVE_REQUEST_RE = re.compile(
    r"\b(?:and|и)\s+(?:delete|remove|drop|удал(?:и|ить|яй))\s+"
    r"(?:all|everything|files?|вс[её]|файлы?)\b",
    re.I,
)


def semantic_tail_is_safe(
    value: str,
    *,
    allow_initial_request_head: bool = False,
) -> bool:
    """Reject text that contains evidence of another independent request."""

    raw = str(value or "").strip()
    if not raw:
        return True
    if re.search(r"(?:[,;:](?=\s|[A-ZА-ЯЁ])|[\u2013\u2014]|\s/\s|[!?])", raw):
        return False
    if _DISCOURSE_SWITCH_RE.search(raw):
        return False
    if _COORDINATED_DESTRUCTIVE_REQUEST_RE.search(raw):
        return False
    for match in _STRONG_REQUEST_HEAD_RE.finditer(raw):
        if allow_initial_request_head and not raw[:match.start()].strip():
            continue
        return False
    return True


def match_inventory_frame(question: str) -> InventoryFrame | None:
    q = clean_phrase(question)
    patterns = (
        re.compile(
            rf"^(?:what|which)\s+(?P<items>source\s+types?)\s+"
            rf"(?:are\s+)?(?:available|supported)(?:\s+for\s+(?P<context>{_INDEXING_CONTEXT}))?$",
            re.I,
        ),
        re.compile(
            rf"^(?:list|name|show)\s+(?:the\s+)?(?P<items>source\s+types?)"
            rf"(?:\s+(?:supported\s+)?for\s+(?P<context>{_INDEXING_CONTEXT}))?$",
            re.I,
        ),
        re.compile(
            rf"^(?:what|which)\s+(?P<items>(?:document|file)\s+formats?)\s+"
            rf"(?:are\s+)?(?:available|supported)(?:\s+for\s+(?P<context>{_INDEXING_CONTEXT}))?$",
            re.I,
        ),
        re.compile(
            rf"^(?:list|name|show)\s+(?:the\s+)?(?P<items>(?:document|file)\s+formats?)"
            rf"(?:\s+(?:supported\s+)?for\s+(?P<context>{_INDEXING_CONTEXT}))?$",
            re.I,
        ),
        re.compile(
            rf"^(?:what|which)\s+(?P<items>(?:test|pytest|suite)\s+markers?)\s+"
            rf"(?:are\s+)?(?:available|defined|registered|supported)"
            rf"(?:\s+(?:in|for|by)\s+(?P<context>{_MARKER_CONTEXT}))?$",
            re.I,
        ),
        re.compile(
            rf"^(?:list|name|show)\s+(?:the\s+)?(?P<items>(?:test|pytest|suite)\s+markers?)"
            rf"(?:\s+(?:in|for|used\s+by)\s+(?P<context>{_MARKER_CONTEXT}))?$",
            re.I,
        ),
    )
    for pattern in patterns:
        match = pattern.fullmatch(q)
        if match is None:
            continue
        context = clean_phrase(match.groupdict().get("context") or "") or None
        if context is not None and not semantic_tail_is_safe(context):
            return None
        return _inventory_frame(match.group("items"), context)

    russian = re.fullmatch(
        rf"(?:какие|перечисли|назови)\s+(?P<items>типы\s+источников|"
        rf"форматы\s+(?:документов|файлов)|pytest[- ]?маркеры|"
        rf"тестовые\s+маркеры|маркеры\s+тестов)"
        rf"(?:\s+(?:поддерживаются|доступны|зарегистрированы)"
        rf"(?:\s+для\s+(?P<context>{_INDEXING_CONTEXT}|{_MARKER_CONTEXT}))?)?",
        q,
        re.I,
    )
    if russian is not None:
        context = clean_phrase(russian.group("context") or "") or None
        if context is not None and not semantic_tail_is_safe(context):
            return None
        return _inventory_frame(russian.group("items"), context)
    return None


def match_requirements_frame(question: str) -> RequirementsFrame | None:
    q = clean_phrase(question)
    patterns = (
        r"what\s+does\s+(?:the\s+)?(.+?)\s+require",
        r"what\s+is\s+required\s+by\s+(?:the\s+)?(.+)",
        r"what\s+are\s+the\s+requirements\s+for\s+(?:the\s+)?(.+)",
        r"what\s+must\s+(?:the\s+)?(.+?)\s+(?:include|contain|do)",
        r"что\s+требуется\s+для\s+(.+)",
        r"какие\s+требования\s+(?:есть\s+)?для\s+(.+)",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, q, re.I)
        if match is not None:
            subject = clean_phrase(match.group(1))
            if subject and semantic_tail_is_safe(
                subject,
                allow_initial_request_head=True,
            ):
                return RequirementsFrame(subject)
    return None


_EN_SYNC_SURFACE_RE = re.compile(
    r"(?P<verb>sync|synchronize|refresh|update|reindex)\s+(?:the\s+)?"
    r"(?:project\s+docs?(?:\s+index)?|project\s+documentation(?:\s+index)?)"
    r"(?:\s+(?P<context>"
    r"after\s+(?:(?:changing|editing|updating|modifying)\s+"
    r"(?:a\s+|the\s+)?file|file\s+changes)|"
    r"when\s+(?:a\s+|the\s+)?file\s+changes"
    r"))?",
    re.I,
)
_RU_SYNC_SURFACE_RE = re.compile(
    r"(?:синхронизир(?:овать|уй)|обновить|обнови|переиндексир(?:овать|уй))\s+"
    r"(?:документац(?:ию|ия|ии)\s+проекта|"
    r"проектн(?:ую|ой)\s+документац(?:ию|ии))"
    r"(?:\s+(?P<context>после\s+(?:изменения|редактирования|обновления)\s+"
    r"файла))?",
    re.I,
)


def match_action_frame(question: str) -> ActionFrame | None:
    q = clean_phrase(question)
    english = re.fullmatch(
        r"(?:how\s+(?:do|should|can)\s+i|"
        r"what\s+(?:command|call)\s+should\s+i\s+use\s+to)\s+(.+)",
        q,
        re.I,
    )
    russian = re.fullmatch(r"как\s+(?:мне\s+)?(.+)", q, re.I)
    action = english or russian
    if action is None:
        return None
    surface = clean_phrase(action.group(1))
    sync = _EN_SYNC_SURFACE_RE.fullmatch(surface) or _RU_SYNC_SURFACE_RE.fullmatch(surface)
    if sync is not None:
        context = clean_phrase(sync.groupdict().get("context") or "") or None
        if context is not None and not semantic_tail_is_safe(context):
            return None
        return ActionFrame("sync_project_docs", surface, context)
    return None


def ambiguous_frame_reason(question: str) -> str | None:
    """Return a fail-closed reason for intentionally ambiguous surface forms."""

    q = clean_phrase(question)
    if re.match(
        r"^(?:(?:what|which)\s+markers?\b|(?:list|name|show)\s+(?:the\s+)?markers?\b|"
        r"(?:какие|перечисли|назови)\s+маркеры\b)",
        q,
        re.I,
    ):
        return "unresolved_inventory_category:markers"
    if re.match(
        r"^(?:(?:what|which)\s+formats?\b|(?:list|name|show)\s+(?:the\s+)?formats?\b|"
        r"(?:какие|перечисли|назови)\s+форматы\b)",
        q,
        re.I,
    ):
        return "unresolved_inventory_category:formats"

    action_prefix = re.match(
        r"^(?:how\s+(?:do|should|can)\s+i|"
        r"what\s+(?:command|call)\s+should\s+i\s+use\s+to)\s+(.+)$",
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

    russian_action = re.match(r"^как\s+(?:мне\s+)?(.+)$", q, re.I)
    if russian_action is not None:
        surface = clean_phrase(russian_action.group(1)).casefold()
        if re.search(r"\bиндекс(?:а|у|ом|е)?\s+документац", surface) and not re.search(
            r"(?:документац\w*\s+проекта|проектн\w*\s+документац)",
            surface,
        ):
            return "unresolved_requested_operation"
    return None


__all__ = [
    "ActionFrame", "InventoryFrame", "QuestionClause", "RequirementsFrame",
    "ambiguous_frame_reason", "clean_phrase", "match_action_frame",
    "match_inventory_frame", "match_requirements_frame",
    "semantic_tail_is_safe", "split_question_clause_spans",
    "split_question_clauses", "strip_request_wrapper",
]
