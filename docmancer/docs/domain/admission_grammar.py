"""Compatibility shapes without a natural-language semantic grammar.

Literal spans can be retained by callers. They do not certify paraphrase
equivalence, requested answer shape, or authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class MeaningSlot:
    role: str
    start: int
    end: int
    text: str
    canonical: str


@dataclass(frozen=True, slots=True)
class ParsedMeaning:
    operator: str
    arguments: tuple[MeaningSlot, ...]
    constraints: tuple[MeaningSlot, ...] = ()

    @property
    def subject(self) -> str:
        for role in ('subject', 'left', 'attribute'):
            for slot in self.arguments:
                if slot.role == role:
                    return slot.text.strip('`"')
        return ''


# Retained protocol identifiers, not a vocabulary or parser rule table.
NEW_RELATIONS = frozenset({'precedence', 'enumeration', 'mapping', 'temporal_order', 'callable_form'})


def canonical_phrase(value: str) -> str:
    """Literal identity only; no translation, stemming or semantic aliases."""
    return value


def ordered_list_spans(text: str) -> tuple[tuple[int, int], ...]:
    """No inferred natural-language enumeration contract."""
    return ()


@lru_cache(maxsize=256)
def parse_admission_frame(question: str) -> ParsedMeaning | None:
    return None
