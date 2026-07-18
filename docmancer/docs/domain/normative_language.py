"""Deterministic classification of source-backed normative language."""
from __future__ import annotations

import re
from typing import Literal

NormativeModality = Literal["forbidden", "required"]

_FORBIDDEN_RE = re.compile(
    r"\b(?:must\s+not|may\s+not|cannot|do\s+not|don't|never|forbidden|prohibited)\b",
    re.IGNORECASE,
)
_REQUIRED_RE = re.compile(
    r"\b(?:must|required|requires|shall|invariant|is\s+reserved\s+for|"
    r"only\s+(?:after|before|when|if)|is\s+allowed\s+only)\b",
    re.IGNORECASE,
)
_DEFINITION_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+|"
    r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s+means\b",
    re.IGNORECASE,
)
_NOT_REQUIRED_RE = re.compile(
    r"\b(?:not|required\s+not\s+to)\s+required\b", re.IGNORECASE
)
_CODE_DECLARATION_RE = re.compile(
    r"^\s*(?:(?:async\s+)?def|class|import|from)\b", re.IGNORECASE
)


def classify_normative_modality(value: str) -> NormativeModality | None:
    """Return a bounded domain modality without interpreting or paraphrasing text."""

    text = str(value or "")
    if _CODE_DECLARATION_RE.search(text):
        return None
    if _FORBIDDEN_RE.search(text):
        return "forbidden"
    if (_REQUIRED_RE.search(text) and not _NOT_REQUIRED_RE.search(text)) or _DEFINITION_RE.search(text):
        return "required"
    return None


def has_normative_language(value: str) -> bool:
    return classify_normative_modality(value) is not None
