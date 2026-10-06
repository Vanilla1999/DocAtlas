"""Compatibility preferences without semantic request-part or stopping rules."""
from __future__ import annotations

import re
from typing import FrozenSet


def recognized_request_parts(question: str) -> FrozenSet[str]:
    return frozenset()


def visible_request_parts(question: str, text: str) -> FrozenSet[str]:
    return frozenset()


def direct_evidence_preference(question: str, text: str) -> tuple[int, int, int, int]:
    return (0, 0, 0, 0)


def recognized_request_satisfied(question: str, text: str) -> bool:
    # Unknown completeness never short-circuits bounded source selection.
    return False


def _complete_fence(text: str) -> bool:
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    opening = re.match(r"^\s*(`{3,}|~{3,})", lines[0])
    return bool(opening and re.fullmatch(r"\s*" + re.escape(opening[1]) + r"\s*", lines[-1]))


def _is_question_echo(question: str, text: str) -> bool:
    return bool(question.strip() and " ".join(question.split()) == " ".join(text.split()))


__all__ = ["direct_evidence_preference", "recognized_request_parts",
           "recognized_request_satisfied", "visible_request_parts"]
