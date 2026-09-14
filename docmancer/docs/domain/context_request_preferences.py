"""Small request-shape preferences for compact context selection; never proof."""
from __future__ import annotations

import re
from typing import FrozenSet

_CODE_REQUEST_RE = re.compile(r"\b(?:code|example|snippet|runnable)\b", re.I)
_SIGNATURE_REQUEST_RE = re.compile(r"\b(?:signature|declaration)\b", re.I)
_FENCE_RE = re.compile(r"^\s*(```|~~~)", re.M)
_SIGNATURE_RE = re.compile(
    r"(?:`[^`\n]*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\([^\n)]*\)"
    r"(?:\s*->\s*[^`\n]+)?`|\b(?:def|class)\s+[A-Za-z_]\w*\s*\()",
    re.I,
)
_DURATION_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|sec(?:ond)?s?|minutes?|mins?)\b",
    re.I,
)
_EXCEPTION_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:Exception|Error|Timeout)\b")
_TIMEOUT_KINDS = ("connect", "pool", "read", "write")


def recognized_request_parts(question: str) -> FrozenSet[str]:
    """Return narrowly recognized requested parts used only for selection order."""
    q = question.casefold()
    parts: set[str] = set()
    if _CODE_REQUEST_RE.search(question):
        parts.add("code_example")
    if _SIGNATURE_REQUEST_RE.search(question):
        parts.add("signature")
    if "timeout" in q and "default" in q:
        parts.add("default_timeout")
        if re.search(r"\b(?:how\s+long|duration|seconds?|minutes?|time)\b", q):
            parts.add("timeout_duration")
        if re.search(r"\b(?:which\s+exception|exception|error)\b", q):
            parts.add("timeout_exception")
    for kind in _TIMEOUT_KINDS:
        if re.search(rf"\b{kind}\b", q) and "timeout" in q:
            parts.add(f"timeout_kind:{kind}")
    origins = re.findall(r"\bfrom\s+([A-Za-z][A-Za-z0-9_.-]*)\b", question, re.I)
    normalized_origins = tuple(dict.fromkeys(origin.casefold() for origin in origins))
    if len(normalized_origins) >= 2 and re.search(
        r"\b(?:same\s+way|differ|difference|compare|versus|vs\.?|unlike)\b", q
    ):
        parts.add("origin_comparison")
        parts.update(f"origin:{origin}" for origin in normalized_origins)
    return frozenset(parts)


def visible_request_parts(question: str, text: str) -> FrozenSet[str]:
    """Return requested parts literally visible in one candidate."""
    requested = recognized_request_parts(question)
    if not requested:
        return frozenset()
    body = text.casefold()
    visible: set[str] = set()
    if "code_example" in requested and _complete_fence(text):
        visible.add("code_example")
    if "signature" in requested and _SIGNATURE_RE.search(text):
        visible.add("signature")
    if "default_timeout" in requested and "timeout" in body and "default" in body:
        visible.add("default_timeout")
    if "timeout_duration" in requested and _DURATION_RE.search(text):
        visible.add("timeout_duration")
    if "timeout_exception" in requested and _EXCEPTION_RE.search(text):
        visible.add("timeout_exception")
    origins = [part.split(":", 1)[1] for part in requested if part.startswith("origin:")]
    for kind in _TIMEOUT_KINDS:
        part = f"timeout_kind:{kind}"
        if part in requested and re.search(rf"\b{kind}\b", body) and "timeout" in body:
            visible.add(part)
    for origin in origins:
        if re.search(rf"(?<![\w-]){re.escape(origin)}(?![\w-])", body):
            visible.add(f"origin:{origin}")
    if "origin_comparison" in requested and origins and all(
        f"origin:{origin}" in visible for origin in origins
    ):
        visible.add("origin_comparison")
    return frozenset(visible)


def direct_evidence_preference(question: str, text: str) -> tuple[int, int, int, int]:
    """Tie-break already-qualified evidence without creating completeness proof."""
    requested = recognized_request_parts(question)
    visible = visible_request_parts(question, text)
    non_echo = int(not _is_question_echo(question, text))
    if "code_example" in requested:
        presentation = 2 if "code_example" in visible else 0
    elif "signature" in requested:
        presentation = 2 if "signature" in visible else 0
    else:
        presentation = 1 if not _FENCE_RE.search(text) else 0
    return (len(visible & requested), non_echo, presentation, -len(text))


def recognized_request_satisfied(question: str, text: str) -> bool:
    """Return a selection stop hint only for a non-empty recognized request shape."""
    requested = recognized_request_parts(question)
    return bool(requested and requested <= visible_request_parts(question, text))


def _complete_fence(text: str) -> bool:
    stripped = text.strip()
    opening = _FENCE_RE.match(stripped)
    if opening is None:
        return False
    marker = opening.group(1)
    lines = stripped.splitlines()
    return len(lines) >= 2 and bool(re.fullmatch(rf"\s*{re.escape(marker)}\s*", lines[-1]))


def _is_question_echo(question: str, text: str) -> bool:
    def normalize(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9_.-]+", value.casefold()))
    return bool(question.strip() and normalize(question) == normalize(text))


__all__ = [
    "direct_evidence_preference",
    "recognized_request_parts",
    "recognized_request_satisfied",
    "visible_request_parts",
]
