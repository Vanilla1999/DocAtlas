"""Lexical identity boundaries shared by context qualification and ranking."""
from __future__ import annotations

import re


def technical_term_pattern(term: str, *, exact: bool = True) -> str:
    """Do not count a suffix of a hyphenated/dotted identifier as another name.

    A sentence-final dot is punctuation, whereas ``.member`` extends a symbol.
    Non-exact retrieval still requires the literal spelling, not inflection.
    """
    technical = bool(re.search(r"[_-]|\w\.\w", term))
    left = r"(?<![\w.-])" if technical else r"(?<![\w-])" if exact else r"(?<!\w)"
    right = r"(?![\w-]|\.\w)" if technical else r"(?![\w-])" if exact else r"(?!\w)"
    return left + re.escape(term) + right
