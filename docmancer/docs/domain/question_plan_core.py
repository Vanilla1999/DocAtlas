"""QuestionPlan data model, normalization, and source-span binding helpers."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Callable, Literal

from docmancer.docs.domain.question_frame_core import (
    QuestionClause,
    clean_phrase,
    semantic_tail_is_safe,
    strip_request_wrapper,
)
from docmancer.docs.domain.technical_terms import TechnicalTermKind, coerce_technical_term

PlanKind = Literal[
    "definition", "purpose", "behavior", "usage", "workflow", "inventory",
    "command", "relation", "comparison", "location", "attribute",
]


@dataclass(frozen=True, slots=True)
class PlannedFacet:
    kind: PlanKind
    subject: str
    relation: str | None = None
    attribute: str | None = None
    target: str | None = None
    value_kind: str = "text"
    expected_value: str | None = None
    item_kind: str | None = None
    response_mode: str = "value"
    context: str | None = None
    subject_kind: TechnicalTermKind | None = None
    subject_aliases: tuple[str, ...] = ()
    span_text: str | None = None
    query_span_start: int | None = None
    query_span_end: int | None = None

    def __post_init__(self) -> None:
        if (self.query_span_start is None) != (self.query_span_end is None):
            raise ValueError("planned facet query span must be complete")
        if (
            self.query_span_start is not None
            and self.query_span_end is not None
            and (self.query_span_start < 0 or self.query_span_end <= self.query_span_start)
        ):
            raise ValueError("planned facet query span is invalid")


@dataclass(frozen=True, slots=True)
class QuestionPlan:
    facets: tuple[PlannedFacet, ...] = ()
    clauses: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()
    parse_trace: tuple[str, ...] = ()
    consumed_spans: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        for start, end in self.consumed_spans:
            if start < 0 or end <= start:
                raise ValueError("question plan consumed span is invalid")

    @property
    def handled(self) -> bool:
        return bool(self.facets or self.unresolved_parts)


Rule = Callable[[str], QuestionPlan | None]


def _clean(value: str) -> str:
    value = " ".join(str(value or "").strip(" ?!.,:").split())
    return re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.I)[:160]


def _technical(
    value: str,
    kind: TechnicalTermKind | None = None,
) -> tuple[str, TechnicalTermKind | None, tuple[str, ...]]:
    value = _clean(value)
    if not value:
        return "", None, ()
    if kind is not None or re.search(r"[_-]|^[A-Z][A-Z0-9_]+$|\.yaml$", value):
        term = coerce_technical_term(value, kind, context=value)
        return term.raw, term.kind, term.aliases
    return value, None, ()


def _normalized_clause(
    clause: QuestionClause,
    *,
    compound: bool = False,
) -> str:
    value = " ".join(clause.text.split())
    value = strip_request_wrapper(value)
    return clean_phrase(value) if compound else value


def _span_pattern(value: str) -> re.Pattern[str] | None:
    tokens = str(value or "").split()
    if not tokens:
        return None
    return re.compile(r"\s+".join(re.escape(token) for token in tokens), re.I)


def _bind_plan_to_clause(plan: QuestionPlan, clause: QuestionClause) -> QuestionPlan:
    """Attach exact source offsets without changing the canonical facet identity."""

    facets: list[PlannedFacet] = []
    cursor = 0
    for facet in plan.facets:
        pattern = _span_pattern(facet.span_text or facet.subject)
        match = pattern.search(clause.text, cursor) if pattern is not None else None
        if match is None and pattern is not None:
            match = pattern.search(clause.text)
        if match is None:
            start, end = clause.start, clause.end
        else:
            start, end = clause.start + match.start(), clause.start + match.end()
            cursor = match.end()
        facets.append(replace(
            facet,
            query_span_start=start,
            query_span_end=end,
        ))
    return replace(
        plan,
        facets=tuple(facets),
        consumed_spans=((clause.start, clause.end),) if facets else (),
    )


def _bind_whole_plan(
    plan: QuestionPlan,
    question: str,
    clauses: tuple[QuestionClause, ...],
) -> QuestionPlan:
    """Bind a frozen whole-question rule while retaining every clause span."""

    whole = QuestionClause(question, 0, len(question))
    bound = _bind_plan_to_clause(plan, whole)
    return replace(
        bound,
        consumed_spans=tuple((clause.start, clause.end) for clause in clauses),
    )


def _unsafe_free_text(
    value: str,
    *,
    allow_initial_request_head: bool = False,
) -> bool:
    """Reject free text that contains evidence of another request."""

    return not semantic_tail_is_safe(
        value,
        allow_initial_request_head=allow_initial_request_head,
    )

__all__ = [
    "PlanKind", "PlannedFacet", "QuestionPlan", "Rule",
    "_bind_plan_to_clause", "_bind_whole_plan", "_clean",
    "_normalized_clause", "_technical", "_unsafe_free_text",
]
