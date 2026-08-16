"""Immutable data contracts for evidence selection.

Keeping selector data models separate from ranking/orchestration makes the
critical selection module reviewable without changing selection semantics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal, Mapping, Sequence, overload

from docmancer.docs.domain.answer_units import AnswerUnit
from docmancer.docs.domain.project_answer_contract import LifecycleIntent, ProofObligation
from docmancer.retrieval.contracts import canonical_hash

SELECTOR_SCHEMA_VERSION = "budget-aware-evidence-selector-v6"
MAX_SELECTOR_CANDIDATES = 20
MAX_VISIBLE_DOCUMENTS = 3
MAX_VISIBLE_SPANS = 6

OmissionReason = Literal[
    "wrong_version", "unknown_version", "forbidden_source", "outside_scope",
    "stale", "instruction_risk", "invalid_identity", "navigation_only",
    "query_identifier_conflict", "query_intent_mismatch",
    "authority_conflict", "exact_duplicate", "overlap_duplicate",
    "near_duplicate", "source_cap", "zero_marginal_utility", "budget",
    "dominated", "candidate_cap",
]
ProofRole = Literal[
    "generic_fact", "document_identity", "target_identity", "document_statement",
    "project_rule", "implementation_fact", "dependency_fact",
]
EvidenceQualifier = Literal[
    "proposed", "not_implemented", "confirmation_required", "negated",
    "conditional", "deprecated",
]
_PROOF_ROLES = frozenset({
    "generic_fact", "document_identity", "target_identity", "document_statement",
    "project_rule", "implementation_fact", "dependency_fact",
})
_EVIDENCE_QUALIFIERS = frozenset({
    "proposed", "not_implemented", "confirmation_required", "negated",
    "conditional", "deprecated",
})

@dataclass(frozen=True, slots=True)
class SelectionConfig:
    result_kind: Literal["docs_answer", "patch_context"]
    target_tokens: int
    hard_tokens: int
    profile: Literal["generic", "library_docs_answer", "project_document_answer", "project_docs_answer"] = "generic"
    schema_version: str = SELECTOR_SCHEMA_VERSION
    max_candidates: int = MAX_SELECTOR_CANDIDATES
    max_sources: int = 3
    max_items_per_source: int = 2
    max_documents: int = MAX_VISIBLE_DOCUMENTS
    max_spans: int = MAX_VISIBLE_SPANS
    near_duplicate_threshold: int = 850
    overlap_threshold: int = 800
    marginal_utility_threshold: int = 80
    shingle_size: int = 5
    wrapper_reserve_tokens: int = 120
    cache_enabled: bool = False

    def __post_init__(self) -> None:
        if self.result_kind not in {"docs_answer", "patch_context"}:
            raise ValueError("unsupported evidence result kind")
        if self.profile not in {"generic", "library_docs_answer", "project_document_answer", "project_docs_answer"}:
            raise ValueError("unsupported evidence selection profile")
        if not 1 <= self.target_tokens <= self.hard_tokens:
            raise ValueError("selector token budgets are invalid")
        if not 1 <= self.max_candidates <= MAX_SELECTOR_CANDIDATES:
            raise ValueError("selector candidate limit is invalid")
        if self.max_sources < 1 or self.max_items_per_source < 1:
            raise ValueError("selector source limits are invalid")
        if self.max_documents < 1 or self.max_spans < 1:
            raise ValueError("selector document/span limits are invalid")
        if not 0 <= self.near_duplicate_threshold <= 1000:
            raise ValueError("near duplicate threshold is invalid")

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    requirement_id: str
    kind: str
    value: str
    mandatory: bool = True
    public_provenance: str = "public_task_contract"
    source_path: str | None = None
    target_path: str | None = None
    version_binding: str | None = None
    # Hash-bound provenance from the pure query analyser; it does not alter
    # selection semantics.
    query_extraction_kind: str | None = None
    query_span_start: int | None = None
    query_span_end: int | None = None
    query_span_text: str | None = None
    proof_role: ProofRole = "generic_fact"
    qualifiers: tuple[EvidenceQualifier, ...] = ()
    obligation_kind: str | None = None
    subject: str | None = None
    attribute: str | None = None
    relation: str | None = None
    obligation_target: str | None = None
    value_kind: str | None = None
    expected_value: str | None = None
    item_kind: str | None = None
    cardinality: int | None = None
    response_mode: str = "value"
    subject_kind: str | None = None
    subject_aliases: tuple[str, ...] = ()
    context: str | None = None
    lifecycle_intent: LifecycleIntent = "current"

    def __post_init__(self) -> None:
        if self.proof_role not in _PROOF_ROLES:
            raise ValueError(f"unsupported evidence proof role: {self.proof_role}")
        qualifiers = tuple(sorted(set(self.qualifiers)))
        unknown = set(qualifiers) - _EVIDENCE_QUALIFIERS
        if unknown:
            raise ValueError(f"unsupported evidence qualifiers: {', '.join(sorted(unknown))}")
        if self.kind == "proof_obligation":
            if not self.obligation_kind or not self.subject or not self.value_kind:
                raise ValueError("typed proof obligation is incomplete")
            if self.cardinality is not None and not 1 <= self.cardinality <= 32:
                raise ValueError("typed proof obligation cardinality is invalid")
            if self.response_mode not in {
                "value", "count", "names", "count_and_names", "call", "path", "workflow", "purpose",
            }:
                raise ValueError("typed proof obligation response mode is invalid")
            if self.subject_kind is not None and self.subject_kind not in {
                "cli_command", "cli_flag", "env_var", "config_key", "code_symbol", "plain_term",
            }:
                raise ValueError("typed proof obligation subject kind is invalid")
            if len(self.subject_aliases) > 8:
                raise ValueError("typed proof obligation aliases exceed bounds")
        object.__setattr__(self, "subject_aliases", tuple(dict.fromkeys(
            str(value).strip()[:160]
            for value in self.subject_aliases
            if str(value).strip()
        )))
        object.__setattr__(self, "qualifiers", qualifiers)

    def as_proof_obligation(self) -> ProofObligation | None:
        if self.kind != "proof_obligation":
            return None
        return ProofObligation(
            obligation_id=self.requirement_id,
            kind=self.obligation_kind,  # type: ignore[arg-type]
            subject=str(self.subject),
            attribute=self.attribute,
            relation=self.relation,
            target=self.obligation_target,
            value_kind=self.value_kind,  # type: ignore[arg-type]
            expected_value=self.expected_value,
            item_kind=self.item_kind,
            cardinality=self.cardinality,
            response_mode=self.response_mode,
            subject_kind=self.subject_kind,  # type: ignore[arg-type]
            subject_aliases=self.subject_aliases,
            context=self.context,
            mandatory=self.mandatory,
            query_span_start=self.query_span_start,
            query_span_end=self.query_span_end,
            query_span_text=self.query_span_text,
            lifecycle_intent=self.lifecycle_intent,
        )


@dataclass(frozen=True, slots=True)
class EvidenceRequirementSet(Sequence[EvidenceRequirement]):
    """Canonical immutable requirements owned by evidence selection.

    Entity and facet fields reserve the canonical contract surface for later
    analysis. They intentionally have no selection semantics in this phase.
    """

    requirements: tuple[EvidenceRequirement, ...] = ()
    required_entities: tuple[str, ...] = ()
    required_facets: tuple[str, ...] = ()
    query_extraction_provenance: tuple[tuple[str, str, str], ...] = ()
    query_requirement_spans: tuple[tuple[str, int, int, str], ...] = ()
    retrieval_hints: tuple[str, ...] = ()
    concept_queries: tuple[str, ...] = ()
    answer_contract_hash: str | None = None
    lifecycle_intent: LifecycleIntent = "current"
    parse_trace: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        requirements_by_id: dict[str, EvidenceRequirement] = {}
        for item in self.requirements:
            existing = requirements_by_id.get(item.requirement_id)
            if existing is not None and existing != item:
                raise ValueError(f"conflicting evidence requirement ID: {item.requirement_id}")
            requirements_by_id[item.requirement_id] = item
        canonical_requirements = tuple(sorted(
            requirements_by_id.values(), key=lambda item: item.requirement_id,
        ))
        entities = tuple(sorted({str(value).strip() for value in self.required_entities if str(value).strip()}))
        facets = tuple(sorted({str(value).strip() for value in self.required_facets if str(value).strip()}))
        provenance = tuple(sorted({
            (item.requirement_id, item.query_extraction_kind, item.value.casefold())
            for item in canonical_requirements
            if item.public_provenance == "query_exact_term" and item.query_extraction_kind
        }))
        if self.query_extraction_provenance:
            provenance = tuple(sorted({
                (str(requirement_id), str(kind), str(value).casefold())
                for requirement_id, kind, value in self.query_extraction_provenance
            }))
        spans = tuple(sorted({
            (item.requirement_id, item.query_span_start, item.query_span_end, item.query_span_text)
            for item in canonical_requirements
            if item.query_span_start is not None
            and item.query_span_end is not None
            and item.query_span_text is not None
        }))
        if self.query_requirement_spans:
            spans = tuple(sorted({
                (str(requirement_id), int(start), int(end), str(text))
                for requirement_id, start, end, text in self.query_requirement_spans
                if int(start) >= 0 and int(end) > int(start) and str(text)
            }))
        object.__setattr__(self, "requirements", canonical_requirements)
        object.__setattr__(self, "required_entities", entities)
        object.__setattr__(self, "required_facets", facets)
        object.__setattr__(self, "query_extraction_provenance", provenance)
        object.__setattr__(self, "query_requirement_spans", spans)
        object.__setattr__(self, "retrieval_hints", tuple(dict.fromkeys(
            str(value).strip()[:160]
            for value in self.retrieval_hints
            if str(value).strip()
        ))[:24])
        object.__setattr__(self, "concept_queries", tuple(dict.fromkeys(
            str(value).strip()[:320]
            for value in self.concept_queries
            if str(value).strip()
        ))[:4])
        object.__setattr__(self, "parse_trace", tuple(dict.fromkeys(
            str(value).strip()[:160] for value in self.parse_trace if str(value).strip()
        ))[:24])
        object.__setattr__(self, "unresolved_parts", tuple(dict.fromkeys(
            str(value).strip()[:160] for value in self.unresolved_parts if str(value).strip()
        ))[:12])

    def __len__(self) -> int:
        return len(self.requirements)

    @overload
    def __getitem__(self, index: int) -> EvidenceRequirement: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[EvidenceRequirement, ...]: ...

    def __getitem__(self, index: int | slice) -> EvidenceRequirement | tuple[EvidenceRequirement, ...]:
        return self.requirements[index]

    @property
    def hash_payload(self) -> dict[str, Any]:
        def requirement_payload(item: EvidenceRequirement) -> dict[str, Any]:
            payload = asdict(item)
            if payload.get("response_mode") == "value":
                payload.pop("response_mode", None)
            if payload.get("subject_kind") is None:
                payload.pop("subject_kind", None)
            if not payload.get("subject_aliases"):
                payload.pop("subject_aliases", None)
            if payload.get("context") is None:
                payload.pop("context", None)
            return payload

        payload = {
            "requirements": [requirement_payload(item) for item in self.requirements],
            "required_entities": list(self.required_entities),
            "required_facets": list(self.required_facets),
            "query_extraction_provenance": [list(item) for item in self.query_extraction_provenance],
            "query_requirement_spans": [list(item) for item in self.query_requirement_spans],
            "retrieval_hints": list(self.retrieval_hints),
            "concept_queries": list(self.concept_queries),
            "answer_contract_hash": self.answer_contract_hash,
            "lifecycle_intent": self.lifecycle_intent,
        }
        if self.parse_trace:
            payload["parse_trace"] = list(self.parse_trace)
        if self.unresolved_parts:
            payload["unresolved_parts"] = list(self.unresolved_parts)
        return payload

    @property
    def requirements_hash(self) -> str:
        return canonical_hash(self.hash_payload)


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    stable_id: str
    evidence_id: str
    hydration_id: int | None
    identity_kind: str
    source_identity: str
    identity_aliases: tuple[str, ...]
    path_or_url: str
    section: str
    parent_logical_id: str
    content_sha256: str
    display_text: str
    projected_text: str
    token_estimate: int
    fit_token_estimate: int
    reported_token_estimate: int | None
    char_start: int | None
    char_end: int | None
    line_start: int | None
    line_end: int | None
    retrieval_rank: int
    component_ranks: tuple[tuple[str, int], ...]
    relevance_millis: int
    authority: str
    source_class: str
    version_binding: str
    resolved_version: str
    docs_snapshot_exact: bool | None
    project_identity: str
    module_id: str
    doc_scope: str
    symbols: tuple[str, ...]
    exact_terms: tuple[str, ...]
    instruction_risk_flags: tuple[str, ...]
    freshness: str
    navigation_only: bool
    answer_units: tuple[AnswerUnit, ...] = ()
    requirement_witnesses: tuple["RequirementWitness", ...] = ()
    covered_requirement_ids: frozenset[str] = frozenset()
    original: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Omission:
    stable_id: str
    reason_code: OmissionReason
    representative_stable_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceAssignment:
    requirement_id: str
    evidence_id: str
    path: str
    char_start: int | None
    char_end: int | None
    line_start: int | None
    line_end: int | None
    projected_content_hash: str
    proof_role: ProofRole
    qualifiers: tuple[EvidenceQualifier, ...]
    unit_id: str | None = None
    unit_kind: str | None = None
    unit_char_start: int | None = None
    unit_char_end: int | None = None
    unit_content_hash: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementWitness:
    requirement_id: str
    unit_id: str
    unit_kind: str
    unit_text: str = field(compare=False, repr=False)
    unit_char_start: int | None
    unit_char_end: int | None
    unit_content_hash: str
    subject_score: int
    relation_score: int
    value_score: int
    completeness_score: int


@dataclass(frozen=True, slots=True)
class SupportDecision:
    """Immutable public support verdict produced only by ``select_evidence``."""

    answer_supported: bool
    support_status: Literal["supported", "insufficient_evidence"]
    reason_code: str | None
    missing_requirement_ids: tuple[str, ...]
    satisfied_requirement_ids: tuple[str, ...]
    mandatory_requirement_ids: tuple[str, ...]
    mandatory_coverage: float
    selected_evidence_ids: tuple[str, ...]
    requirements_hash: str
    selector_config_hash: str
    eligibility_contract_hash: str
    candidate_trace_hash: str
    selection_hash: str
    assignment_hash: str
    decision_hash: str
    requirements: EvidenceRequirementSet = field(compare=False, repr=False)

    @property
    def answer_available(self) -> bool:
        return self.answer_supported

    def as_payload(self) -> dict[str, Any]:
        return {
            "answer_supported": self.answer_supported,
            "answer_available": self.answer_supported,
            "support_status": self.support_status,
            "decision": self.support_status,
            "reason_code": self.reason_code,
            "missing_requirement_ids": list(self.missing_requirement_ids),
            "satisfied_requirement_ids": list(self.satisfied_requirement_ids),
            "mandatory_requirement_ids": list(self.mandatory_requirement_ids),
            "mandatory_coverage": self.mandatory_coverage,
            "evidence_coverage": self.mandatory_coverage,
            "selected_evidence_ids": list(self.selected_evidence_ids),
            "requirements_hash": self.requirements_hash,
            "selector_config_hash": self.selector_config_hash,
            "eligibility_contract_hash": self.eligibility_contract_hash,
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
            "assignment_hash": self.assignment_hash,
            "decision_hash": self.decision_hash,
        }

    def with_insufficient_reason_code(self, reason_code: str) -> "SupportDecision":
        """Return an insufficient verdict with one audited runtime reason."""

        if self.answer_supported or self.support_status != "insufficient_evidence":
            raise ValueError("only an insufficient support decision can carry an insufficiency reason")
        if not reason_code:
            raise ValueError("an insufficiency reason code is required")

        payload = {
            "answer_supported": self.answer_supported,
            "support_status": self.support_status,
            "reason_code": reason_code,
            "missing_requirement_ids": self.missing_requirement_ids,
            "satisfied_requirement_ids": self.satisfied_requirement_ids,
            "mandatory_requirement_ids": self.mandatory_requirement_ids,
            "mandatory_coverage": self.mandatory_coverage,
            "selected_evidence_ids": self.selected_evidence_ids,
            "requirements_hash": self.requirements_hash,
            "selector_config_hash": self.selector_config_hash,
            "eligibility_contract_hash": self.eligibility_contract_hash,
            "candidate_trace_hash": self.candidate_trace_hash,
            "selection_hash": self.selection_hash,
            "assignment_hash": self.assignment_hash,
        }
        return replace(
            self,
            reason_code=str(reason_code),
            decision_hash=canonical_hash(payload),
        )



__all__ = [
    "SELECTOR_SCHEMA_VERSION", "MAX_SELECTOR_CANDIDATES", "MAX_VISIBLE_DOCUMENTS", "MAX_VISIBLE_SPANS",
    "OmissionReason", "ProofRole", "EvidenceQualifier", "SelectionConfig",
    "EvidenceRequirement", "EvidenceRequirementSet", "EvidenceCandidate", "Omission",
    "EvidenceAssignment", "RequirementWitness", "SupportDecision",
]
