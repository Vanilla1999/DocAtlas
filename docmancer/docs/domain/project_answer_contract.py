"""Bounded semantic contract for project-documentation answers.

The contract deliberately separates *retrieval hints* from *proof obligations*.
Hints may widen recall, but only a locally valid answer unit can discharge an
obligation.  The public MCP input surface remains unchanged; this module is an
internal, immutable boundary shared by query planning, evidence selection, and
projection validation.
"""

from __future__ import annotations

from dataclasses import replace as _replace

from ._project_answer_contract_shared import *  # noqa: F401,F403

from ._project_answer_contract_part01 import *  # noqa: F401,F403

from ._project_answer_contract_part02 import *  # noqa: F401,F403
from ._project_answer_contract_part02 import (
    build_project_answer_contract as _build_project_answer_contract_legacy,
)
from .legacy_question_coverage import legacy_coverage_gaps as _legacy_coverage_gaps
from .question_plan import compile_question_plan as _compile_question_plan


def build_project_answer_contract(question: str) -> ProjectAnswerContract:
    """Build the contract and fail closed when legacy semantics are incomplete."""

    contract = _build_project_answer_contract_legacy(question)
    raw_question = str(question or "")[:4_000]
    plan = _compile_question_plan(raw_question)
    if plan.handled or contract.unresolved_parts:
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
