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










































@dataclass(frozen=True, slots=True)
class SelectionDecision:
    status: Literal["ok", "insufficient_evidence"]
    selected_candidates: tuple[EvidenceCandidate, ...]
    omissions: tuple[Omission, ...]
    missing_requirements: tuple[str, ...]
    unresolved_conflicts: tuple[str, ...]
    metrics: Mapping[str, Any]
    selector_config_hash: str
    eligibility_contract_hash: str
    candidate_trace_hash: str
    selection_hash: str
    assignments: tuple[EvidenceAssignment, ...]
    support_decision: SupportDecision
    requirements: EvidenceRequirementSet = field(
        default_factory=EvidenceRequirementSet, compare=False, repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.requirements, EvidenceRequirementSet):
            object.__setattr__(self, "requirements", EvidenceRequirementSet(tuple(self.requirements)))

    @property
    def selected_items(self) -> list[dict[str, Any]]:
        return [dict(candidate.original) for candidate in self.selected_candidates]

    def audit_manifest(self) -> dict[str, Any]:
        return {
            "schema_version": SELECTOR_SCHEMA_VERSION,
            "status": self.status,
            "selected_stable_ids": [item.stable_id for item in self.selected_candidates],
            "omissions": [
                {
                    "stable_id": item.stable_id,
                    "reason_code": item.reason_code,
                    "representative_stable_id": item.representative_stable_id,
                }
                for item in self.omissions
            ],
            "omission_counts": _count_reasons(self.omissions),
            "missing_requirements": list(self.missing_requirements),
            "unresolved_conflicts": list(self.unresolved_conflicts),
            "metrics": dict(self.metrics),
            "selector_config_hash": self.selector_config_hash,
            "eligibility_contract_hash": self.eligibility_contract_hash,
            "requirements_hash": self.requirements.requirements_hash,
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
            "assignments": [asdict(item) for item in self.assignments],
            "assignment_hash": self.support_decision.assignment_hash,
            "support_decision": self.support_decision.as_payload(),
        }


def resolve_assignment_unit(
    candidate: EvidenceCandidate,
    assignment: EvidenceAssignment,
) -> AnswerUnit | None:
    if not assignment.unit_id:
        return None
    return next(
        (item for item in candidate.answer_units if item.unit_id == assignment.unit_id),
        None,
    )


def validate_assignment_binding(
    requirement: EvidenceRequirement,
    candidate: EvidenceCandidate,
    assignment: EvidenceAssignment,
) -> bool:
    unit = resolve_assignment_unit(candidate, assignment)
    if unit is None:
        return requirement.kind != "proof_obligation" and assignment.unit_id is None
    if (
        assignment.unit_kind != unit.kind
        or assignment.unit_char_start != unit.char_start
        or assignment.unit_char_end != unit.char_end
        or assignment.unit_content_hash != unit.content_sha256
        or assignment.projected_content_hash != unit.content_sha256
    ):
        return False
    obligation = requirement.as_proof_obligation()
    return obligation is None or local_proof_for_obligation(
        obligation,
        unit,
        source=_candidate_source_view(candidate),
    ).valid


@dataclass(frozen=True, slots=True)
class MixedSelectionLane:
    lane: Literal["project", "library"]
    identity: str
    decision: SelectionDecision

    @property
    def qualifier(self) -> str:
        return f"{self.lane}:{self.identity}"


@dataclass(frozen=True, slots=True)
class AggregateMixedSelectionDecision:
    """Canonical mixed-lane decision with collision-safe child identities."""

    lanes: tuple[MixedSelectionLane, ...]
    selection_decision: SelectionDecision
    child_decision_hash: str
    child_assignment_hash: str

    @property
    def requirements(self) -> EvidenceRequirementSet:
        return self.selection_decision.requirements

    @property
    def selected_candidates(self) -> tuple[EvidenceCandidate, ...]:
        return self.selection_decision.selected_candidates

    @property
    def assignments(self) -> tuple[EvidenceAssignment, ...]:
        return self.selection_decision.assignments

    @property
    def support_decision(self) -> SupportDecision:
        return self.selection_decision.support_decision

    def audit_manifest(self) -> dict[str, Any]:
        return {
            **self.selection_decision.audit_manifest(),
            "mixed_lanes": [
                {
                    "lane": lane.lane,
                    "identity": lane.identity,
                    "decision_hash": lane.decision.support_decision.decision_hash,
                    "assignment_hash": lane.decision.support_decision.assignment_hash,
                }
                for lane in self.lanes
            ],
            "child_decision_hash": self.child_decision_hash,
            "child_assignment_hash": self.child_assignment_hash,
        }


def aggregate_mixed_selection(
    entries: Iterable[tuple[Literal["project", "library"], str, SelectionDecision]],
) -> AggregateMixedSelectionDecision:
    """Combine canonical lane decisions without allowing cross-lane ID aliasing."""

    lanes = tuple(sorted(
        (MixedSelectionLane(lane, str(identity), decision) for lane, identity, decision in entries),
        key=lambda item: (item.lane, item.identity),
    ))
    if len(lanes) < 2:
        raise ValueError("mixed selection requires at least two lane decisions")

    requirements: list[EvidenceRequirement] = []
    candidates: list[EvidenceCandidate] = []
    assignments: list[EvidenceAssignment] = []
    missing: list[str] = []
    conflicts: list[str] = []
    omissions: list[Omission] = []
    for lane in lanes:
        prefix = lane.qualifier + ":"
        requirements.extend(
            replace(requirement, requirement_id=prefix + requirement.requirement_id)
            for requirement in lane.decision.requirements
        )
        candidates.extend(
            replace(
                candidate,
                stable_id=prefix + candidate.stable_id,
                evidence_id=prefix + candidate.evidence_id,
                covered_requirement_ids=frozenset(
                    prefix + requirement_id
                    for requirement_id in candidate.covered_requirement_ids
                ),
            )
            for candidate in lane.decision.selected_candidates
        )
        assignments.extend(
            replace(
                assignment,
                requirement_id=prefix + assignment.requirement_id,
                evidence_id=prefix + assignment.evidence_id,
            )
            for assignment in lane.decision.assignments
        )
        missing.extend(prefix + value for value in lane.decision.missing_requirements)
        conflicts.extend(prefix + value for value in lane.decision.unresolved_conflicts)
        omissions.extend(
            replace(
                omission,
                stable_id=prefix + omission.stable_id,
                representative_stable_id=(
                    prefix + omission.representative_stable_id
                    if omission.representative_stable_id else None
                ),
            )
            for omission in lane.decision.omissions
        )

    requirement_set = EvidenceRequirementSet(tuple(requirements))
    mandatory_ids = tuple(item.requirement_id for item in requirement_set if item.mandatory)
    satisfied_ids = tuple(sorted({item.requirement_id for item in assignments}))
    missing_ids = tuple(sorted(set(mandatory_ids) - set(satisfied_ids)))
    selected_ids = tuple(sorted({item.evidence_id for item in assignments}))
    child_decision_hash = canonical_hash([
        (lane.lane, lane.identity, lane.decision.support_decision.decision_hash)
        for lane in lanes
    ])
    child_assignment_hash = canonical_hash([
        (lane.lane, lane.identity, lane.decision.support_decision.assignment_hash)
        for lane in lanes
    ])
    assignment_hash = canonical_hash({
        "assignments": [asdict(item) for item in assignments],
        "child_assignment_hash": child_assignment_hash,
    })
    selected_documents = {_normalized_source(item.source_identity) for item in candidates}
    selected_tokens = sum(item.token_estimate for item in candidates)
    bounded_materialization_failed = (
        len(selected_documents) > MAX_VISIBLE_DOCUMENTS
        or len(candidates) > MAX_VISIBLE_SPANS
        or selected_tokens + MIXED_WRAPPER_RESERVE_TOKENS > MAX_MIXED_VISIBLE_TOKENS
    )
    if bounded_materialization_failed:
        missing_ids = tuple(sorted({*missing_ids, "bounded_evidence_not_materializable"}))
        missing.append("bounded_evidence_not_materializable")
    supported = (
        not bounded_materialization_failed
        and all(lane.decision.support_decision.answer_supported for lane in lanes)
    )
    base = {
        "answer_supported": supported,
        "support_status": "supported" if supported else "insufficient_evidence",
        "reason_code": (
            None if supported else
            "bounded_evidence_not_materializable" if bounded_materialization_failed else
            "mixed_support_incomplete"
        ),
        "missing_requirement_ids": missing_ids,
        "satisfied_requirement_ids": satisfied_ids,
        "mandatory_requirement_ids": mandatory_ids,
        "mandatory_coverage": (
            len(set(satisfied_ids) & set(mandatory_ids)) / len(mandatory_ids)
            if mandatory_ids else 1.0
        ),
        "selected_evidence_ids": selected_ids,
        "requirements_hash": requirement_set.requirements_hash,
        "selector_config_hash": canonical_hash([lane.decision.selector_config_hash for lane in lanes]),
        "eligibility_contract_hash": canonical_hash([lane.decision.eligibility_contract_hash for lane in lanes]),
        "candidate_trace_hash": canonical_hash([lane.decision.candidate_trace_hash for lane in lanes]),
        "selection_hash": canonical_hash({
            "children": child_decision_hash,
            "selected_evidence_ids": selected_ids,
        }),
        "assignment_hash": assignment_hash,
    }
    support = SupportDecision(
        **base,
        decision_hash=canonical_hash({**base, "child_decision_hash": child_decision_hash}),
        requirements=requirement_set,
    )
    decision = SelectionDecision(
        status="ok" if supported else "insufficient_evidence",
        selected_candidates=tuple(candidates), omissions=tuple(omissions),
        missing_requirements=tuple(missing), unresolved_conflicts=tuple(conflicts),
        metrics={
            "lane_count": len(lanes),
            "selected_documents": len(selected_documents),
            "selected_spans": len(candidates),
            "selected_tokens": selected_tokens,
            "projected_total_tokens": selected_tokens + MIXED_WRAPPER_RESERVE_TOKENS,
            "max_documents": MAX_VISIBLE_DOCUMENTS,
            "max_spans": MAX_VISIBLE_SPANS,
            "hard_tokens": MAX_MIXED_VISIBLE_TOKENS,
        },
        selector_config_hash=support.selector_config_hash,
        eligibility_contract_hash=support.eligibility_contract_hash,
        candidate_trace_hash=support.candidate_trace_hash,
        selection_hash=support.selection_hash, assignments=tuple(assignments),
        support_decision=support, requirements=requirement_set,
    )
    return AggregateMixedSelectionDecision(
        lanes=lanes, selection_decision=decision,
        child_decision_hash=child_decision_hash,
        child_assignment_hash=child_assignment_hash,
    )


def docs_selection_config(max_tokens: int) -> SelectionConfig:
    hard = min(800, max(256, int(max_tokens)))
    return SelectionConfig(
        result_kind="docs_answer", target_tokens=min(650, hard), hard_tokens=hard,
        max_sources=3, max_items_per_source=2,
        max_documents=MAX_VISIBLE_DOCUMENTS, max_spans=MAX_VISIBLE_SPANS,
        wrapper_reserve_tokens=120,
        marginal_utility_threshold=100,
    )


def library_docs_selection_config(max_tokens: int) -> SelectionConfig:
    return replace(docs_selection_config(max_tokens), profile="library_docs_answer")


def project_docs_selection_config(max_tokens: int) -> SelectionConfig:
    return replace(docs_selection_config(max_tokens), profile="project_docs_answer")


def patch_selection_config(max_tokens: int) -> SelectionConfig:
    hard = min(2000, max(256, int(max_tokens)))
    return SelectionConfig(
        result_kind="patch_context", target_tokens=min(1200, hard), hard_tokens=hard,
        max_sources=12, max_items_per_source=3, wrapper_reserve_tokens=min(300, hard // 3),
        marginal_utility_threshold=160,
    )


















def select_evidence(
    items: Iterable[Mapping[str, Any]],
    *,
    question: str,
    config: SelectionConfig,
    trust_contract: Mapping[str, Any] | None = None,
    requirements: EvidenceRequirementSet | Sequence[EvidenceRequirement] | None = None,
    required_evidence_paths: Iterable[str] = (),
    required_target_paths: Iterable[str] = (),
    public_requirements: Iterable[Mapping[str, Any] | str] = (),
    library_requirement_contract: Mapping[str, Iterable[str]] | None = None,
    exact_version: str | None = None,
    project_identity: str | None = None,
    module_id: str | None = None,
) -> SelectionDecision:
    materialized_items = [dict(item) for item in items if isinstance(item, Mapping)]
    requirements = (
        requirements if isinstance(requirements, EvidenceRequirementSet) else
        EvidenceRequirementSet(tuple(requirements)) if requirements else
        build_requirements(
            question,
            required_evidence_paths=required_evidence_paths,
            required_target_paths=required_target_paths,
            public_requirements=public_requirements,
            library_requirement_contract=library_requirement_contract,
            exact_version=exact_version,
            project_identity=project_identity,
            module_id=module_id,
            profile=config.profile,
        )
    )
    canonical_project_identity = _scope_requirement_value(requirements, "project_identity")
    canonical_module_id = _scope_requirement_value(requirements, "module_id")
    if isinstance(requirements, EvidenceRequirementSet):
        if project_identity and canonical_project_identity != project_identity:
            raise ValueError("canonical requirements must contain the requested project identity")
        if module_id and canonical_module_id != module_id:
            raise ValueError("canonical requirements must contain the requested module id")
    invalid_provenance = sorted({
        item.public_provenance
        for item in requirements
        if item.public_provenance not in _ALLOWED_REQUIREMENT_PROVENANCE
    })
    if invalid_provenance:
        raise ValueError(
            "unsupported evidence requirement provenance: " + ", ".join(invalid_provenance)
        )
    v3_answer_units = any(
        item.obligation_kind in {"purpose", "effect"}
        or item.subject_kind is not None
        or (item.obligation_kind == "inventory" and item.item_kind not in {None, "public_tool"})
        for item in requirements
    )
    raw_candidates, omissions = normalize_candidates(
        materialized_items,
        result_kind=config.result_kind,
        include_soft_wrapped_prose=v3_answer_units,
    )
    eligibility_contract_hash = canonical_hash({
        "trust_contract": _canonical_contract_value(trust_contract or {}),
        "project_identity": project_identity,
        "module_id": module_id,
        "result_kind": config.result_kind,
    })
    identity_bindings: dict[str, tuple[Any, ...]] = {}
    identity_collisions: set[str] = set()
    for candidate in raw_candidates:
        binding = (
            candidate.identity_kind,
            candidate.source_identity,
            candidate.parent_logical_id,
            candidate.content_sha256,
            candidate.symbols,
            candidate.exact_terms,
        )
        previous = identity_bindings.setdefault(candidate.stable_id, binding)
        if previous != binding:
            identity_collisions.add(candidate.stable_id)
    if identity_collisions:
        raw_candidates = [
            candidate for candidate in raw_candidates
            if candidate.stable_id not in identity_collisions
        ]
        omissions.extend(
            Omission(stable_id, "invalid_identity")
            for stable_id in sorted(identity_collisions)
        )
    candidate_trace_hash = canonical_hash([
        {
            "stable_id": item.stable_id,
            "identity_kind": item.identity_kind,
            "content_sha256": item.content_sha256,
            "source_identity": item.source_identity,
            "identity_aliases": list(item.identity_aliases),
            "hydration_id": item.hydration_id,
            "rank": item.retrieval_rank,
            "component_ranks": list(item.component_ranks),
            "relevance_millis": item.relevance_millis,
            "authority": item.authority,
            "source_class": item.source_class,
            "version_binding": item.version_binding,
            "resolved_version": item.resolved_version,
            "docs_snapshot_exact": item.docs_snapshot_exact,
            "project_identity": item.project_identity,
            "module_id": item.module_id,
            "doc_scope": item.doc_scope,
            "symbols": list(item.symbols),
            "exact_terms": list(item.exact_terms),
            "instruction_risk_flags": list(item.instruction_risk_flags),
            "freshness": item.freshness,
            "navigation_only": item.navigation_only,
            "token_estimate": item.token_estimate,
        }
        for item in sorted(raw_candidates, key=lambda row: (
            row.stable_id, row.content_sha256, row.retrieval_rank, row.component_ranks,
        ))
    ] + [{
        "input_trace": sorted(
            (_raw_candidate_binding(item) for item in materialized_items),
            key=canonical_hash,
        ),
        "normalization_omissions": sorted(
            (
                {
                    "stable_id": omission.stable_id,
                    "reason_code": omission.reason_code,
                    "representative_stable_id": omission.representative_stable_id,
                }
                for omission in omissions
            ),
            key=canonical_hash,
        ),
    }])
    eligible, hard_omissions, critical_failures = _eligible_candidates(
        raw_candidates, trust_contract or {}, requirements,
        project_identity=canonical_project_identity, module_id=canonical_module_id,
        result_kind=config.result_kind, question=question,
    )
    omissions.extend(hard_omissions)
    policy_requirements = _with_canonical_policy_requirements(requirements, eligible, config.result_kind)
    if policy_requirements != requirements.requirements:
        requirements = EvidenceRequirementSet(
            policy_requirements,
            required_entities=requirements.required_entities,
            required_facets=requirements.required_facets,
            query_extraction_provenance=requirements.query_extraction_provenance,
            query_requirement_spans=requirements.query_requirement_spans,
            retrieval_hints=requirements.retrieval_hints,
            concept_queries=requirements.concept_queries,
            answer_contract_hash=requirements.answer_contract_hash,
            lifecycle_intent=requirements.lifecycle_intent,
        )
    covered = [
        _with_coverage(
            candidate,
            requirements,
            factual_only=(
                config.profile == "project_docs_answer"
                and not any(item.proof_role == "document_statement" for item in requirements)
            ),
        )
        for candidate in eligible
    ]
    mandatory_ids = {item.requirement_id for item in requirements if item.mandatory}
    compositional_question = bool(getattr(requirements, "parse_trace", ()))

    def ordering_key(candidate: EvidenceCandidate) -> tuple[Any, ...]:
        base = (
            0 if candidate.covered_requirement_ids & mandatory_ids else 1,
        )
        if compositional_question:
            # QuestionPlan candidates are deduplicated only after local proof
            # has been computed.  Prefer the candidate carrying the strongest
            # complete mandatory witness before token compactness/retrieval
            # rank, otherwise a short command from the same parent can hide a
            # more complete procedure summary.  Legacy v1-v3 ordering stays
            # byte-for-byte compatible.
            mandatory_witnesses = tuple(
                witness for witness in candidate.requirement_witnesses
                if witness.requirement_id in mandatory_ids
            )
            base += (
                -len(candidate.covered_requirement_ids & mandatory_ids),
                -sum(witness.completeness_score for witness in mandatory_witnesses),
            )
        return (*base, *_candidate_preference(candidate))

    ordered = sorted(covered, key=ordering_key)
    if len(ordered) > config.max_candidates:
        for candidate in ordered[config.max_candidates:]:
            omissions.append(Omission(candidate.stable_id, "candidate_cap"))
        ordered = ordered[:config.max_candidates]
    deduped, dedupe_omissions = _deduplicate(ordered, config, requirements)
    omissions.extend(dedupe_omissions)
    conflicts = _authority_conflicts(deduped)
    mandatory = {item.requirement_id for item in requirements if item.mandatory}
    selected, missing, selection_omissions = _reserve_and_select(
        deduped,
        mandatory,
        config,
        prefer_proof_completeness=compositional_question,
    )
    omissions.extend(selection_omissions)
    selected_documents = {_normalized_source(item.source_identity) for item in selected}
    bounded_materialization_failed = config.result_kind == "docs_answer" and (
        len(selected) > config.max_spans or len(selected_documents) > config.max_documents
    )
    if bounded_materialization_failed:
        missing.add("bounded_evidence_not_materializable")
    missing.update(critical_failures)
    missing.update(f"stable_identity_collision:{value}" for value in identity_collisions)
    if config.result_kind == "docs_answer" and selected and all(item.navigation_only for item in selected):
        missing.add("factual_source_evidence")
    if config.profile == "project_docs_answer" and not mandatory:
        missing.add("project_answer_requirement")
    status: Literal["ok", "insufficient_evidence"] = (
        "ok" if selected and not missing and not conflicts else "insufficient_evidence"
    )
    selected = sorted(selected, key=lambda item: (
        0 if item.covered_requirement_ids & mandatory else 1,
        *_candidate_preference(item),
    ))
    selected_tokens = sum(item.token_estimate for item in selected)
    selected_fit_tokens = sum(item.fit_token_estimate for item in selected)
    metrics = {
        "candidate_count": len(raw_candidates),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected_sources": len({_normalized_source(item.source_identity) for item in selected}),
        "selected_documents": len(selected_documents),
        "max_documents": config.max_documents,
        "max_spans": config.max_spans,
        "selected_tokens": selected_tokens,
        "wrapper_reserve_tokens": config.wrapper_reserve_tokens,
        "projected_total_tokens": selected_tokens + config.wrapper_reserve_tokens,
        "serialized_projected_tokens": (
            selected_fit_tokens + DOCS_SERIALIZATION_RESERVE_TOKENS
            if config.result_kind == "docs_answer"
            else selected_tokens + config.wrapper_reserve_tokens
        ),
        "hard_tokens": config.hard_tokens,
        "mandatory_requirements": len(mandatory),
        "mandatory_covered": len(mandatory & set().union(*(
            item.covered_requirement_ids for item in selected
        ))) if selected else 0,
        "mandatory_coverage_millis": int(
            len(mandatory & set().union(*(item.covered_requirement_ids for item in selected)))
            * 1000 / max(1, len(mandatory))
        ) if selected else 0,
        "requirements_hash": requirements.requirements_hash,
        "omission_counts": _count_reasons(omissions),
        "selected_parents": len({item.parent_logical_id for item in selected if item.parent_logical_id}),
        "selected_children": sum(item.identity_kind == "stable_child" for item in selected),
        "required_facts_per_1000_tokens_millis": int(
            len(set().union(*(item.covered_requirement_ids for item in selected)) if selected else set())
            * 1_000_000 / max(1, selected_tokens)
        ),
        "redundant_visible_token_ratio_millis": _redundant_token_ratio_millis(selected, config),
        "cache": "disabled" if not config.cache_enabled else "miss",
        "selected_feature_trace": _selected_feature_trace(selected, mandatory),
        "candidate_to_selected_ratio_millis": int(len(raw_candidates) * 1000 / max(1, len(selected))),
        "reported_token_mismatches": sum(
            1 for item in raw_candidates
            if item.reported_token_estimate is not None
            and item.reported_token_estimate != _estimated_tokens(item.projected_text)
        ),
    }
    sorted_omissions = tuple(sorted(
        omissions,
        key=lambda item: (
            item.stable_id, item.reason_code, item.representative_stable_id or ""
        ),
    ))
    assignment_rows: list[EvidenceAssignment] = []
    for requirement in sorted(
        (item for item in requirements if item.requirement_id in mandatory),
        key=lambda item: item.requirement_id,
    ):
        matching: list[tuple[EvidenceCandidate, RequirementWitness | None]] = []
        for candidate in selected:
            if requirement.requirement_id not in candidate.covered_requirement_ids:
                continue
            witness = _candidate_requirement_witness(candidate, requirement.requirement_id)
            matching.append((candidate, witness))
        if not matching:
            continue
        matching.sort(key=lambda pair: _assignment_preference(requirement, pair[0], pair[1]))
        candidate, witness = matching[0]
        if witness is not None:
            if witness.unit_char_start is None or witness.unit_char_end is None:
                absolute_start = absolute_end = absolute_line = None
            else:
                absolute_start = (
                    candidate.char_start + witness.unit_char_start
                    if candidate.char_start is not None else witness.unit_char_start
                )
                absolute_end = (
                    candidate.char_start + witness.unit_char_end
                    if candidate.char_start is not None else witness.unit_char_end
                )
                relative_line = candidate.display_text[:witness.unit_char_start].count("\n")
                absolute_line = (
                    candidate.line_start + relative_line
                    if candidate.line_start is not None else relative_line
                )
            projected_hash = witness.unit_content_hash
            qualifier_text = witness.unit_text
        else:
            absolute_start, absolute_end = candidate.char_start, candidate.char_end
            absolute_line = candidate.line_start
            projected_hash = hashlib.sha256(candidate.projected_text.encode("utf-8")).hexdigest()
            qualifier_text = candidate.projected_text
        assignment_rows.append(EvidenceAssignment(
            requirement_id=requirement.requirement_id,
            evidence_id=candidate.stable_id,
            path=candidate.path_or_url,
            char_start=absolute_start,
            char_end=absolute_end,
            line_start=absolute_line,
            line_end=absolute_line,
            projected_content_hash=projected_hash,
            proof_role=requirement.proof_role,
            qualifiers=requirement.qualifiers or _observed_qualifiers(qualifier_text),
            unit_id=witness.unit_id if witness else None,
            unit_kind=witness.unit_kind if witness else None,
            unit_char_start=witness.unit_char_start if witness else None,
            unit_char_end=witness.unit_char_end if witness else None,
            unit_content_hash=witness.unit_content_hash if witness else None,
        ))
    assignments = tuple(assignment_rows)
    assigned_requirement_ids = {item.requirement_id for item in assignments}
    assigned_evidence_ids = tuple(sorted({item.evidence_id for item in assignments}))
    missing.update(mandatory - assigned_requirement_ids)
    if status == "ok" and mandatory - assigned_requirement_ids:
        status = "insufficient_evidence"
    assignment_hash = canonical_hash([asdict(item) for item in assignments])
    selection_hash = canonical_hash({
        "schema_version": SELECTOR_SCHEMA_VERSION,
        "config_hash": config.config_hash,
        "eligibility_contract_hash": eligibility_contract_hash,
        "candidate_trace_hash": candidate_trace_hash,
        "requirements": requirements.hash_payload,
        "selected": [_selected_identity(item) for item in selected],
        "assignments": [asdict(item) for item in assignments],
        "omissions": [asdict(item) for item in sorted_omissions],
        "missing": sorted(missing), "conflicts": sorted(conflicts),
    })
    covered_ids = (
        set().union(*(item.covered_requirement_ids for item in selected))
        if selected else set()
    )
    covered_mandatory = mandatory & assigned_requirement_ids
    mandatory_coverage = (
        len(covered_mandatory) / len(mandatory)
        if mandatory else (1.0 if selected else 0.0)
    )
    public_missing = tuple(sorted(missing))
    public_satisfied = tuple(sorted(covered_ids))
    public_mandatory = tuple(sorted(mandatory))
    unresolved_reason = next((
        reason for reason in requirements.unresolved_parts
        if reason in {"unresolved_query_subject", "unresolved_requested_operation", "unsupported_compound_clause"}
    ), None)
    reason_code = (
        None if status == "ok" else
        unresolved_reason if unresolved_reason else
        "bounded_evidence_not_materializable" if bounded_materialization_failed else
        "authority_conflict" if conflicts else
        "required_evidence_missing" if missing else
        "no_eligible_evidence"
    )
    support_payload = {
        "answer_supported": status == "ok",
        "support_status": "supported" if status == "ok" else "insufficient_evidence",
        "reason_code": reason_code,
        "missing_requirement_ids": public_missing,
        "satisfied_requirement_ids": public_satisfied,
        "mandatory_requirement_ids": public_mandatory,
        "mandatory_coverage": mandatory_coverage,
        "selected_evidence_ids": assigned_evidence_ids,
        "requirements_hash": requirements.requirements_hash,
        "selector_config_hash": config.config_hash,
        "eligibility_contract_hash": eligibility_contract_hash,
        "candidate_trace_hash": candidate_trace_hash,
        "selection_hash": selection_hash,
        "assignment_hash": assignment_hash,
    }
    support_decision = SupportDecision(
        **support_payload,
        decision_hash=canonical_hash(support_payload),
        requirements=requirements,
    )
    return SelectionDecision(
        status=status, selected_candidates=tuple(selected), omissions=sorted_omissions,
        missing_requirements=tuple(sorted(missing)), unresolved_conflicts=tuple(sorted(conflicts)),
        metrics=metrics, selector_config_hash=config.config_hash,
        eligibility_contract_hash=eligibility_contract_hash,
        candidate_trace_hash=candidate_trace_hash, selection_hash=selection_hash,
        assignments=assignments, support_decision=support_decision, requirements=requirements,
    )


def validate_evidence_sufficiency(
    decision: SelectionDecision,
    requirements: EvidenceRequirementSet | Sequence[EvidenceRequirement] = (),
    *,
    result_kind: str | None = None,
) -> list[str]:
    errors: list[str] = []
    requirements = (
        requirements if isinstance(requirements, EvidenceRequirementSet) else
        EvidenceRequirementSet(tuple(requirements)) if requirements else
        decision.requirements
    )
    mandatory = {item.requirement_id for item in requirements if item.mandatory}
    covered = set().union(*(item.covered_requirement_ids for item in decision.selected_candidates)) if decision.selected_candidates else set()
    if decision.status == "ok" and not decision.selected_candidates:
        errors.append("successful selection requires evidence")
    if decision.status == "ok" and mandatory - covered:
        errors.append("successful selection is missing mandatory requirements")
    assigned = {item.requirement_id for item in decision.assignments}
    if decision.status == "ok" and mandatory - assigned:
        errors.append("successful selection is missing mandatory assignments")
    candidates_by_id = {item.stable_id: item for item in decision.selected_candidates}
    requirements_by_id = {item.requirement_id: item for item in requirements}
    for assignment in decision.assignments:
        candidate = candidates_by_id.get(assignment.evidence_id)
        requirement = requirements_by_id.get(assignment.requirement_id)
        if candidate is None or requirement is None:
            errors.append("evidence assignment does not resolve to canonical inputs")
            continue
        if assignment.unit_id is None:
            if result_kind == "docs_answer" and requirement.kind == "proof_obligation":
                errors.append("typed docs assignment requires an answer unit")
            continue
        unit = next((item for item in candidate.answer_units if item.unit_id == assignment.unit_id), None)
        if unit is None:
            errors.append("evidence assignment answer unit is missing")
            continue
        if (
            assignment.unit_kind != unit.kind
            or assignment.unit_char_start != unit.char_start
            or assignment.unit_char_end != unit.char_end
            or assignment.unit_content_hash != unit.content_sha256
            or assignment.projected_content_hash != unit.content_sha256
        ):
            errors.append("evidence assignment answer unit binding is invalid")
            continue
        obligation = requirement.as_proof_obligation()
        if obligation is not None and not local_proof_for_obligation(
            obligation, unit, source=_candidate_source_view(candidate),
        ).valid:
            errors.append("typed evidence assignment no longer proves its obligation")
    if decision.status == "ok" and (decision.missing_requirements or decision.unresolved_conflicts):
        errors.append("successful selection cannot contain unresolved requirements or conflicts")
    if len({item.stable_id for item in decision.selected_candidates}) != len(decision.selected_candidates):
        errors.append("selected stable IDs must be unique")
    if len({(item.stable_id, item.content_sha256) for item in decision.selected_candidates}) != len(decision.selected_candidates):
        errors.append("selected stable identity bindings must be unique")
    if decision.metrics.get("projected_total_tokens", 0) > decision.metrics.get("hard_tokens", 0):
        errors.append("selected whole-item bundle exceeds the hard token budget")
    if result_kind == "docs_answer" and decision.status == "ok" and all(
        item.navigation_only for item in decision.selected_candidates
    ):
        errors.append("successful docs selection requires factual evidence")
    if result_kind == "patch_context" and decision.status == "ok" and not any(
        item.symbols or _PATCH_FACT_RE.search(item.display_text)
        for item in decision.selected_candidates
    ):
        errors.append("successful patch selection requires actionable cited evidence")
    expected = canonical_hash({
        "schema_version": SELECTOR_SCHEMA_VERSION,
        "config_hash": decision.selector_config_hash,
        "eligibility_contract_hash": decision.eligibility_contract_hash,
        "candidate_trace_hash": decision.candidate_trace_hash,
        "requirements": requirements.hash_payload,
        "selected": [_selected_identity(item) for item in decision.selected_candidates],
        "assignments": [asdict(item) for item in decision.assignments],
        "omissions": [asdict(item) for item in decision.omissions],
        "missing": list(decision.missing_requirements),
        "conflicts": list(decision.unresolved_conflicts),
    })
    if expected != decision.selection_hash:
        errors.append("selection hash does not match the decision")
    return errors


def _scope_requirement_value(
    requirements: Sequence[EvidenceRequirement], kind: str,
) -> str | None:
    values = {item.value for item in requirements if item.kind == kind and item.mandatory}
    if len(values) > 1:
        raise ValueError(f"canonical requirements contain conflicting {kind} scope")
    return next(iter(values), None)


def _eligible_candidates(
    candidates: Sequence[EvidenceCandidate],
    trust_contract: Mapping[str, Any],
    requirements: Sequence[EvidenceRequirement],
    *,
    project_identity: str | None,
    module_id: str | None,
    result_kind: str,
    question: str,
) -> tuple[list[EvidenceCandidate], list[Omission], set[str]]:
    forbidden = _trust_source_keys(trust_contract, "rejected") | _trust_source_keys(trust_contract, "risky")
    exact_versions = {item.value for item in requirements if item.kind == "exact_version" and item.mandatory}
    canonical_policy_required = any(
        item.kind == "canonical_policy" and item.mandatory for item in requirements
    )
    legal_intent = bool(
        set(_TOKEN_RE.findall(question.casefold())).intersection(_LEGAL_INTENT_TERMS)
    )
    query_identifiers = _query_identifier_values(requirements)
    eligible: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    critical: set[str] = set()
    for candidate in candidates:
        reason: OmissionReason | None = None
        if set(candidate.identity_aliases) & forbidden:
            reason = "forbidden_source"
        elif candidate.freshness.casefold() == "stale":
            reason = "stale"
            if candidate.authority == "canonical":
                critical.add("stale_canonical_evidence")
        elif candidate.instruction_risk_flags:
            reason = "instruction_risk"
            if candidate.authority == "canonical":
                critical.add("risky_canonical_evidence")
        elif canonical_policy_required and candidate.source_class.casefold() in {
            "generated", "changelog", "research", "community", "mirror",
        }:
            reason = "outside_scope"
        elif project_identity and candidate.project_identity != project_identity:
            reason = "outside_scope"
        elif module_id and candidate.module_id != module_id:
            reason = "outside_scope"
        elif exact_versions and _version_rank(candidate.version_binding) == 2:
            reason = "unknown_version"
        elif exact_versions and candidate.resolved_version not in exact_versions:
            reason = "wrong_version"
        elif result_kind == "docs_answer" and candidate.navigation_only:
            reason = "navigation_only"
        elif (
            candidate.source_class.casefold() == "legal"
            and not legal_intent
        ):
            reason = "query_intent_mismatch"
        elif _query_identifier_conflict(candidate, query_identifiers):
            reason = "query_identifier_conflict"
        if reason:
            omissions.append(Omission(candidate.stable_id, reason))
        else:
            eligible.append(candidate)
    return eligible, omissions, critical


def _query_identifier_conflict(
    candidate: EvidenceCandidate,
    query_identifiers: Sequence[str],
) -> bool:
    """Reject prefix lookalikes without excluding unrelated supporting evidence."""

    haystack = "\n".join((candidate.display_text, *candidate.symbols)).casefold()
    for value in query_identifiers:
        exact_match = False
        prefix_match = False
        start = haystack.find(value)
        while start >= 0:
            before = haystack[start - 1] if start else ""
            after_index = start + len(value)
            after = haystack[after_index] if after_index < len(haystack) else ""
            if not (before == "_" or before.isalnum()):
                if after == "_" or after.isalnum():
                    prefix_match = True
                else:
                    exact_match = True
                    break
            start = haystack.find(value, start + 1)
        if prefix_match and not exact_match:
            return True
    return False


def _query_identifier_values(
    requirements: Sequence[EvidenceRequirement],
) -> tuple[str, ...]:
    return tuple(
        requirement.value.casefold()
        for requirement in requirements
        if requirement.public_provenance == "query_exact_term"
        and (
            "_" in requirement.value
            or "." in requirement.value
            or "::" in requirement.value
            or (
                any(char.isupper() for char in requirement.value[1:])
                and any(char.islower() for char in requirement.value)
            )
        )
    )


def _trust_source_keys(contract: Mapping[str, Any], field: str) -> set[str]:
    sources = contract.get("sources") if isinstance(contract.get("sources"), Mapping) else {}
    aliases = [field, f"{field}_sources"]
    values: list[Any] = []
    for key in aliases:
        for raw in (contract.get(key), sources.get(key)):
            values.extend(raw if isinstance(raw, list) else [raw] if raw else [])
    return {
        _normalized_source(
            value.get("source") or value.get("path") or value.get("url")
            or value.get("canonical_id") or value.get("library_id") or ""
            if isinstance(value, Mapping) else value
        )
        for value in values
        if _normalized_source(
            value.get("source") or value.get("path") or value.get("url")
            or value.get("canonical_id") or value.get("library_id") or ""
            if isinstance(value, Mapping) else value
        )
    }


def _facet_requirement_matches(value: str, haystack: str) -> bool:
    kind, _, detail = value.partition(":")
    if kind == "comparison":
        left, separator, right = detail.partition(":")
        return bool(
            separator
            and requirement_value_visible(left, haystack)
            and requirement_value_visible(right, haystack)
            and (
                re.search(r"\b(?:while|whereas|but|instead|compare|difference|versus|vs\.?|unlike|does\s+not)\b", haystack)
                or re.search(r"\breturns?\b.*\b(?:runs|collects|schedules)\b", haystack)
            )
        )
    if kind == "result_access":
        entity, separator, _ = detail.partition(":")
        return bool(
            separator
            and requirement_value_visible(entity, haystack)
            and "result" in haystack
            and re.search(r"\b(?:obtain|get|retrieve|await)\b", haystack)
        )
    if kind == "request_handling":
        return any(
            re.search(r"\brequest\b|\bзапрос", sentence)
            and re.search(r"\b(?:handles?|process(?:es|ing)?|dispatch(?:es|ing)?|routes?|validates?|forwards?)\b", sentence)
            and re.search(r"\b(?:handler|router|server|tool|transport|service|registry)\b", sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind == "architecture":
        component_pattern = (
            r"\b(?:server|handler|router|service|transport|registry|adapter|layer|module|"
            r"ui|application|domain|infrastructure)\b"
        )
        relation_pattern = (
            r"\b(?:routes?|dispatch(?:es)?|coordinates?|connects?|composes?|through|"
            r"состоит|связывает)\b|->"
        )
        return any(
            len(set(re.findall(component_pattern, sentence))) >= 2
            and re.search(relation_pattern, sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind == "responsiveness":
        return any(
            re.search(r"\b(?:non[- ]blocking|asynchronous|async|does\s+not\s+block)\b", sentence)
            and re.search(r"\b(?:worker|background|event\s+loop|queue|thread|task)\b", sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind in {"behavior", "usage", "workflow"}:
        patterns = {
            "behavior": r"\b(?:reports?|returns?|provides?|shows?|contains?|lists?|возвращает|показывает|сообщает|содержит|перечисляет)\b",
            "usage": r"\b(?:use|used|call|called|when|should|использовать|используется|применять|применяется|когда)\b",
            "workflow": r"\b(?:run|follow|then|after|before|retry|prepare|first|next|запустить|выполнить|затем|после|перед|повторить|сначала)\b",
        }
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack):
            if not requirement_value_visible(detail, sentence):
                continue
            if re.search(
                r"\b(?:does|do|did|is|are|was|were|should|must|can|could|would|will)\s+not\b"
                r"|\b(?:never|cannot|can't|mustn't|shouldn't)\b"
                r"|\b(?:не\s+следует|не\s+нужно|нельзя|никогда\s+не)\b",
                sentence,
            ):
                continue
            entity_pattern = re.escape(detail.casefold())
            marker_pattern = patterns[kind]
            if kind == "behavior":
                relational_match = re.search(
                    rf"{entity_pattern}(?:\W+\w+){{0,6}}?\W+{marker_pattern}", sentence,
                )
            else:
                relational_match = re.search(
                    rf"(?:{entity_pattern}(?:\W+\w+){{0,6}}?\W+{marker_pattern}"
                    rf"|{marker_pattern}(?:\W+\w+){{0,6}}?\W+{entity_pattern})",
                    sentence,
                )
            if kind == "workflow":
                markers = re.findall(marker_pattern, sentence)
                has_sequence = re.search(
                    r"\b(?:then|after|before|first|next|затем|после|перед|сначала)\b",
                    sentence,
                )
                relational_match = bool(relational_match and len(markers) >= 2 and has_sequence)
            if relational_match:
                return True
        return False
    if kind == "recall_mechanism":
        return bool(re.search(r"\b(?:exact[- ]term|exact match|exact query)\b", haystack) and re.search(
            r"\b(?:recall|retrieve|retrieval|match|lookup)\b", haystack,
        ))
    if kind == "authority_invariant":
        return bool(re.search(r"\b(?:authority|scope)\b", haystack) and re.search(
            r"\b(?:unchanged|preserv(?:e|es|ed)|without\s+(?:widening|expanding|broadening)|does\s+not\s+(?:widen|expand|broaden))\b",
            haystack,
        ))
    return False


def _code_group_fragments(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(
        str(fragment).strip()
        for fragment in decoded
        if str(fragment).strip()
    )


def _candidate_code_blocks(candidate: EvidenceCandidate) -> tuple[str, ...]:
    metadata = candidate.original.get("metadata")
    snippets = metadata.get("code_snippets") if isinstance(metadata, Mapping) else None
    if not isinstance(snippets, (list, tuple)):
        snippets = ()
    blocks = [
        str(item.get("code") or "").strip()
        for item in snippets or ()
        if isinstance(item, Mapping) and str(item.get("code") or "").strip()
    ]
    if blocks:
        return tuple(blocks)
    return tuple(match.group(1).strip() for match in re.finditer(
        r"```[^\n]*\n(.*?)```", candidate.display_text, re.DOTALL,
    ) if match.group(1).strip())


def _code_group_requirement_matches(value: str, candidate: EvidenceCandidate) -> bool:
    fragments = _code_group_fragments(value)
    return bool(fragments) and any(
        all(fragment.casefold() in block.casefold() for fragment in fragments)
        for block in _candidate_code_blocks(candidate)
    )


def requirement_probe_query(requirement: EvidenceRequirement) -> str | None:
    """Return a bounded lexical witness query for one canonical requirement."""

    obligation = requirement.as_proof_obligation()
    if obligation is not None:
        parts = (
            obligation.subject,
            *obligation.subject_aliases,
            obligation.attribute,
            obligation.relation,
            obligation.target,
            obligation.expected_value,
            obligation.item_kind,
            obligation.context,
        )
        value = " ".join(dict.fromkeys(
            str(part).strip() for part in parts if str(part or "").strip()
        ))
        return value[:320] or None
    if requirement.kind in {"exact_term", "entity"}:
        return requirement.value.strip() or None
    if requirement.kind == "facet":
        kind, _, detail = requirement.value.partition(":")
        if kind == "comparison":
            left, separator, right = detail.partition(":")
            return f"{left} {right}" if separator else None
        if kind == "result_access":
            entity, separator, _ = detail.partition(":")
            return f"{entity} result" if separator else None
    if requirement.kind == "code_group":
        fragments = _code_group_fragments(requirement.value)
        return " ".join(fragments) if fragments else None
    return None


def _candidate_source_view(candidate: EvidenceCandidate) -> dict[str, Any]:
    metadata = candidate.original.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    view = dict(metadata)
    view.update({
        "path": candidate.path_or_url,
        "source": candidate.path_or_url,
        "title": candidate.section,
        "heading_path": candidate.section,
        "project_identity": candidate.project_identity,
        "module_id": candidate.module_id,
        "authority": candidate.original.get("authority") or candidate.authority,
        "project_doc_authority": (
            candidate.original.get("project_doc_authority")
            or metadata.get("project_doc_authority")
            or candidate.original.get("authority")
            or candidate.authority
        ),
        "project_doc_lifecycle_status": (
            candidate.original.get("project_doc_lifecycle_status")
            or metadata.get("project_doc_lifecycle_status")
            or candidate.original.get("lifecycle_status")
            or metadata.get("lifecycle_status")
            or "active"
        ),
    })
    return view


def _legacy_requirement_matches_unit(
    requirement: EvidenceRequirement,
    unit: AnswerUnit,
    candidate: EvidenceCandidate,
) -> bool:
    text = unit.text.casefold()
    if not unit.proposition and requirement.kind not in {"code_group"}:
        return False
    if requirement.kind in {"exact_term", "entity"}:
        matches = requirement_value_visible(requirement.value, unit.text)
    elif requirement.kind == "facet":
        matches = _facet_requirement_matches(requirement.value, text)
    elif requirement.kind == "code_group":
        fragments = _code_group_fragments(requirement.value)
        matches = bool(fragments) and all(fragment.casefold() in text for fragment in fragments)
    elif requirement.kind == "canonical_policy":
        matches = bool(_PATCH_FACT_RE.search(unit.text))
    elif requirement.kind in {"evidence_path", "target_path", "project_identity", "module_id", "exact_version", "exact_snapshot"}:
        # These obligations are bound by source metadata.  They still need a
        # concrete visible proposition so a successful answer never cites a
        # heading-only or empty chunk.
        matches = unit.proposition
    elif requirement.kind == "unsupported_query":
        matches = False
    else:
        matches = requirement.value.casefold() in text
    if matches and requirement.qualifiers:
        matches = all(_QUALIFIER_PATTERNS[value].search(unit.text) for value in requirement.qualifiers)
    return bool(matches)


def _witness_for_requirement(
    requirement: EvidenceRequirement,
    candidate: EvidenceCandidate,
) -> RequirementWitness | None:
    obligation = requirement.as_proof_obligation()
    if obligation is not None:
        matched = best_local_proof(
            obligation,
            candidate.answer_units,
            source=_candidate_source_view(candidate),
        )
        if matched is None:
            return None
        unit, proof = matched
    else:
        matching_units = [
            unit for unit in candidate.answer_units
            if _legacy_requirement_matches_unit(requirement, unit, candidate)
        ]
        if not matching_units:
            return None
        matching_units.sort(key=lambda unit: (
            0 if unit.proposition else 1,
            len(unit.text),
            unit.char_start if unit.char_start is not None else 10**9,
            unit.unit_id,
        ))
        unit = matching_units[0]
        proof = LocalProof(
            True,
            subject_score=1,
            relation_score=1,
            value_score=1,
            completeness_score=3,
            reason="legacy_local_unit",
        )
    return RequirementWitness(
        requirement_id=requirement.requirement_id,
        unit_id=unit.unit_id,
        unit_kind=unit.kind,
        unit_text=unit.text,
        unit_char_start=unit.char_start,
        unit_char_end=unit.char_end,
        unit_content_hash=unit.content_sha256,
        subject_score=proof.subject_score,
        relation_score=proof.relation_score,
        value_score=proof.value_score,
        completeness_score=proof.completeness_score,
    )


def _with_coverage(
    candidate: EvidenceCandidate,
    requirements: Sequence[EvidenceRequirement],
    *,
    factual_only: bool,
) -> EvidenceCandidate:
    # Paths, headings, and symbols aid retrieval but cannot prove a factual
    # answer. Requirements must match model-visible source text.
    haystack = candidate.display_text.casefold() if factual_only else "\n".join([
        candidate.display_text, candidate.path_or_url, candidate.section,
        " ".join(candidate.symbols), candidate.version_binding, candidate.resolved_version,
    ]).casefold()
    stripped_display = candidate.display_text.strip()
    display_words = re.findall(r"\w+", stripped_display, re.UNICODE)
    incomplete_span = factual_only and bool(
        len(stripped_display) <= 80
        and "\n" not in stripped_display
        and (
            re.fullmatch(r"#{1,6}\s+\S.*", stripped_display) is not None
            or
            stripped_display.endswith(':')
            or (len(display_words) <= 2 and not re.search(r"[.!?;]", stripped_display))
        )
    )
    source = _normalized_source(candidate.path_or_url)
    covered: set[str] = set()
    witnesses: list[RequirementWitness] = []
    for requirement in requirements:
        witness: RequirementWitness | None = None
        value = requirement.value.casefold()
        if requirement.kind == "proof_obligation":
            witness = _witness_for_requirement(requirement, candidate)
            matches = witness is not None
        elif requirement.kind == "canonical_policy":
            matches = candidate.stable_id == requirement.value
        elif requirement.kind in {"evidence_path", "target_path"}:
            wanted = _normalized_source(requirement.value)
            matches = source == wanted or source.endswith("/" + wanted) or wanted.endswith("/" + source)
        elif requirement.kind == "exact_version":
            matches = candidate.resolved_version.casefold() == value and _version_rank(candidate.version_binding) == 0
        elif requirement.kind == "exact_snapshot":
            matches = candidate.docs_snapshot_exact is True
        elif requirement.kind == "project_identity":
            matches = candidate.project_identity == requirement.value
        elif requirement.kind == "module_id":
            matches = candidate.module_id == requirement.value
        elif requirement.kind == "exact_term":
            matches = requirement_value_visible(requirement.value, haystack)
        elif requirement.kind == "entity":
            matches = requirement_value_visible(requirement.value, haystack)
        elif requirement.kind == "facet":
            matches = _facet_requirement_matches(requirement.value, haystack)
        elif requirement.kind == "code_group":
            matches = _code_group_requirement_matches(requirement.value, candidate)
        elif requirement.kind == "unsupported_query":
            matches = False
        else:
            matches = value in haystack
        if matches and incomplete_span and requirement.kind not in {"evidence_path", "target_path"}:
            matches = False
        if matches and requirement.proof_role == "document_statement":
            scoped_paths = {
                _normalized_source(item.value)
                for item in requirements
                if item.kind == "evidence_path"
            }
            matches = bool(scoped_paths) and source in scoped_paths
        if matches and requirement.proof_role == "implementation_fact":
            matches = candidate.source_class in {"source_snippet", "test", "project_file"}
        if matches and requirement.proof_role == "project_rule":
            matches = candidate.authority == "canonical" and candidate.source_class not in {
                "repo_map", "code_graph", "absent_in_source",
            }
        if matches and requirement.proof_role == "dependency_fact":
            matches = candidate.source_class not in {
                "repo_map", "code_graph", "absent_in_source", "project_file", "source_snippet", "test",
            } and _version_rank(candidate.version_binding) == 0
        if matches and requirement.qualifiers:
            matches = all(
                _QUALIFIER_PATTERNS[qualifier].search(candidate.projected_text)
                for qualifier in requirement.qualifiers
            )
        if matches and (factual_only or requirement.kind == "proof_obligation"):
            witness = witness or _witness_for_requirement(requirement, candidate)
            matches = witness is not None
        if matches:
            covered.add(requirement.requirement_id)
            if witness is not None:
                witnesses.append(witness)
    ordered_witnesses = tuple(sorted(
        witnesses,
        key=lambda item: (
            item.requirement_id,
            item.unit_char_start if item.unit_char_start is not None else 10**9,
            item.unit_id,
        ),
    ))
    witness_units = tuple(
        unit
        for witness in ordered_witnesses
        for unit in candidate.answer_units
        if unit.unit_id == witness.unit_id
    )
    material = materialize_answer_units(candidate.display_text, witness_units)
    fit_tokens = candidate.fit_token_estimate
    visible_tokens = candidate.token_estimate
    if material:
        visible_tokens = _estimated_tokens(material)
        fit_tokens = _docs_answer_candidate_tokens(
            stable_id=candidate.stable_id,
            path=candidate.path_or_url,
            section=candidate.section,
            projected=material,
            version_binding=candidate.version_binding,
        )
    return replace(
        candidate,
        token_estimate=visible_tokens,
        fit_token_estimate=fit_tokens,
        covered_requirement_ids=frozenset(covered),
        requirement_witnesses=ordered_witnesses,
    )


def _with_canonical_policy_requirements(
    requirements: Sequence[EvidenceRequirement],
    candidates: Sequence[EvidenceCandidate],
    result_kind: str,
) -> tuple[EvidenceRequirement, ...]:
    if result_kind != "patch_context":
        return tuple(requirements)
    additions = [
        EvidenceRequirement(
            requirement_id=f"canonical_policy:{candidate.stable_id}",
            kind="canonical_policy",
            value=candidate.stable_id,
            public_provenance="canonical_policy_requirement",
        )
        for candidate in candidates
        if candidate.authority == "canonical"
        and str(candidate.original.get("authority") or "").casefold() in {
            "source_of_truth", "project_rule", "explicit_agent_policy",
        }
        and _PATCH_FACT_RE.search(candidate.display_text)
    ]
    unique = {item.requirement_id: item for item in (*requirements, *additions)}
    return tuple(unique[key] for key in sorted(unique))


def _candidate_preference(candidate: EvidenceCandidate) -> tuple[Any, ...]:
    return (
        0 if candidate.authority == "canonical" else 1,
        _version_rank(candidate.version_binding),
        0 if candidate.docs_snapshot_exact is True else 1,
        -len(candidate.covered_requirement_ids),
        candidate.token_estimate,
        -candidate.relevance_millis,
        candidate.retrieval_rank,
        candidate.stable_id,
    )


def _candidate_requirement_witness(
    candidate: EvidenceCandidate,
    requirement_id: str,
) -> RequirementWitness | None:
    return next(
        (item for item in candidate.requirement_witnesses if item.requirement_id == requirement_id),
        None,
    )


def _lifecycle_assignment_rank(
    requirement: EvidenceRequirement,
    candidate: EvidenceCandidate,
) -> int:
    lifecycle = str(
        _candidate_source_view(candidate).get("project_doc_lifecycle_status") or "active"
    ).casefold()
    historical = lifecycle in {"completed", "historical", "closed", "superseded", "deprecated"}
    if requirement.lifecycle_intent == "either":
        return 0
    if requirement.lifecycle_intent == "historical":
        return 0 if historical else 1
    return 1 if historical else 0


def _assignment_preference(
    requirement: EvidenceRequirement,
    candidate: EvidenceCandidate,
    witness: RequirementWitness | None,
) -> tuple[Any, ...]:
    return (
        0 if witness is not None else 1,
        -(witness.completeness_score if witness else 0),
        0 if candidate.authority == "canonical" else 1,
        _lifecycle_assignment_rank(requirement, candidate),
        _version_rank(candidate.version_binding),
        -candidate.relevance_millis,
        len(witness.unit_text) if witness else candidate.token_estimate * 4,
        candidate.retrieval_rank,
        candidate.stable_id,
    )


def _deduplicate(
    candidates: Sequence[EvidenceCandidate],
    config: SelectionConfig,
    requirements: Sequence[EvidenceRequirement],
) -> tuple[list[EvidenceCandidate], list[Omission]]:
    selected: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    for candidate in candidates:
        duplicate: tuple[OmissionReason, EvidenceCandidate] | None = None
        for representative in selected:
            distinct_versions = bool(
                candidate.resolved_version
                and representative.resolved_version
                and candidate.resolved_version.casefold() != representative.resolved_version.casefold()
            )
            if distinct_versions:
                continue
            if _policy_polarity(candidate.display_text) != _policy_polarity(representative.display_text):
                continue
            has_new_symbols = bool(set(candidate.symbols) - set(representative.symbols))
            if candidate.stable_id == representative.stable_id or (
                candidate.parent_logical_id
                and candidate.parent_logical_id == representative.parent_logical_id
                and candidate.content_sha256 == representative.content_sha256
                and not has_new_symbols
            ):
                duplicate = "exact_duplicate", representative
                break
            if (
                _overlap_millis(candidate, representative) >= config.overlap_threshold
                and not (candidate.covered_requirement_ids - representative.covered_requirement_ids)
                and not has_new_symbols
            ):
                duplicate = "overlap_duplicate", representative
                break
            if (
                _normalized_source(candidate.source_identity) == _normalized_source(representative.source_identity)
                and _jaccard_millis(candidate.display_text, representative.display_text, config.shingle_size)
                >= config.near_duplicate_threshold
                and not (candidate.covered_requirement_ids - representative.covered_requirement_ids)
                and not has_new_symbols
            ):
                duplicate = "near_duplicate", representative
                break
        if duplicate:
            omissions.append(Omission(candidate.stable_id, duplicate[0], duplicate[1].stable_id))
        else:
            selected.append(candidate)
    return selected, omissions


def _selected_identity(candidate: EvidenceCandidate) -> dict[str, Any]:
    return {
        "stable_id": candidate.stable_id,
        "content_sha256": candidate.content_sha256,
        "source_identity": candidate.source_identity,
        "parent_logical_id": candidate.parent_logical_id,
        "projected_content_sha256": hashlib.sha256(
            candidate.projected_text.encode("utf-8")
        ).hexdigest(),
    }


def _raw_candidate_binding(item: Mapping[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    display = _display_text(item)
    score = next((
        value for value in (
            item.get("score"), item.get("relevance_score"),
            metadata.get("score"), metadata.get("relevance_score"),
        )
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ), None)
    return {
        "stable_id": str(
            item.get("stable_chunk_id") or item.get("stable_child_id")
            or metadata.get("stable_chunk_id") or item.get("stable_id") or ""
        ),
        "path_or_url": _source_path(item),
        "parent_logical_id": str(
            item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""
        ),
        "display_content_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
        "supplied_display_content_hash": str(item.get("display_content_hash") or ""),
        "retrieval_rank": _positive_int(
            item.get("retrieval_rank") if item.get("retrieval_rank") is not None else item.get("rank"),
            default=10_000,
        ),
        "relevance_millis": int(round(float(score) * 1000)) if score is not None else 0,
        "symbols": sorted(_symbols(item)),
        "exact_terms": sorted(
            str(value)
            for value in (
                item.get("exact_terms")
                if isinstance(item.get("exact_terms"), (list, tuple, set))
                else [item.get("exact_terms")] if item.get("exact_terms") else []
            )
        ),
        "project_identity": str(item.get("project_identity") or ""),
        "module_id": str(item.get("module_id") or ""),
        "doc_scope": str(item.get("doc_scope") or ""),
    }


def _canonical_contract_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_contract_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_canonical_contract_value(item) for item in value), key=canonical_hash
        )
    if isinstance(value, (list, tuple)):
        return [_canonical_contract_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _policy_polarity(value: str) -> str:
    lowered = value.casefold()
    if re.search(r"\b(?:must\s+not|do\s+not|never|forbidden|prohibited)\b", lowered):
        return "forbidden"
    if re.search(r"\b(?:must|required|shall)\b", lowered):
        return "required"
    return "neutral"


def _overlap_millis(left: EvidenceCandidate, right: EvidenceCandidate) -> int:
    if not left.parent_logical_id or left.parent_logical_id != right.parent_logical_id:
        return 0
    if None in {left.char_start, left.char_end, right.char_start, right.char_end}:
        return 0
    intersection = max(0, min(left.char_end, right.char_end) - max(left.char_start, right.char_start))
    denominator = min(left.char_end - left.char_start, right.char_end - right.char_start)
    return int(intersection * 1000 / denominator) if denominator > 0 else 0


def _shingles(value: str, size: int) -> set[tuple[str, ...]]:
    tokens = [token.casefold() for token in _TOKEN_RE.findall(" ".join(value.split()))]
    if not tokens:
        return set()
    if len(tokens) < size:
        return {tuple(tokens)}
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def _jaccard_millis(left: str, right: str, size: int) -> int:
    left_set, right_set = _shingles(left, size), _shingles(right, size)
    union = left_set | right_set
    return int(len(left_set & right_set) * 1000 / len(union)) if union else 0


def _reserve_and_select(
    candidates: Sequence[EvidenceCandidate],
    mandatory: set[str],
    config: SelectionConfig,
    *,
    prefer_proof_completeness: bool = False,
) -> tuple[list[EvidenceCandidate], set[str], list[Omission]]:
    fit_reserve = (
        DOCS_SERIALIZATION_RESERVE_TOKENS
        if config.result_kind == "docs_answer"
        else config.wrapper_reserve_tokens
    )
    available = max(1, config.hard_tokens - fit_reserve)
    selected: list[EvidenceCandidate] = []
    remaining = set(mandatory)
    pool = list(candidates)
    omissions: list[Omission] = []
    # Compatibility-only docs projection: a single already-eligible witness
    # may be rendered when the caller did not supply a typed profile. Patch
    # selection and multi-candidate ranking continue through the normal utility
    # algorithm, so this cannot become a proof/readiness bypass.
    if (
        not mandatory
        and config.profile == "generic"
        and config.result_kind == "docs_answer"
        and len(pool) == 1
        and pool[0].fit_token_estimate <= available
    ):
        return [pool[0]], set(), []
    while remaining:
        options = [candidate for candidate in pool if candidate.covered_requirement_ids & remaining]
        if not options:
            break
        def mandatory_choice_key(candidate: EvidenceCandidate) -> tuple[Any, ...]:
            key: tuple[Any, ...] = (
                -len(candidate.covered_requirement_ids & remaining),
            )
            if prefer_proof_completeness:
                # A compositional QuestionPlan may have several witnesses that
                # satisfy the same mandatory facet.  Selection must prefer the
                # strongest local proof before compactness; otherwise a short
                # command example can hide a complete procedure summary from
                # the same source.  Legacy v1-v3 selection keeps its frozen
                # ordering by leaving this flag false.
                key += (-sum(
                    witness.completeness_score
                    for witness in candidate.requirement_witnesses
                    if witness.requirement_id in remaining
                ),)
            return (*key,
                0 if candidate.authority == "canonical" else 1,
                _version_rank(candidate.version_binding),
                0 if candidate.docs_snapshot_exact is True else 1,
                candidate.token_estimate,
                candidate.retrieval_rank,
                candidate.stable_id,
            )

        best = min(options, key=mandatory_choice_key)
        selected.append(best)
        pool.remove(best)
        remaining -= best.covered_requirement_ids
    selected = _repair_mandatory_selection(
        selected,
        candidates,
        mandatory,
        prefer_proof_completeness=prefer_proof_completeness,
    )
    covered_after_repair = set().union(*(
        item.covered_requirement_ids for item in selected
    )) if selected else set()
    remaining = mandatory - covered_after_repair
    selected_ids = {item.stable_id for item in selected}
    pool = [item for item in candidates if item.stable_id not in selected_ids]
    if sum(item.fit_token_estimate for item in selected) > available:
        remaining.add("mandatory_evidence_does_not_fit")
        for candidate in candidates:
            omissions.append(Omission(candidate.stable_id, "budget"))
        return [], remaining, omissions

    spent = sum(item.fit_token_estimate for item in selected)
    selected_sources = {_normalized_source(item.source_identity) for item in selected}
    source_counts: dict[str, int] = {}
    for item in selected:
        key = _normalized_source(item.source_identity)
        source_counts[key] = source_counts.get(key, 0) + 1
    selected_terms = _selection_terms(selected)
    if config.result_kind == "docs_answer" and mandatory and not remaining:
        omissions.extend(Omission(candidate.stable_id, "dominated") for candidate in pool)
        return selected, remaining, omissions
    while pool:
        scored: list[tuple[tuple[Any, ...], EvidenceCandidate, int]] = []
        selected_coverage = set().union(*(
            item.covered_requirement_ids for item in selected
        )) if selected else set()
        selected_symbols = {symbol for item in selected for symbol in item.symbols}
        selected_cost = sum(item.token_estimate for item in selected)
        for candidate in pool:
            if (
                candidate.covered_requirement_ids
                and candidate.covered_requirement_ids <= selected_coverage
                and candidate.token_estimate >= selected_cost
                and not (set(candidate.symbols) - selected_symbols)
            ):
                omissions.append(Omission(candidate.stable_id, "dominated"))
                continue
            source_key = _normalized_source(candidate.source_identity)
            is_mandatory = bool(candidate.covered_requirement_ids & mandatory)
            if not is_mandatory and source_key not in selected_sources and len(selected_sources) >= config.max_sources:
                continue
            if not is_mandatory and source_counts.get(source_key, 0) >= config.max_items_per_source:
                continue
            utility = _marginal_utility(candidate, selected_terms, set())
            ratio = int(utility * 100 / max(1, candidate.token_estimate))
            scored.append(((-ratio, -utility, *_candidate_preference(candidate)), candidate, ratio))
        omitted_ids = {item.stable_id for item in omissions}
        pool = [item for item in pool if item.stable_id not in omitted_ids]
        if not scored:
            break
        _, best, utility_ratio = min(scored, key=lambda row: row[0])
        pool.remove(best)
        source_key = _normalized_source(best.source_identity)
        if utility_ratio < config.marginal_utility_threshold:
            omissions.append(Omission(best.stable_id, "zero_marginal_utility"))
            continue
        if spent + best.fit_token_estimate > available:
            omissions.append(Omission(best.stable_id, "budget"))
            continue
        selected.append(best)
        spent += best.fit_token_estimate
        selected_sources.add(source_key)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        selected_terms = _selection_terms(selected)
        if spent >= min(available, config.target_tokens - config.wrapper_reserve_tokens):
            break
    selected_ids = {item.stable_id for item in selected}
    omitted_ids = {item.stable_id for item in omissions}
    for candidate in candidates:
        if candidate.stable_id in selected_ids or candidate.stable_id in omitted_ids:
            continue
        source_key = _normalized_source(candidate.source_identity)
        reason: OmissionReason = (
            "source_cap"
            if source_counts.get(source_key, 0) >= config.max_items_per_source
            or (source_key not in selected_sources and len(selected_sources) >= config.max_sources)
            else "dominated"
        )
        omissions.append(Omission(candidate.stable_id, reason))
    return selected, remaining, omissions


def _repair_mandatory_selection(
    selected: Sequence[EvidenceCandidate],
    candidates: Sequence[EvidenceCandidate],
    mandatory: set[str],
    *,
    prefer_proof_completeness: bool = False,
) -> list[EvidenceCandidate]:
    """One bounded 1/2-item replacement pass for a smaller complete cover."""

    if not selected or not mandatory:
        return list(selected)
    current = list(selected)
    current_ids = {item.stable_id for item in current}
    pool = [item for item in candidates if item.stable_id not in current_ids]

    def complete(rows: Sequence[EvidenceCandidate]) -> bool:
        coverage = set().union(*(item.covered_requirement_ids for item in rows)) if rows else set()
        return mandatory <= coverage

    def quality(rows: Sequence[EvidenceCandidate]) -> tuple[Any, ...]:
        proof_quality: tuple[Any, ...] = ()
        if prefer_proof_completeness:
            proof_quality = (-sum(
                witness.completeness_score
                for item in rows
                for witness in item.requirement_witnesses
                if witness.requirement_id in mandatory
            ),)
        return (
            *proof_quality,
            sum(item.authority != "canonical" for item in rows),
            sum(_version_rank(item.version_binding) for item in rows),
            sum(item.token_estimate for item in rows),
            len(rows),
            tuple(sorted(item.stable_id for item in rows)),
        )

    best, best_quality = current, quality(current)
    removals = [combo for size in (1, 2) for combo in itertools.combinations(current, min(size, len(current)))]
    additions = [combo for size in (1, 2) for combo in itertools.combinations(pool, min(size, len(pool)))]
    for removed in removals:
        retained = [item for item in current if item not in removed]
        for added in additions:
            proposal = [*retained, *added]
            proposal_quality = quality(proposal)
            if complete(proposal) and proposal_quality < best_quality:
                best, best_quality = proposal, proposal_quality
    return best


def _selection_terms(candidates: Sequence[EvidenceCandidate]) -> set[str]:
    return {
        token.casefold()
        for candidate in candidates
        for token in _TOKEN_RE.findall(candidate.display_text)
        if len(token) > 2
    }


def _marginal_utility(candidate: EvidenceCandidate, selected_terms: set[str], mandatory: set[str]) -> int:
    terms = {token.casefold() for token in _TOKEN_RE.findall(candidate.display_text) if len(token) > 2}
    novelty = min(80, len(terms - selected_terms) * 4)
    return (
        len(candidate.covered_requirement_ids & mandatory) * 1000
        + len(candidate.covered_requirement_ids) * 180
        + (220 if candidate.authority == "canonical" else 40)
        + (120 if _version_rank(candidate.version_binding) == 0 else 20)
        + (80 if candidate.docs_snapshot_exact is True else 0)
        + (80 if candidate.projected_text.strip() else 0)
        + min(100, max(0, candidate.relevance_millis // 10))
        + (60 if candidate.symbols else 0)
        + novelty
        - (80 if candidate.navigation_only else 0)
    )


def _selected_feature_trace(
    candidates: Sequence[EvidenceCandidate], mandatory: set[str]
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    prior_terms: set[str] = set()
    prior_sources: set[str] = set()
    prior_modules: set[str] = set()
    prior_symbols: set[str] = set()
    for candidate in candidates:
        terms = {token.casefold() for token in _TOKEN_RE.findall(candidate.display_text) if len(token) > 2}
        source = _normalized_source(candidate.source_identity)
        symbols = set(candidate.symbols)
        trace.append({
            "stable_id": candidate.stable_id,
            "retrieval_relevance": candidate.relevance_millis,
            "exact_term_coverage": len(candidate.covered_requirement_ids),
            "mandatory_requirement_coverage": len(candidate.covered_requirement_ids & mandatory),
            "authority": 1000 if candidate.authority == "canonical" else 250,
            "version_exactness": 1000 if _version_rank(candidate.version_binding) == 0 else 0,
            "usable_snippet": 1000 if candidate.projected_text.strip() else 0,
            "new_source_fact_terms": len(terms - prior_terms),
            "new_module_coverage": int(bool(candidate.module_id and candidate.module_id not in prior_modules)),
            "new_target_symbols": len(symbols - prior_symbols),
            "new_source": int(bool(source and source not in prior_sources)),
            "novelty_millis": int(len(terms - prior_terms) * 1000 / max(1, len(terms))),
            "token_cost": candidate.token_estimate,
            "expansion_cost": 0,
            "stale_risk": int(candidate.freshness.casefold() == "stale"),
            "generic_source_penalty": int(candidate.authority != "canonical"),
            "ambiguity_penalty": int(candidate.navigation_only),
        })
        prior_terms.update(terms)
        prior_sources.add(source)
        if candidate.module_id:
            prior_modules.add(candidate.module_id)
        prior_symbols.update(symbols)
    return trace


def _redundant_token_ratio_millis(
    candidates: Sequence[EvidenceCandidate], config: SelectionConfig
) -> int:
    redundant = 0
    accepted: list[EvidenceCandidate] = []
    for candidate in candidates:
        if any(
            _jaccard_millis(candidate.display_text, previous.display_text, config.shingle_size)
            >= config.near_duplicate_threshold
            for previous in accepted
        ):
            redundant += candidate.token_estimate
        accepted.append(candidate)
    total = sum(item.token_estimate for item in candidates)
    return int(redundant * 1000 / total) if total else 0


def _authority_conflicts(candidates: Sequence[EvidenceCandidate]) -> set[str]:
    required: dict[str, set[str]] = {}
    forbidden: dict[str, set[str]] = {}
    for candidate in candidates:
        if candidate.authority != "canonical":
            continue
        for line in candidate.display_text.splitlines():
            normalized = " ".join(re.findall(r"[\w]+", line.casefold()))
            if "must not" in line.casefold() or "never" in line.casefold() or "forbidden" in line.casefold():
                key = re.sub(r"\b(?:must|not|never|forbidden|be)\b", " ", normalized)
                forbidden.setdefault(" ".join(key.split()), set()).add(candidate.stable_id)
            elif "must" in line.casefold() or "required" in line.casefold():
                key = re.sub(r"\b(?:must|required|be)\b", " ", normalized)
                required.setdefault(" ".join(key.split()), set()).add(candidate.stable_id)
    return {
        key for key in required.keys() & forbidden.keys() if key
    }


def _count_reasons(omissions: Sequence[Omission]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for omission in omissions:
        counts[omission.reason_code] = counts.get(omission.reason_code, 0) + 1
    return dict(sorted(counts.items()))


__all__ = [
    "MAX_SELECTOR_CANDIDATES", "SELECTOR_SCHEMA_VERSION", "EvidenceCandidate",
    "EvidenceRequirement", "EvidenceRequirementSet", "Omission", "SelectionConfig", "SelectionDecision",
    "build_requirements", "docs_selection_config", "library_docs_selection_config", "project_docs_selection_config", "normalize_candidates",
    "patch_selection_config", "select_evidence", "validate_evidence_sufficiency",
]
