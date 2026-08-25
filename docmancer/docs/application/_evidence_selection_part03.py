"""Implementation shard 3 for evidence_selection."""
from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

from ._evidence_selection_part01 import SelectionDecision, _assignment_preference, _candidate_preference, _candidate_requirement_witness, _candidate_source_view, _count_reasons, _eligible_candidates, _redundant_token_ratio_millis, _selected_identity
from ._evidence_selection_part02 import _authority_conflicts, _code_group_requirement_matches, _deduplicate, _facet_requirement_matches, _raw_candidate_binding, _reserve_and_select, _scope_requirement_value, _selected_feature_trace, _with_canonical_policy_requirements, _witness_for_requirement


def _hydrate_cohesive_contract_paragraphs(
    items: list[dict[str, Any]],
    requirements: EvidenceRequirementSet,
) -> None:
    """Expose one indexed paragraph when a typed contract facet spans its sentences."""

    if not any(item.relation == "applicable_contract" for item in requirements):
        return
    for item in items:
        display = str(item.get("display_text") or "").strip()
        content = str(item.get("content") or "").strip()
        if (
            not display
            or display == content
            or display not in content
            or len(content) > 4_000
            or "\n\n" in content
        ):
            continue
        item["display_text"] = content
        item["display_content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()

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
    if config.result_kind == "docs_answer" and isinstance(requirements, EvidenceRequirementSet):
        _hydrate_cohesive_contract_paragraphs(materialized_items, requirements)
    v3_answer_units = any(
        item.obligation_kind in {"purpose", "effect"}
        or item.relation == "applicable_contract"
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
        elif requirement.kind in {
            "target_declaration", "preserve_declaration",
            "behavioral_contract", "cross_module_invariant",
        }:
            witness = _witness_for_requirement(requirement, candidate)
            matches = witness is not None
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

__all__=['select_evidence', 'validate_evidence_sufficiency', '_with_coverage', '_canonical_contract_value']
