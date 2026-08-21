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
from ._project_answer_contract_shared import ProofObligation as _ProofObligation

from ._project_answer_contract_part01 import *  # noqa: F401,F403

from ._project_answer_contract_part02 import *  # noqa: F401,F403
from ._project_answer_contract_part02 import (
    build_project_answer_contract as _build_project_answer_contract_legacy,
)
from .answer_completeness import (
    extract_project_answer_requirements as _extract_project_answer_requirements,
    extract_query_relevance_terms as _extract_query_relevance_terms,
)
from .legacy_question_coverage import legacy_coverage_gaps as _legacy_coverage_gaps
from .question_plan import compile_question_plan as _compile_question_plan


_GENERIC_PROJECT_TERM_LIMIT = 8
_SINGLE_EXPLICIT_INTENT_RE = _re.compile(
    r"\b(?:how|what|when|where|why|should|must|behav(?:e|es|ior)|handle(?:d|s)?|"
    r"configure(?:d|s)?|persist(?:s|ed)?|select(?:s|ed)?|preserv(?:e|es|ed)|"
    r"accept(?:s|ed)?|return(?:s|ed)?|report(?:s|ed)?|apply|applies|work(?:s|ed)?)\b",
    _re.I,
)
_TECHNICAL_TERM_SHAPE_RE = _re.compile(
    r"(?:[_.:/-]|[a-z][A-Z]|[A-Za-z]+\d|\d[A-Za-z]+)"
)


def _bounded_unique_terms(values: object) -> tuple[str, ...]:
    rows: list[str] = []
    for value in values if isinstance(values, (list, tuple)) else ():
        term = " ".join(str(value or "").split()).strip("`'\".,:;!?()[]{}")
        if term and term.casefold() not in {row.casefold() for row in rows}:
            rows.append(term)
        if len(rows) >= _GENERIC_PROJECT_TERM_LIMIT:
            break
    return tuple(rows)


def _generic_project_terms(question: str) -> tuple[str, ...]:
    """Return a conservative bounded fallback contract for novel project terms.

    Existing QuestionPlan/legacy obligations always win.  This fallback exists
    only for the bootstrap hole where both parsers are silent even though the
    question contains reviewable project-specific anchors.  A lone opaque word
    remains unsupported unless it is an explicitly named technical term in a
    clear behavior/workflow question.
    """

    explicit = _bounded_unique_terms(_extract_project_answer_requirements(question))
    if len(explicit) >= 2:
        return explicit
    if (
        len(explicit) == 1
        and _TECHNICAL_TERM_SHAPE_RE.search(explicit[0])
        and _SINGLE_EXPLICIT_INTENT_RE.search(question)
    ):
        return explicit

    relevance = _bounded_unique_terms(_extract_query_relevance_terms(question))
    return relevance if len(relevance) >= 3 else ()


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
        generic_terms = _generic_project_terms(raw_question)
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
