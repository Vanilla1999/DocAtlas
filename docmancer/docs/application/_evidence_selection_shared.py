"""Deterministic, provider-free minimal evidence selection.

The selector owns evidence eligibility and fitting.  Formatters receive only a
validated whole-item subset and remain responsible for serialization safety,
not for deciding which source facts are important.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Literal, Mapping, Sequence, overload

from docmancer.docs.domain.answer_units import (
    AnswerUnit,
    LocalProof,
    best_local_proof,
    extract_answer_units,
    local_proof_for_obligation,
    materialize_answer_units,
)
from docmancer.docs.application.evidence_models import (
    SELECTOR_SCHEMA_VERSION, MAX_SELECTOR_CANDIDATES, MAX_VISIBLE_DOCUMENTS, MAX_VISIBLE_SPANS,
    OmissionReason, ProofRole, EvidenceQualifier, SelectionConfig, EvidenceRequirement,
    EvidenceRequirementSet, EvidenceCandidate, Omission, EvidenceAssignment,
    RequirementWitness, SupportDecision,
)
from docmancer.docs.application.evidence_candidates import (
    docs_answer_candidate_tokens as _docs_answer_candidate_tokens,
    estimated_tokens as _estimated_tokens,
    normalized_source as _normalized_source,
    normalize_candidates,
    observed_qualifiers as _observed_qualifiers,
    positive_int as _positive_int,
    requirement_value_visible,
    display_text as _display_text,
    source_path as _source_path,
    symbols as _symbols,
    version_rank as _version_rank,
)
from docmancer.docs.application.evidence_requirements import build_requirements

from docmancer.docs.domain.project_answer_contract import (
    LifecycleIntent,
    ProofObligation,
    ProjectAnswerContract,
    build_project_answer_contract,
)
from docmancer.retrieval.contracts import canonical_hash
from docmancer.retrieval.query_planning import extract_exact_terms


MAX_MIXED_VISIBLE_TOKENS = 800
MIXED_WRAPPER_RESERVE_TOKENS = 120
MAX_REQUIREMENT_IDENTIFIERS = 12
MAX_REQUIREMENT_PATHS = 12
MAX_PUBLIC_REQUIREMENTS = 12
MAX_CODE_GROUPS = 6
DOCS_SERIALIZATION_RESERVE_TOKENS = 350
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(r"[\w.+:/-]+", re.UNICODE)
_COMPARISON_IDENTIFIER = r"(?<![a-z0-9_`])(`?[a-z][a-z0-9_]*`?)(?![a-z0-9_`])"
_LOWERCASE_COMPARISON_RE = re.compile(
    rf"{_COMPARISON_IDENTIFIER}\s+instead\s+of\s+{_COMPARISON_IDENTIFIER}",
    re.IGNORECASE,
)
_COMPARE_WITH_RE = re.compile(
    rf"\bcompare\s+{_COMPARISON_IDENTIFIER}\s+with\s+{_COMPARISON_IDENTIFIER}", re.IGNORECASE,
)
_COMPARING_AND_RE = re.compile(
    rf"\bcomparing\s+{_COMPARISON_IDENTIFIER}\s+and\s+{_COMPARISON_IDENTIFIER}", re.IGNORECASE,
)
_RESULT_ACCESS_RE = re.compile(r"\b(?:obtain|get|retrieve)\s+(?:its|the)\s+result\b", re.IGNORECASE)
_PASSIVE_RESULT_ACCESS_RE = re.compile(
    r"\b(?:the\s+)?(?:scheduled\s+task\s+)?result\s+is\s+obtained\b", re.IGNORECASE,
)
_CODE_REQUEST_RE = re.compile(
    r"\b(?:show|write|give|provide|need)\s+(?:an?\s+)?(?:code|example|snippet)\b"
    r"|\b(?:code|example|snippet)\s+(?:for|that|showing)\b",
    re.IGNORECASE,
)
_PATCH_FACT_RE = re.compile(
    r"\b(?:must|shall|required|requires?|never|cannot|may\s+not|forbidden|prohibited|"
    r"is\s+reserved\s+for|only\s+(?:after|before|when|if)|is\s+allowed\s+only|"
    r"pytest|compileall|cargo\s+(?:test|check|build)|npm\s+(?:test|run)|"
    r"dart\s+(?:test|analyze)|go\s+test|make\s+test)\b",
    re.IGNORECASE,
)
_LEGAL_INTENT_TERMS = frozenset({
    "agreement", "arbitration", "conditions", "copyright", "disclaimer",
    "dmca", "eula", "governing", "indemnification", "jurisdiction", "legal",
    "liability", "license", "privacy", "terms", "warranties", "waiver",
})
_ALLOWED_REQUIREMENT_PROVENANCE = frozenset({
    "query_exact_term",
    "public_task_contract",
    "required_evidence_paths",
    "required_target_paths",
    "exact_dependency_binding",
    "selector_scope_requirement",
    "canonical_policy_requirement",
    "disclosed_authority_version_conflict",
})

_QUALIFIER_PATTERNS = {
    "proposed": re.compile(r"\bpropos(?:ed|al)\b", re.I),
    "not_implemented": re.compile(r"\bnot\s+(?:yet\s+)?implemented\b", re.I),
    "confirmation_required": re.compile(r"\b(?:confirmation|required approval)\s+(?:is\s+)?required\b", re.I),
    "negated": re.compile(r"\b(?:not|never|no|cannot|must not)\b", re.I),
    "conditional": re.compile(r"\b(?:if|when|unless|only after|only before)\b", re.I),
    "deprecated": re.compile(r"\bdeprecated\b", re.I),
}
























































































































































__all__ = [
    "MAX_SELECTOR_CANDIDATES", "SELECTOR_SCHEMA_VERSION", "EvidenceCandidate",
    "EvidenceRequirement", "EvidenceRequirementSet", "Omission", "SelectionConfig", "SelectionDecision",
    "build_requirements", "docs_selection_config", "library_docs_selection_config", "project_docs_selection_config", "normalize_candidates",
    "patch_selection_config", "select_evidence", "validate_evidence_sufficiency",
]

__all__=[n for n in globals() if not n.startswith('__')]
