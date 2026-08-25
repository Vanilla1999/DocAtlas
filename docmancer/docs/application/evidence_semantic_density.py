"""Pure semantic-density helpers for source-scoped patch evidence.

This module deliberately has no selector side effects. The selector imports the
helpers explicitly so import order cannot change ranking, fitting, or proof
semantics for unrelated evidence.
"""
from __future__ import annotations

import re

from docmancer.docs.application.evidence_models import EvidenceCandidate, EvidenceRequirement


_BEHAVIORAL_FACT_RE = re.compile(
    r"\b(?:must|shall|required|requires?|never|cannot|may\s+not|forbidden|prohibited|"
    r"is\s+reserved\s+for|is\s+allowed\s+only|only\s+(?:after|before|when|if)|"
    r"do\s+not|should\s+not)\b"
    r"|^\s*(?:[-*]\s+)?(?:use|call|delegate|reject|allow|block|keep|return|require)\b",
    re.IGNORECASE,
)
_HARD_NORMATIVE_RE = re.compile(
    r"\b(?:is\s+allowed\s+only|must\s+not|do\s+not|never|cannot|forbidden|prohibited|"
    r"only\s+(?:after|before|when|if))\b",
    re.IGNORECASE,
)
_CONFIG_VALUE_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\s*:\s*(?:true|false|null|none|[0-9]+)\b",
    re.IGNORECASE,
)
_GENERIC_SCOPE_TOKENS = frozenset({
    "application", "contract", "flow", "gate", "module", "policy",
})


def _normalized_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/").casefold()


def _scope_tokens(value: str) -> tuple[str, ...]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value or ""))
    return tuple(
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9_]+", expanded.replace("_", " "))
        if len(token) >= 3
    )


def source_scoped_behavioral_match(
    requirement: EvidenceRequirement,
    unit_text: str,
    candidate: EvidenceCandidate,
) -> bool:
    """Require a normative local proposition from the requested source and scope."""

    wanted_source = _normalized_path(requirement.source_path or "")
    actual_source = _normalized_path(candidate.path_or_url or candidate.source_identity)
    if not wanted_source or not (
        actual_source == wanted_source
        or actual_source.endswith("/" + wanted_source)
        or wanted_source.endswith("/" + actual_source)
    ):
        return False
    if not _BEHAVIORAL_FACT_RE.search(unit_text):
        return False

    scope = requirement.subject or requirement.value
    scope_tokens = set(_scope_tokens(scope))
    if not scope_tokens:
        return False
    unit_tokens = set(_scope_tokens(unit_text))
    symbol_tokens = {
        token
        for symbol in candidate.symbols
        for token in _scope_tokens(symbol)
    }
    source_tokens = set(_scope_tokens(actual_source.rsplit("/", 1)[-1].rsplit(".", 1)[0]))
    domain_tokens = scope_tokens - _GENERIC_SCOPE_TOKENS
    if domain_tokens:
        return bool(domain_tokens & (unit_tokens | symbol_tokens | source_tokens))
    return bool(scope_tokens & (unit_tokens | symbol_tokens | source_tokens))


def source_fact_unit_semantic_score(text: str) -> int:
    """Rank source-fact witnesses without changing global candidate ordering."""

    if not _BEHAVIORAL_FACT_RE.search(text):
        return 0
    score = 2
    if _HARD_NORMATIVE_RE.search(text):
        score += 2
    if _CONFIG_VALUE_RE.search(text):
        score += 4
    return score


__all__ = [
    "source_fact_unit_semantic_score",
    "source_scoped_behavioral_match",
]
