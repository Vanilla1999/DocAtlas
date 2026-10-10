"""Exact structural question spans and explicit legacy frame DTOs.

Structure is not a certificate of independent requests or semantic coverage.
Natural-language heads, wrappers, conjunctions, and domain identities are not
interpreted here.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from .need_composition import mask_protected

InventoryKind = Literal["source", "format", "marker"]


@dataclass(frozen=True, slots=True)
class QuestionClause:
    """An exact, non-empty source span, without semantic authority."""
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


def clean_phrase(value: str) -> str:
    return " ".join(str(value or "").strip(" ?!.,:;").split())[:180]


def strip_request_wrapper(value: str) -> str:
    """Compatibility identity: no natural-language wrapper is erased."""
    return str(value or "")


def _trim_clause(question: str, start: int, end: int) -> QuestionClause | None:
    while start < end and question[start].isspace():
        start += 1
    while end > start and question[end - 1].isspace():
        end -= 1
    if start >= end:
        return None
    return QuestionClause(question[start:end], start, end)


def split_question_clause_spans(question: str) -> tuple[QuestionClause, ...]:
    """Return paragraph spans only; quoted/link delimiters stay protected."""
    value = str(question or "")
    masked = mask_protected(value)
    clauses: list[QuestionClause] = []
    cursor = 0
    for match in re.finditer(r"\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*", masked):
        clause = _trim_clause(value, cursor, match.start())
        if clause is not None:
            clauses.append(clause)
        cursor = match.end()
    final = _trim_clause(value, cursor, len(value))
    if final is not None:
        clauses.append(final)
    return tuple(clauses)


def split_question_clauses(question: str) -> tuple[str, ...]:
    return tuple(
        cleaned for clause in split_question_clause_spans(question)
        if (cleaned := clean_phrase(clause.text))
    )


def semantic_tail_is_safe(
    value: str,
    *,
    allow_initial_request_head: bool = False,
) -> bool:
    """Only absence of text is certified; nonempty untyped tails are unknown."""
    return not str(value or "").strip()


def match_inventory_frame(question: str) -> InventoryFrame | None:
    return None


def _inventory_frame(items: str, context: str | None) -> InventoryFrame:
    raise ValueError("untyped inventory category is unresolved")


def match_requirements_frame(question: str) -> RequirementsFrame | None:
    return None


def match_action_frame(question: str) -> ActionFrame | None:
    return None


def ambiguous_frame_reason(question: str) -> str | None:
    return "unresolved_question_semantics" if str(question or "").strip() else None


__all__ = [
    "ActionFrame", "InventoryFrame", "QuestionClause", "RequirementsFrame",
    "ambiguous_frame_reason", "clean_phrase", "match_action_frame",
    "match_inventory_frame", "match_requirements_frame",
    "semantic_tail_is_safe", "split_question_clause_spans",
    "split_question_clauses", "strip_request_wrapper",
]
