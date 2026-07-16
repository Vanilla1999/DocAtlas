"""Shared deterministic request-intent predicates for routing and projection."""

from __future__ import annotations

import re


_CHANGE_WORDS = re.compile(
    r"\b(implement|create|build|write|develop|introduce|replace|add|change|edit|modify|fix|"
    r"refactor|remove|rename|update|patch|migrate|code|"
    r"реализ\w*|созда\w*|сдела\w*|напиш\w*|разработ\w*|добав\w*|измен\w*|"
    r"исправ\w*|рефактор\w*|замен\w*|удал\w*|переимен\w*|обнов\w*)\b",
    re.IGNORECASE,
)
_DOCUMENTATION_PREFIX = re.compile(
    r"^\s*(how|what|why|where|when|show|explain|describe|как|что|почему|где|когда|"
    r"покажи|объясни|опиши)\b",
    re.IGNORECASE,
)


def is_change_request(question: str) -> bool:
    """Return true only for an explicit change imperative, not a how-to question."""

    text = str(question or "").strip()
    if not text or _DOCUMENTATION_PREFIX.search(text):
        return False
    return bool(_CHANGE_WORDS.search(text))


def model_projection_kind(question: str) -> str:
    return "patch_context" if is_change_request(question) else "docs_answer"
