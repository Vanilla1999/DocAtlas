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

from docmancer.retrieval.contracts import canonical_hash as _canonical_hash

from ._project_answer_contract_shared import *  # noqa: F401,F403

from ._project_answer_contract_part01 import *  # noqa: F401,F403
from ._project_answer_contract_part01 import ProofObligation as _ProofObligation

from ._project_answer_contract_part02 import *  # noqa: F401,F403
from ._project_answer_contract_part02 import (
    build_project_answer_contract as _build_project_answer_contract_legacy,
)
from .legacy_question_coverage import legacy_coverage_gaps as _legacy_coverage_gaps
from .question_plan import compile_question_plan as _compile_question_plan
from .technical_terms import extract_technical_terms as _extract_technical_terms


_GENERIC_PROJECT_TERM_LIMIT = 12
_GENERIC_PROJECT_INTENT_RE = _re.compile(
    r"\b(?:how|what|which|when|where|why|should|must|does|do|is|are|"
    r"behav(?:e|es|ior)|handle(?:d|s)?|configure(?:d|s)?|persist(?:s|ed)?|"
    r"select(?:s|ed)?|preserv(?:e|es|ed)|accept(?:s|ed)?|return(?:s|ed)?|"
    r"report(?:s|ed)?|apply|applies|work(?:s|ed)?)\b",
    _re.I,
)
_TAIL_STOP_TOKENS = frozenset({
    "about", "after", "also", "and", "are", "before", "does", "for", "from",
    "have", "how", "into", "is", "must", "of", "or", "project", "question",
    "should", "that", "the", "this", "what", "when", "where", "which", "while",
    "with", "как", "какие", "когда", "про", "проект", "что", "чтобы",
})


def _clean_term(value: object) -> str:
    return " ".join(str(value or "").split()).strip("`'\".,:;!?()[]{}")[:160]


def _append_unique(rows: list[str], value: object) -> None:
    term = _clean_term(value)
    if not term or any(term.casefold() == row.casefold() for row in rows):
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
        if normalized in _TAIL_STOP_TOKENS:
            continue
        if len(normalized) < 4 and not _re.search(r"[_.:/+-]", token):
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
    retrieval hints. It deliberately samples both the beginning and end of the
    question so a late unrelated request cannot disappear behind a front-only
    term cap.
    """

    if not _GENERIC_PROJECT_INTENT_RE.search(question):
        return ()

    technical = tuple(term.raw for term in _extract_technical_terms(question))
    hints = tuple(_clean_term(value) for value in contract.retrieval_hints if _clean_term(value))
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


def _generic_term_obligations(
    question: str,
    terms: tuple[str, ...],
) -> tuple[_ProofObligation, ...]:
    obligations: list[_ProofObligation] = []
    for index, term in enumerate(terms):
        match = _re.search(_re.escape(term), question, _re.I)
        start = match.start() if match else None
        end = match.end() if match else None
        raw = question[start:end] if start is not None and end is not None else None
        identity = _canonical_hash({
            "kind": "exact_fact",
            "subject": term.casefold(),
            "relation": "generic_project_fact",
            "value_kind": "text",
        })[:16]
        obligations.append(_ProofObligation(
            obligation_id=f"project_answer:generic:{index}:exact_fact:{identity}",
            kind="exact_fact",
            subject=term,
            relation="generic_project_fact",
            value_kind="text",
            query_span_start=start,
            query_span_end=end,
            query_span_text=raw,
        ))
    return tuple(obligations)


def build_project_answer_contract(question: str) -> ProjectAnswerContract:
    """Build the contract and fail closed when legacy semantics are incomplete."""

    contract = _build_project_answer_contract_legacy(question)
    raw_question = str(question or "")[:4_000]
    plan = _compile_question_plan(raw_question)
    if plan.handled or contract.unresolved_parts:
        return contract

    if not contract.proof_obligations:
        generic_terms = _generic_project_terms(raw_question, contract)
        if generic_terms:
            contract = _replace(
                contract,
                subjects=tuple(dict.fromkeys((*contract.subjects, *generic_terms))),
                retrieval_hints=tuple(dict.fromkeys((*contract.retrieval_hints, *generic_terms))),
                proof_obligations=_generic_term_obligations(raw_question, generic_terms),
                parse_trace=(*contract.parse_trace, "fallback:generic_project_terms"),
            )

    gaps = _legacy_coverage_gaps(raw_question, contract.proof_obligations)
    if not gaps:
        return contract
    return _replace(
        contract,
        parse_trace=(*contract.parse_trace, "fail_closed:legacy_coverage"),
        unresolved_parts=gaps,
    )


__all__=[n for n in globals() if not n.startswith("__")]
