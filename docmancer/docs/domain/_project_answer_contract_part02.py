"""Conservative adapter retaining the immutable project-answer DTO signature."""
from __future__ import annotations

from ._project_answer_contract_shared import *  # noqa: F401,F403
from ._project_answer_contract_part01 import ProjectAnswerContract


def build_project_answer_contract(question: str) -> ProjectAnswerContract:
    """Bind question identity without compiling NL into expected answers.

    Hash the complete input, even when it exceeds the historical parser bound.
    The DTO deliberately contains no retrieval probes or inferred obligations.
    """
    source_question = str(question or "")
    return ProjectAnswerContract(
        question_hash=canonical_hash(source_question),
        retrieval_hints=(),
        concept_queries=(),
        subjects=(),
        proof_obligations=(),
        schema_version=PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
        input_limits=("question",) if len(source_question) > 4_000 else (),
        parse_trace=("context_only:literal_request",),
        unresolved_parts=(),
        component_scope_complete=False,
    )


__all__ = ["build_project_answer_contract"]
