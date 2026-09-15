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
        r"\bwhat\s+(.{1,180}?\b(?:contract|policy|rule|invariant))\s+"
        r"does\s+.+?\s+use\b",
        question,
        re.I,
    )
    if match is not None:
        return _tokens(match.group(1))
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


def _behavior_qualifier_tokens(
    question: str,
    obligations: tuple[_ObligationLike, ...],
) -> tuple[str, ...]:
    """Return operation terms that a generic ``how does`` contract must retain."""

    behavior = next((row for row in obligations if row.kind == "behavior"), None)
    if behavior is None or not behavior.subject:
        return ()
    subject_pattern = re.escape(behavior.subject).replace(r"\ ", r"[\s_]+")
    match = re.match(
        rf"^\s*how\s+does\s+(?:the\s+)?{subject_pattern}\s+(.+?)[?!.]*\s*$",
        question,
        re.I,
    )
    if match is None:
        return ()
    tail = match.group(1).strip()
    if re.fullmatch(r"work", tail, re.I):
        return ()
    if re.match(r"^(?:choose|split)\b", tail, re.I):
        tail = re.sub(r"^(?:choose|split)\s+", "", tail, count=1, flags=re.I)
    return _tokens(tail)


def _item_is_covered(item: str, semantic_tokens: set[str]) -> bool:
    alternatives = [part.strip() for part in re.split(r"\s+or\s+", item, flags=re.I)]
    for alternative in alternatives:
        required = set(_tokens(alternative, drop_generic_list=True))
        if required and required.issubset(semantic_tokens):
            return True
    return False



def _reviewed_legacy_frame(question: str, rows: tuple[_ObligationLike, ...]) -> bool:
    """Whole grammars, not identifier hits or percentages, may close legacy scope.

    Keep the small existing structured frames. A legacy keyword branch without
    a whole-question grammar remains useful for retrieval but not certification.
    """
    from ._project_answer_contract_shared import (
        _COORDINATED_EFFECT_RE, _DECLARATIVE_RELATION_RE, _FEATURE_CONTEXT_RE,
        _SUPPORTED_VALUES_RE, _TERM_IN_CONTEXT_RE, _USED_FOR_RE,
    )
    structured = (
        (_COORDINATED_EFFECT_RE, {"effect"}),
        (_DECLARATIVE_RELATION_RE, {"relation"}),
        (_FEATURE_CONTEXT_RE, {"purpose"}),
        (_SUPPORTED_VALUES_RE, {"inventory"}),
        (_TERM_IN_CONTEXT_RE, {"purpose"}),
        (_USED_FOR_RE, {"purpose"}),
    )
    if any(pattern.fullmatch(question) and {r.kind for r in rows} == kinds
           for pattern, kinds in structured):
        return True
    if len(rows) != 1:
        return False
    row = rows[0]
    subject = re.escape(row.subject).replace(r"\ ", r"\s+")
    subject = rf"`?{subject}`?"
    prefix = r"\s*"
    suffix = r"\s*[?!.]*\s*"
    grammar = None
    if row.kind == "definition":
        grammar = rf"(?:what\s+is|define|meaning\s+of|что\s+такое)\s+(?:the\s+)?{subject}"
    elif row.kind == "behavior":
        operation = re.escape(row.expected_value) if row.expected_value else r"(?:do|work)"
        target = rf"\s+{re.escape(row.target)}" if row.target else ""
        grammar = rf"(?:what|how)\s+does\s+(?:the\s+)?{subject}\s+{operation}{target}"
    elif row.kind == "workflow":
        target = rf"\s+{re.escape(row.target)}" if row.target else ""
        grammar = rf"how\s+does\s+(?:the\s+)?{subject}{target}\s+work"
    elif row.kind == "usage":
        grammar = rf"when\s+should\s+(?:i\s+use\s+{subject}|{subject}\s+be\s+used)"
    elif row.kind == "location":
        # The old extractor takes the entire tail as a title. An unquoted
        # temporal/conditional clause is not thereby a recognized document.
        if not re.fullmatch(r"[`\"].+[`\"]", row.subject) and re.search(
            r"\b(?:after|before|under|when|после|перед|когда)\b", row.subject, re.I,
        ):
            return False
        # _location_subject canonicalizes the existing project-name alias.
        grammar = rf"(?:where\s+is|где\s+находится)\s+(?:the\s+)?(?:DocAtlas\s+)?{subject}"
    elif row.kind == "attribute" and row.attribute == "timeout":
        grammar = rf"what\s+is\s+(?:the\s+)?{subject}\s+(?:timeout|deadline)"
    elif row.kind == "attribute" and row.attribute:
        attribute = re.escape(row.attribute).replace(r"\ ", r"\s+")
        grammar = rf"how\s+many\s+{attribute}\s+does\s+{subject}\s+(?:allow|permit|support|have|use)"
    elif row.kind == "exact_fact" and row.relation == "implementation":
        grammar = rf"(?:implement|wire|реализовать)\s+{subject}"
    elif row.kind == "inventory" and row.subject == "Docs MCP":
        # The existing bounded public surface has explicit subject aliases.
        # These templates end at the inventory: no extra request is consumed.
        public_subject = r"(?:the\s+)?(?:Docs\s+MCP(?:\s+server)?|MCP\s+server|DocAtlas)"
        number = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
        grammar = (
            rf"(?:which|how\s+many|what\s+are|list)\s+(?:the\s+)?(?:{number}\s+)?"
            rf"(?:public\s+)?(?:Docs\s+)?(?:MCP\s+)?tools\s+"
            rf"(?:(?:does|do)\s+{public_subject}\s+expose|of\s+{public_subject})"
            rf"|what\s+are\s+(?:the\s+)?(?:{number}\s+)?(?:public\s+)?Docs\s+MCP\s+tools"
            rf"|what\s+is\s+the\s+{number}-tool\s+public\s+Docs\s+MCP\s+surface"
        )
    return grammar is not None and re.fullmatch(prefix + "(?:" + grammar + ")" + suffix, question, re.I) is not None

def legacy_coverage_gaps(
    question: str,
    obligations: Iterable[_ObligationLike],
) -> tuple[str, ...]:
    """Return deterministic unresolved reasons for an incomplete legacy contract."""

    rows = tuple(obligations)
    if not rows:
        return ("unsupported_query:legacy_no_contract",)

    gaps: list[str] = []
    # Generic do/work only owns the complete simple frame. Any suffix that
    # its extractor discarded is unresolved, regardless of its vocabulary.
    for row in rows:
        if row.kind != "behavior" or not row.subject:
            continue
        subject = re.escape(row.subject).replace(r"\ ", r"[\s_]+")
        simple = re.fullmatch(
            rf"\s*(?:how|what)\s+does\s+(?:the\s+)?`?{subject}`?\s+"
            r"(?:do|work)\b(?P<tail>.*?)\s*[?!.]*\s*", question, re.I,
        )
        if simple and (tail := simple.group("tail").strip()):
            gaps.append(f"legacy_unresolved:behavior_suffix:{tail}")
    # Legacy identifier/keyword matches have no reviewed conditional frame.
    # Keep the actual qualifier as residue: topical overlap (even all its words)
    # is not evidence that the condition and the requested action were parsed.
    # Fully owned question frames are checked before this fallback is called.
    qualifier = re.search(
        r"\b(?:if|unless|without|only\s+(?:when|if)|provided\s+that|"
        r"если|если\s+только|без|только\s+(?:когда|если)|при\s+условии)\b[^?!.]*",
        question,
        re.I,
    )
    # This existing two-obligation contract has a complete, bounded grammar.
    # Its "without" relation is represented, unlike an arbitrary conditional
    # suffix on a recognized identifier. Neither a stem count nor a partial
    # keyword match can grant this exception.
    recall_authority_frame = bool(re.fullmatch(
        r"\s*how\s+does\s+exact[- ]term\s+(?:recall|retrieval)\s+improve\s+"
        r"without\s+widening\s+authority(?:\s+scope)?\s*[?!.]*\s*",
        question, re.I,
    )) and {row.relation for row in rows} == {"recall_mechanism", "authority_invariant"}
    if qualifier is not None and not recall_authority_frame:
        gaps.append(f"legacy_unresolved:condition:{qualifier.group(0).strip()}")
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
    behavior_tokens = set(_behavior_qualifier_tokens(question, rows))
    if behavior_tokens and not behavior_tokens.issubset(semantic_tokens):
        gaps.append("legacy_unresolved:behavior_operation")
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

    if not gaps and not recall_authority_frame and not _reviewed_legacy_frame(question, rows):
        gaps.append(f"legacy_unresolved:unreviewed_frame:{question.strip()}")
    return tuple(dict.fromkeys(gaps))


__all__ = ["legacy_coverage_gaps"]
