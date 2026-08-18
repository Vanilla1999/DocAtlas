"""Fail-closed proof for presupposed project-doc claims.

A ``why`` question with a universal/cardinality premise is not answered merely
because evidence repeats the premise.  A bounded local witness must either
contradict the premise (so the answer can correct it) or restate it together
with an explicit causal explanation.
"""
from __future__ import annotations

import re
from typing import Mapping, TypeAlias

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.technical_terms import term_sequence_present

PremiseProofResult: TypeAlias = tuple[bool, int, int, str, int]

_NUMBER_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "один": 1, "одна": 1, "два": 2, "две": 2, "три": 3,
    "четыре": 4, "пять": 5, "шесть": 6, "семь": 7,
    "восемь": 8, "девять": 9, "десять": 10,
}
_NUMBER_TOKEN = (
    r"\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять"
)
_CAUSAL_RE = re.compile(
    r"\b(?:because|since|due\s+to|so\s+that|in\s+order\s+to|to\s+ensure|"
    r"by\s+design|therefore|потому\s+что|так\s+как|для\s+того\s+чтобы|"
    r"чтобы|из-за|поэтому)\b",
    re.I,
)
_LIMITATION_RE = re.compile(
    r"\b(?:not\s+always|sometimes|only\s+when|only\s+if|unless|"
    r"не\s+всегда|иногда|только\s+когда|только\s+если)\b",
    re.I,
)
_ACTION_FORMS = {
    "delete": ("delete", "deletes", "deleted", "deleting", "remove", "removes", "removed", "removing", "удаляет", "удалить", "удалять"),
    "remove": ("delete", "deletes", "deleted", "deleting", "remove", "removes", "removed", "removing", "удаляет", "удалить", "удалять"),
    "удаляет": ("delete", "deletes", "deleted", "deleting", "remove", "removes", "removed", "removing", "удаляет", "удалить", "удалять"),
    "preserve": ("preserve", "preserves", "preserved", "preserving", "keep", "keeps", "kept", "сохраняет", "сохранить", "сохранять"),
    "сохраняет": ("preserve", "preserves", "preserved", "preserving", "keep", "keeps", "kept", "сохраняет", "сохранить", "сохранять"),
    "retry": ("retry", "retries", "retried", "retrying", "повторяет", "повторить", "повторять"),
    "повторяет": ("retry", "retries", "retried", "retrying", "повторяет", "повторить", "повторять"),
    "bypass": ("bypass", "bypasses", "bypassed", "bypassing", "обходит", "обойти"),
    "обходит": ("bypass", "bypasses", "bypassed", "bypassing", "обходит", "обойти"),
}
_STOP_TARGET_TOKENS = frozenset({"the", "a", "an", "does", "always", "never", "всегда", "никогда"})


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("_", " ").split())


def _clauses(text: str) -> tuple[str, ...]:
    return tuple(
        part.strip()
        for part in re.split(r"(?<=[.!?;])\s+|\n+", str(text or ""))
        if part.strip()
    ) or (str(text or "").strip(),)


def _count_value(value: object) -> int | None:
    raw = _norm(value)
    if raw.isdigit():
        number = int(raw)
        return number if 1 <= number <= 32 else None
    return _NUMBER_VALUES.get(raw)


def _target_parts(target: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tokens = _norm(target).split()
    if len(tokens) < 2:
        return (), ()
    forms = _ACTION_FORMS.get(tokens[0], ())
    objects = tuple(
        token for token in tokens[1:]
        if token not in _STOP_TARGET_TOKENS and len(token) >= 3
    )
    return forms, objects


def _target_bound(target: str, clause: str) -> tuple[bool, tuple[str, ...]]:
    forms, object_tokens = _target_parts(target)
    if not forms or not object_tokens:
        return False, forms
    normalized = _norm(clause)
    action_present = any(
        re.search(rf"(?<!\w){re.escape(form)}(?!\w)", normalized)
        for form in forms
    )
    object_hits = sum(token in normalized for token in set(object_tokens))
    return action_present and object_hits >= min(2, len(set(object_tokens))), forms


def _negative_action(clause: str, forms: tuple[str, ...]) -> bool:
    if not forms:
        return False
    action = "(?:" + "|".join(re.escape(form) for form in forms) + ")"
    patterns = (
        rf"\bnever\b(?:\W+\w+){{0,5}}?\W+{action}\b",
        rf"\b(?:does|do|did|will|would|can|could|must|should)\s+not\b(?:\W+\w+){{0,5}}?\W+{action}\b",
        rf"\bcannot\b(?:\W+\w+){{0,5}}?\W+{action}\b",
        rf"\bникогда\s+не\b(?:\W+\w+){{0,5}}?\W+{action}\b",
        rf"\bне\b(?:\W+\w+){{0,4}}?\W+{action}\b",
    )
    normalized = _norm(clause)
    return any(re.search(pattern, normalized, re.I) for pattern in patterns)


def _universal_action(clause: str, forms: tuple[str, ...]) -> bool:
    if not forms:
        return False
    action = "(?:" + "|".join(re.escape(form) for form in forms) + ")"
    normalized = _norm(clause)
    return bool(
        re.search(rf"\b(?:always|всегда)\b(?:\W+\w+){{0,5}}?\W+{action}\b", normalized, re.I)
    )


def _premise_check(
    obligation: ProofObligation,
    text: str,
) -> PremiseProofResult:
    expected = _norm(obligation.expected_value)
    if expected not in {"always", "never"} or not obligation.target:
        return False, 0, 0, "premise_expectation_missing", 0

    for clause in _clauses(text):
        if not term_sequence_present(obligation.subject, clause):
            continue
        bound, forms = _target_bound(obligation.target, clause)
        if not bound:
            continue
        negative = _negative_action(clause, forms)
        causal = bool(_CAUSAL_RE.search(clause))
        limited = bool(_LIMITATION_RE.search(clause))
        universal = _universal_action(clause, forms)

        if expected == "always":
            contradiction = negative or limited
            explained = universal and not negative and causal
        else:
            contradiction = not negative
            explained = negative and causal

        if contradiction:
            return True, 4, 4, "premise_corrected", 3
        if explained:
            return True, 4, 4, "premise_explained", 3

    return False, 0, 0, "premise_truth_unresolved", 0


def _premise_cardinality(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None,
) -> PremiseProofResult:
    expected = _count_value(obligation.expected_value)
    if expected is None:
        return False, 0, 0, "premise_cardinality_expectation_missing", 0
    source_text = _norm(" ".join(str((source or {}).get(key) or "") for key in (
        "path", "source", "title", "heading_path", "project_doc_path",
    )))
    count_re = re.compile(
        rf"\b(?:exactly\s+)?(?P<count>{_NUMBER_TOKEN})\s+"
        rf"(?:public\s+)?(?:docs\s+mcp\s+)?tools?\b",
        re.I,
    )
    for clause in _clauses(text):
        normalized = _norm(clause)
        subject_bound = term_sequence_present(obligation.subject, clause) or "docs mcp" in source_text
        if not subject_bound:
            continue
        counts = {
            value
            for match in count_re.finditer(normalized)
            if (value := _count_value(match.group("count"))) is not None
        }
        if len(counts) != 1:
            continue
        observed = next(iter(counts))
        if observed != expected:
            return True, 4, 4, "premise_cardinality_corrected", 3
        if _CAUSAL_RE.search(clause):
            return True, 4, 4, "premise_cardinality_explained", 3
    return False, 0, 0, "premise_cardinality_unresolved", 0


def premise_relation_proof(
    obligation: ProofObligation,
    text: str,
    *,
    source: Mapping[str, object] | None = None,
) -> PremiseProofResult | None:
    """Return a proof result only for premise relations."""

    if obligation.relation == "premise_check":
        return _premise_check(obligation, text)
    if obligation.relation == "premise_cardinality":
        return _premise_cardinality(obligation, text, source=source)
    return None


__all__ = ["PremiseProofResult", "premise_relation_proof"]
