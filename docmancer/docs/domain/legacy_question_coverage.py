"""Fail-closed semantic coverage checks for the frozen legacy question parser.

The legacy parser may continue to build its historical proof obligations, but it
must not authorize ``supported`` when those obligations cover only a convenient
subset of the user's request.  This module never creates proof obligations and
never broadens retrieval.  It only detects a small set of independent semantic
facets that are visible in the public question and verifies that the legacy
contract already represents them.
"""
from __future__ import annotations

import re
from typing import Iterable, Protocol


class _ObligationLike(Protocol):
    kind: str
    subject: str
    attribute: str | None
    relation: str | None
    target: str | None
    item_kind: str | None
    expected_value: str | None
    context: str | None


_STOP_TOKENS = frozenset({
    "a", "an", "and", "are", "be", "between", "contract", "does", "for",
    "from", "how", "in", "is", "of", "or", "policy", "public", "rule",
    "the", "to", "what", "when", "which", "with",
    "и", "или", "как", "какие", "когда", "между", "правило", "политика",
    "контракт", "для", "что", "это",
})
_GENERIC_LIST_TOKENS = frozenset({"call", "calls", "item", "items", "value", "values"})


def _stem(token: str) -> str:
    value = token.casefold().strip("`'\".,:;!?()[]{}")
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("s") and len(value) > 4 and not value.endswith("ss"):
        return value[:-1]
    return value


def _tokens(value: object, *, drop_generic_list: bool = False) -> tuple[str, ...]:
    rows = []
    for raw in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.-]+", str(value or "")):
        token = _stem(raw)
        if len(token) < 2 or token in _STOP_TOKENS:
            continue
        if drop_generic_list and token in _GENERIC_LIST_TOKENS:
            continue
        rows.append(token)
    return tuple(dict.fromkeys(rows))


def _semantic_text(obligation: _ObligationLike) -> str:
    return " ".join(str(value or "") for value in (
        obligation.kind,
        obligation.subject,
        obligation.attribute,
        obligation.relation,
        obligation.target,
        obligation.item_kind,
        obligation.expected_value,
        obligation.context,
    ))


def _semantic_token_set(obligations: Iterable[_ObligationLike]) -> set[str]:
    result: set[str] = set()
    for obligation in obligations:
        result.update(_tokens(_semantic_text(obligation)))
    return result


def _has_kind_or_relation(
    obligations: tuple[_ObligationLike, ...],
    *,
    kinds: tuple[str, ...] = (),
    relations: tuple[str, ...] = (),
) -> bool:
    return any(
        str(row.kind or "") in kinds or str(row.relation or "") in relations
        for row in obligations
    )


def _inventory_requested(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:what\s+are|which|list|enumerate|name|how\s+many)\b[^?]{0,100}"
            r"\btools?\b",
            question,
            re.I,
        )
        or re.search(
            r"\b(?:назови|перечисли|какие|сколько)\b[^?]{0,100}\bинструмент\w*\b",
            question,
            re.I,
        )
    )


def _purpose_requested(question: str) -> bool:
    return bool(re.search(
        r"\bpurposes?\b|\bwhat\s+.+?\s+(?:is|are)\s+for\b|"
        r"\bназначени\w*\b|\bдля\s+чего\b",
        question,
        re.I,
    ))


def _usage_requested(question: str) -> bool:
    return bool(
        re.search(
            r"\bwhen\b[^?]{0,100}\b(?:use|used|using)\b|"
            r"\bwhen\s+(?:do|should|would)\b[^?]{0,100}\buse\b|"
            r"\bwhen\s+should\b[^?]{0,100}\bbe\s+used\b",
            question,
            re.I,
        )
        or re.search(
            r"\bкогда\b[^?]{0,100}\bиспольз\w*\b|"
            r"\bкогда\s+(?:использовать|следует\s+использовать)\b",
            question,
            re.I,
        )
    )


def _comparison_requested(question: str) -> bool:
    return bool(re.search(
        r"\bdifference\s+between\b|\bdiffer(?:s|ed|ent)?\s+from\b|"
        r"\bcompare\b[^?]{0,120}\b(?:with|and)\b|"
        r"\bразниц\w*\s+между\b|\bчем\b[^?]{0,100}\bотлича\w*\b",
        question,
        re.I,
    ))


def _contract_scope_tokens(question: str) -> tuple[str, ...]:
    match = re.search(
        r"\b(?:what\s+is|explain|describe)\s+(?:the\s+)?(.{1,180}?)\s+"
        r"(?:contract|policy|rule|invariant)\b",
        question,
        re.I,
    )
    if match is None:
        match = re.search(
            r"\bwhat\s+(?:project\s+)?(?:rules|policies)\s+govern\s+"
            r"(.{1,180}?)(?:,\s*including\b|[?!.]*$)",
            question,
            re.I,
        )
    if match is None:
        return ()
    return _tokens(match.group(1))


def _requirement_items(question: str) -> tuple[str, ...]:
    match = re.search(r"\brequire(?:s|d)?\s+for\s+(.+?)[?!.]*$", question, re.I)
    if match is None:
        match = re.search(r"\bincluding\s+(.+?)[?!.]*$", question, re.I)
    if match is None:
        return ()
    tail = match.group(1).strip()
    if not tail:
        return ()
    parts = [
        part.strip(" `\"'.,:;!?()")
        for part in re.split(r"\s*,\s*|\s+and\s+", tail, flags=re.I)
        if part.strip(" `\"'.,:;!?()")
    ]
    return tuple(parts) if len(parts) >= 2 else ()


def _item_is_covered(item: str, semantic_tokens: set[str]) -> bool:
    alternatives = [part.strip() for part in re.split(r"\s+or\s+", item, flags=re.I)]
    for alternative in alternatives:
        required = set(_tokens(alternative, drop_generic_list=True))
        if required and required.issubset(semantic_tokens):
            return True
    return False


def legacy_coverage_gaps(
    question: str,
    obligations: Iterable[_ObligationLike],
) -> tuple[str, ...]:
    """Return deterministic unresolved reasons for an incomplete legacy contract."""

    rows = tuple(obligations)
    if not rows:
        return ("unsupported_query:legacy_no_contract",)

    gaps: list[str] = []
    if _inventory_requested(question) and not _has_kind_or_relation(rows, kinds=("inventory",)):
        gaps.append("legacy_unresolved:inventory")
    if _purpose_requested(question) and not _has_kind_or_relation(
        rows, kinds=("purpose",), relations=("purpose",),
    ):
        gaps.append("legacy_unresolved:purpose")
    if _usage_requested(question) and not _has_kind_or_relation(
        rows, kinds=("usage",), relations=("usage", "public_tool_usage", "per_tool_usage"),
    ):
        gaps.append("legacy_unresolved:usage")
    if _comparison_requested(question) and not _has_kind_or_relation(
        rows, kinds=("comparison",), relations=("contrast",),
    ):
        gaps.append("legacy_unresolved:comparison")

    semantic_tokens = _semantic_token_set(rows)
    contract_tokens = set(_contract_scope_tokens(question))
    if contract_tokens and not contract_tokens.issubset(semantic_tokens):
        gaps.append("legacy_unresolved:contract_scope")

    requirement_items = _requirement_items(question)
    if requirement_items:
        missing = [
            item for item in requirement_items
            if not _item_is_covered(item, semantic_tokens)
        ]
        if missing:
            gaps.append("legacy_unresolved:requirement_items")

    return tuple(dict.fromkeys(gaps))


__all__ = ["legacy_coverage_gaps"]
