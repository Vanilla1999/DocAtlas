"""Bounded verbatim Latin phrases inside an otherwise non-Latin request.

These are optional retrieval hints, not translations, semantic rewrites or proof
of the whole question. Offsets delimit original text; no words are manufactured.
"""
from __future__ import annotations

import re
import unicodedata

_RUN = re.compile(r"(?<![\w.])(?:[A-Za-z][A-Za-z0-9_-]*[ \t]+){1,3}[A-Za-z][A-Za-z0-9_-]*(?![\w.])")
_MAX_INPUT = 5000
_MAX_RUNS = 2
_MAX_CHARS = 160


def mixed_script_phrases(question: str) -> tuple[str, ...]:
    """Extract at most two literal multiword hints without changing the request."""
    if not isinstance(question, str) or len(question) > _MAX_INPUT:
        return ()
    if not any(c.isalpha() and "LATIN" not in unicodedata.name(c, "") for c in question):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for match in _RUN.finditer(question):
        text = match.group()
        key = text.casefold()
        if len(text) > _MAX_CHARS or key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= _MAX_RUNS:
            break
    return tuple(result)
