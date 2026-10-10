"""Compatibility DTO boundary: documentation questions are not answer contracts.

Only original questions and explicit host lookups authorize retrieval.  A quote
or an identifier occurrence is context, not independent answer authorization.
"""
from __future__ import annotations

from ._project_answer_contract_shared import *  # noqa: F401,F403
from ._project_answer_contract_part01 import *  # noqa: F401,F403
from ._project_answer_contract_part02 import build_project_answer_contract


def obligations_can_authorize_docs_answer(
    obligations: tuple[ProofObligation, ...],
) -> bool:
    """Legacy lexical proof has no independent entailment authority."""
    return False


def can_authorize_docs_answer(contract: ProjectAnswerContract) -> bool:
    return False


__all__ = [name for name in globals() if not name.startswith("__")]
