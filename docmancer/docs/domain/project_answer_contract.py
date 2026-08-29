"""Bounded semantic contract for project-documentation answers.

The contract deliberately separates *retrieval hints* from *proof obligations*.
Hints may widen recall, but only a locally valid answer unit can discharge an
obligation.  The public MCP input surface remains unchanged; this module is an
internal, immutable boundary shared by query planning, evidence selection, and
projection validation.
"""

from __future__ import annotations

from dataclasses import replace as _replace
import re as _re

from ._project_answer_contract_shared import *  # noqa: F401,F403

from ._project_answer_contract_part01 import *  # noqa: F401,F403

from ._project_answer_contract_part02 import *  # noqa: F401,F403
from ._project_answer_contract_part02 import (
    build_project_answer_contract as _build_project_answer_contract_legacy,
)
from .legacy_question_coverage import legacy_coverage_gaps as _legacy_coverage_gaps
from .question_plan import compile_question_plan as _compile_question_plan
from .technical_terms import extract_technical_terms as _extract_technical_terms


_GENERIC_PROJECT_TERM_LIMIT = MAX_PROOF_OBLIGATIONS
_GENERIC_PROJECT_INTENT_RE = _re.compile(
    r"\b(?:how|what|which|when|where|should|must|does|do|is|are|"
    r"behav(?:e|es|ior)|handle(?:d|s)?|configure(?:d|s)?|persist(?:s|ed)?|"
    r"select(?:s|ed)?|preserv(?:e|es|ed)|accept(?:s|ed)?|return(?:s|ed)?|"
    r"report(?:s|ed)?|apply|applies|work(?:s|ed)?)\b",
    _re.I,
)
_CAUSAL_WHY_RE = _re.compile(r"^\s*(?:why|почему)\b", _re.I)
_GENERIC_PROJECT_STOP_TOKENS = frozenset({
    "a", "about", "after", "also", "an", "and", "apply", "applied", "applies",
    "applying", "are", "as", "at", "be", "before", "being", "been", "by", "can",
    "configure", "configured", "configures", "configuring", "could", "do", "does",
    "documented", "for", "from", "handle", "handled", "handles", "handling", "have",
    "how", "in", "into", "is", "must", "of", "on", "or", "persist", "persisted",
    "persisting", "persists", "preserve", "preserved", "preserves", "preserving",
    "project", "question", "report", "reported", "reporting", "reports", "return",
    "returned", "returning", "returns", "safely", "select", "selected", "selecting",
    "selects", "should", "that", "the", "this", "to", "what", "when", "where",
    "which", "while", "why", "with", "without", "work", "worked", "working", "works",
    "accept", "accepted", "accepting", "accepts",
    "а", "без", "в", "для", "до", "и", "из", "или", "как", "какие", "когда",
    "на", "не", "о", "по", "после", "почему", "при", "про", "проект", "с", "что",
    "чтобы",
})
_GENERIC_COMPOUND_SEPARATOR_RE = _re.compile(r"[_.:/+-]")
_GENERIC_ANCHOR_PART_RE = _re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")


def _clean_term(value: object) -> str:
    return " ".join(str(value or "").split()).strip("`'\".,:;!?()[]{}")[:160]


def _project_anchor(value: object) -> str:
    term = _clean_term(value)
    return "" if term.casefold() in _GENERIC_PROJECT_STOP_TOKENS else term


def _compound_anchor_parts(value: str) -> frozenset[str]:
    if not _GENERIC_COMPOUND_SEPARATOR_RE.search(value):
        return frozenset()
    return frozenset(
        part.casefold()
        for part in _GENERIC_ANCHOR_PART_RE.findall(value)
        if part
    )


def _bare_anchor_is_redundant(term: str, rows: list[str]) -> bool:
    """Prefer `trip.take`/`gold/gem` over duplicate bare `trip`/`gold` anchors."""

    if _GENERIC_COMPOUND_SEPARATOR_RE.search(term):
        return False
    normalized = term.casefold()
    return any(normalized in _compound_anchor_parts(row) for row in rows)


def _append_unique(rows: list[str], value: object) -> None:
    term = _project_anchor(value)
    if (
        not term
        or any(term.casefold() == row.casefold() for row in rows)
        or _bare_anchor_is_redundant(term, rows)
    ):
        return
    if len(rows) < _GENERIC_PROJECT_TERM_LIMIT:
        rows.append(term)


def _tail_guard_terms(question: str) -> tuple[str, ...]:
    """Keep late query semantics visible even when retrieval hints are front-heavy."""

    tokens = _re.findall(
        r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_.:/+-]{2,}",
        question,
    )
    tail: list[str] = []
    for token in reversed(tokens):
        normalized = token.casefold()
        if normalized in _GENERIC_PROJECT_STOP_TOKENS:
            continue
        if len(normalized) < 3 and not _GENERIC_COMPOUND_SEPARATOR_RE.search(token):
            continue
        tail.append(token)
        if len(tail) >= 4:
            break
    return tuple(reversed(tail))


def _generic_project_terms(
    question: str,
    contract: ProjectAnswerContract,
) -> tuple[str, ...]:
    """Return a conservative whole-question fallback for novel project terms.

    Existing QuestionPlan/legacy obligations always win. This path uses only
    domain-local technical identities plus the legacy parser's own bounded
    retrieval hints. Query scaffolding and action verbs can identify intent but
    never become mandatory proof facts. More precise compound/code anchors are
    kept ahead of redundant bare components so the bounded proof surface spends
    capacity on independent semantics. The term set samples both the beginning
    and end of the question so a late unrelated request cannot disappear behind
    a front-only cap. Causal ``why`` questions remain fail-closed because a bag
    of exact facts is not a sufficient proof contract for causality.
    """

    if _CAUSAL_WHY_RE.search(question) or not _GENERIC_PROJECT_INTENT_RE.search(question):
        return ()

    technical = tuple(
        term.raw for term in _extract_technical_terms(question)
        if _project_anchor(term.raw)
    )
    hints = tuple(
        term
        for value in contract.retrieval_hints
        if (term := _project_anchor(value))
    )
    if not technical and len(hints) < 3:
        return ()
    if len(technical) > _GENERIC_PROJECT_TERM_LIMIT:
        return ()

    rows: list[str] = []
    for value in technical:
        _append_unique(rows, value)

    # Preserve early task identity and late constraints/adversarial tails.
    for value in hints[:4]:
        _append_unique(rows, value)
    for value in _tail_guard_terms(question):
        _append_unique(rows, value)
    for value in reversed(hints[-4:]):
        _append_unique(rows, value)

    # Fill remaining bounded capacity from the complete hint stream.
    for value in hints:
        _append_unique(rows, value)

    return tuple(rows) if len(rows) >= (1 if technical else 3) else ()


def _merge_bounded(existing: tuple[str, ...], additions: tuple[str, ...], limit: int) -> tuple[str, ...]:
    """Append fallback identity without breaking the contract's existing hard bounds."""

    return tuple(dict.fromkeys((*existing, *additions)))[:limit]


def build_project_answer_contract(question: str) -> ProjectAnswerContract:
    """Build the contract and fail closed when legacy semantics are incomplete."""

    contract = _build_project_answer_contract_legacy(question)
    raw_question = str(question or "")[:4_000]
    plan = _compile_question_plan(raw_question)
    if plan.handled:
        return contract

    if contract.unresolved_parts:
        generic_terms = _generic_project_terms(raw_question, contract)
        if generic_terms:
            contract = _replace(
                contract,
                subjects=_merge_bounded(
                    contract.subjects, generic_terms, MAX_SUBJECTS,
                ),
                retrieval_hints=_merge_bounded(
                    contract.retrieval_hints, generic_terms, MAX_RETRIEVAL_HINTS,
                ),
                parse_trace=(*contract.parse_trace, "fallback:generic_project_terms"),
            )
        return contract

    if not contract.proof_obligations:
        generic_terms = _generic_project_terms(raw_question, contract)
        if generic_terms:
            contract = _replace(
                contract,
                subjects=_merge_bounded(contract.subjects, generic_terms, MAX_SUBJECTS),
                retrieval_hints=_merge_bounded(
                    contract.retrieval_hints, generic_terms, MAX_RETRIEVAL_HINTS,
                ),
                parse_trace=(*contract.parse_trace, "fallback:generic_project_terms"),
                unresolved_parts=("unsupported_query:generic_free_form_relation",),
            )

    if contract.unresolved_parts:
        return contract
    gaps = _legacy_coverage_gaps(raw_question, contract.proof_obligations)
    if not gaps:
        return contract
    return _replace(
        contract,
        parse_trace=(*contract.parse_trace, "fail_closed:legacy_coverage"),
        unresolved_parts=gaps,
    )


__all__=[n for n in globals() if not n.startswith("__")]
