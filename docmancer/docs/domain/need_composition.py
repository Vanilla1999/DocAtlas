"""Literal masking and legacy composition DTOs, without NL interpretation."""
from __future__ import annotations
from dataclasses import dataclass
import re

_PROTECTED = re.compile(
    r'(?P<tick>`+)(?:(?!(?P=tick)).)*(?P=tick)'
    r'|"[^"\n]*"|(?<!\w)\'[^\'\n]+\''
    r'|\[[^\]\n]*\]\([^\n]*?\)', re.S)


def mask_protected(question: str) -> str:
    """Hide quotation/link separators, not their bytes or positions."""
    return _PROTECTED.sub(lambda m: 'x' * len(m[0]), question)


def independent_sentence_spans(question: str) -> tuple[tuple[int, int], ...]:
    """Punctuation cannot certify independent requests or semantic scope."""
    return ()


@dataclass(frozen=True, slots=True)
class ComposedPart:
    """Explicit proposal DTO, not source proof or a prose-derived contract."""
    start: int
    end: int
    relation: str
    focus: tuple[tuple[int, int], ...]
    constraints: tuple[tuple[int, int], ...] = ()
    alternatives: tuple[tuple[int, int], ...] = ()
    categories: tuple[tuple[int, int], ...] = ()
    requirement: str = 'scalar'
    expected_count: int | None = None
    prerequisite: int | None = None


def _trim_span(question: str, start: int, end: int, *, article: bool = False) -> tuple[int, int]:
    # Retain structural trimming, but never erase natural-language articles.
    while start < end and question[start].isspace():
        start += 1
    while end > start and (question[end - 1].isspace() or question[end - 1] in ',.?!'):
        end -= 1
    return start, end


def _condition_spans(question: str, masked: str, *, end: int | None = None):
    return ()


def _plain_span(question: str, span: tuple[int, int]) -> bool:
    return False


def _set_part(question: str, masked: str) -> tuple[ComposedPart, ...]:
    return ()


def compositional_parts(question: str) -> tuple[ComposedPart, ...]:
    """Untyped text supplies no relation, count, condition, or dependency."""
    return ()
