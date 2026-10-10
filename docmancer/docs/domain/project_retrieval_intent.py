"""Conservative compatibility interfaces for project retrieval.

Free-form questions do not generate aliases, source policies or authority.
Answer certification remains the responsibility of the answer contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

ProjectRetrievalDisposition = Literal["typed_context", "broad_context", "fail_closed"]


@dataclass(frozen=True, slots=True)
class ProjectRetrievalAlias:
    intent_id: str
    text: str
    force_context_only: bool
    source_language: str
    preferred_catalog_roles: tuple[str, ...] = ()
    forbidden_catalog_roles: tuple[str, ...] = ()
    forbidden_evidence_terms: tuple[str, ...] = ()


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token.casefold() for token in
        re.findall(r"[\w.:/+-]+", value)))


def _specific_contract_request(tokens: tuple[str, ...]) -> bool:
    """Legacy premise detector: uncertainty cannot authorize a fallback."""
    return True


def build_project_retrieval_aliases(question: str) -> tuple[ProjectRetrievalAlias, ...]:
    return ()


def project_retrieval_disposition(question: str) -> ProjectRetrievalDisposition:
    from docmancer.docs.domain.project_answer_contract import (
        build_project_answer_contract, can_authorize_docs_answer,
    )
    contract = build_project_answer_contract(question)
    if can_authorize_docs_answer(contract):
        return "typed_context"
    return "fail_closed"


def project_retrieval_requires_context_only(question: str) -> bool:
    return project_retrieval_disposition(question) == "broad_context"


def project_retrieval_allows_context_fallback(question: str) -> bool:
    return project_retrieval_disposition(question) == "broad_context"


def project_retrieval_allows_certified_answer(question: str) -> bool:
    return project_retrieval_disposition(question) == "typed_context"


__all__ = [
    "ProjectRetrievalAlias", "ProjectRetrievalDisposition",
    "build_project_retrieval_aliases", "project_retrieval_disposition",
    "project_retrieval_requires_context_only", "project_retrieval_allows_context_fallback",
    "project_retrieval_allows_certified_answer",
]
