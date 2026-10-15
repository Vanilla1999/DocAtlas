"""Conservative legacy relation-witness adapter, without semantic dictionaries."""
from __future__ import annotations

from .admission_grammar import ParsedMeaning


def relation_local_witness(
    frame: ParsedMeaning, text: str,
) -> tuple[bool | None, tuple[tuple[int, int], ...]]:
    """A supplied frame and source quote are not independent entailment proof."""
    return False, ()
