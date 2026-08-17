"""Implementation shard 1 for evidence_selection."""
from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

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


def _count_reasons(omissions: Sequence[Omission]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for omission in omissions:
        counts[omission.reason_code] = counts.get(omission.reason_code, 0) + 1
    return dict(sorted(counts.items()))

__all__=['SelectionDecision', 'resolve_assignment_unit', 'validate_assignment_binding', 'MixedSelectionLane', 'AggregateMixedSelectionDecision', 'aggregate_mixed_selection', 'docs_selection_config', 'library_docs_selection_config', 'project_docs_selection_config', 'patch_selection_config', '_eligible_candidates', '_query_identifier_conflict', '_query_identifier_values', '_trust_source_keys', '_candidate_source_view', '_candidate_preference', '_candidate_requirement_witness', '_lifecycle_assignment_rank', '_assignment_preference', '_selected_identity', '_shingles', '_jaccard_millis', '_repair_mandatory_selection', '_selection_terms', '_marginal_utility', '_redundant_token_ratio_millis', '_count_reasons']
