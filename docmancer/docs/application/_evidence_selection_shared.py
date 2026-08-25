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
from docmancer.docs.application.evidence_requirements import build_requirements as _build_requirements_impl

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
    "patch_request_plan",
})

_QUALIFIER_PATTERNS = {
    "proposed": re.compile(r"\bpropos(?:ed|al)\b", re.I),
    "not_implemented": re.compile(r"\bnot\s+(?:yet\s+)?implemented\b", re.I),
    "confirmation_required": re.compile(r"\b(?:confirmation|required approval)\s+(?:is\s+)?required\b", re.I),
    "negated": re.compile(r"\b(?:not|never|no|cannot|must not)\b", re.I),
    "conditional": re.compile(r"\b(?:if|when|unless|only after|only before)\b", re.I),
    "deprecated": re.compile(r"\bdeprecated\b", re.I),
}

_GOVERNANCE_PROJECT_RULE_RELATIONS = frozenset({
    "governed_scope",
    "governance_facet",
    "governance_ownership",
    "governance_requirement",
    "governance_state",
    "governance_version",
})


def _source_fact_requirements(
    public_requirements: Iterable[Mapping[str, Any] | str],
) -> tuple[EvidenceRequirement, ...]:
    """Normalize public ``source_fact`` rows into source-scoped behavior obligations.

    The public contract names the source and behavioral scope, not an expected
    benchmark sentence.  The selector must still locate a substantive local
    witness inside that source.  Internally these use the existing
    ``behavioral_contract`` proof path so packet formatting keeps the assigned
    witness visible and cited.
    """

    rows: list[EvidenceRequirement] = []
    for raw in public_requirements:
        if not isinstance(raw, Mapping) or str(raw.get("kind") or "").casefold() != "source_fact":
            continue
        source_path = str(raw.get("source_path") or "").strip().replace("\\", "/")
        scope = str(raw.get("scope") or raw.get("subject") or "").strip()
        modality = str(raw.get("modality") or "required").strip().casefold()
        if not source_path or not scope:
            raise ValueError("source_fact requires source_path and scope")
        if modality not in {"required", "advisory"}:
            raise ValueError(f"unsupported source_fact modality: {modality}")
        provenance = str(raw.get("public_provenance") or "public_task_contract")
        if provenance not in _ALLOWED_REQUIREMENT_PROVENANCE:
            raise ValueError(f"unsupported evidence requirement provenance: {provenance}")
        proof_role = str(raw.get("proof_role") or "generic_fact")
        requirement_id = str(raw.get("requirement_id") or "").strip() or (
            "behavioral_contract:" + scope
        )
        rows.append(EvidenceRequirement(
            requirement_id=requirement_id,
            kind="behavioral_contract",
            value=scope,
            mandatory=modality == "required",
            public_provenance=provenance,
            query_extraction_kind="source_fact",
            proof_role=proof_role,
            source_path=source_path,
            subject=scope,
            relation="source_fact",
            response_mode="value",
        ))
    return tuple(rows)


def build_requirements(*args: Any, **kwargs: Any) -> EvidenceRequirementSet:
    """Bind typed governance and source-scoped obligations to selector policy."""

    requirements = _build_requirements_impl(*args, **kwargs)
    source_facts = _source_fact_requirements(kwargs.get("public_requirements") or ())
    rebound = tuple(
        replace(item, proof_role="project_rule")
        if (
            item.kind == "proof_obligation"
            and item.relation in _GOVERNANCE_PROJECT_RULE_RELATIONS
            and item.proof_role != "project_rule"
        )
        else item
        for item in requirements.requirements
    )
    if source_facts:
        source_fact_ids = {item.requirement_id for item in source_facts}
        rebound = tuple(item for item in rebound if item.requirement_id not in source_fact_ids)
        rebound = tuple(sorted((*rebound, *source_facts), key=lambda item: item.requirement_id))
    if rebound == requirements.requirements:
        return requirements
    return replace(requirements, requirements=rebound)


__all__ = [
    "MAX_SELECTOR_CANDIDATES", "SELECTOR_SCHEMA_VERSION", "EvidenceCandidate",
    "EvidenceRequirement", "EvidenceRequirementSet", "Omission", "SelectionConfig", "SelectionDecision",
    "build_requirements", "docs_selection_config", "library_docs_selection_config", "project_docs_selection_config", "normalize_candidates",
    "patch_selection_config", "select_evidence", "validate_evidence_sufficiency",
]

__all__=[n for n in globals() if not n.startswith('__')]
