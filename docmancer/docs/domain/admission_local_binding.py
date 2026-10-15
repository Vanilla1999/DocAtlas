"""Compatibility hooks without inferred natural-language default bindings.

Literal answer units remain available through answer_units. A subject/property
co-occurrence, heading, condition or anaphora is not a local relation witness.
Unknown forms stay explicit; callers must not turn None into semantic credit.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .answer_units import AnswerUnit
from .technical_tokens import technical_term_pattern

_WORD = r"[A-Za-z][A-Za-z0-9_-]*"  # Retained technical identifier syntax.
_STATE = re.compile(r"(?!)")  # Nonmatching former NL-condition adapter.


def default_property(query: Mapping[str, Any]) -> str | None:
    """No property nomination from NL words or supplied semantic metadata."""
    return None


def _subject_pattern(subject: str) -> str:
    return technical_term_pattern(subject, exact=True)


def _property_pattern(attribute: str, *, plural: bool = False) -> str:
    """Escape caller-supplied literal syntax, without guessed inflections."""
    words = attribute.split()
    if not words:
        return r"(?!)"
    return r"(?<![\w-])" + r"\s+".join(re.escape(word) for word in words) + r"(?![\w-])"


def _assignment(attribute: str, subject: str | None) -> str:
    """Nonmatching adapter: NL ownership/default clauses are not assignments."""
    return r"(?P<value>(?!))"


def _single_clause(text: str) -> bool:
    """Structural boundary check only; a single clause does not prove meaning."""
    return not re.search(r"[;\n]|[.!?]\s+\S", text)


def _condition(text: str) -> tuple[str, str] | None:
    return None


def _conditioned_clause(text: str, required: tuple[str, str] | None) -> str | None:
    return None


def _value_is_local(match: re.Match[str] | None, attribute: str) -> bool:
    return False


def _discourse_value_is_local(answer: str, attribute: str) -> bool:
    return False


def bound_default_units(
    query: Mapping[str, Any], text: str,
) -> tuple[AnswerUnit, ...] | None:
    """Unknown NL binding, not an empty supported set or a guessed proposition."""
    return None


def default_local_witness(query: Mapping[str, Any], text: str
                          ) -> tuple[bool | None, tuple[tuple[int, int], ...]]:
    """Preserve the tri-state ABI; no supported default relation is inferred."""
    return None, ()


__all__ = ["bound_default_units", "default_property", "default_local_witness"]
