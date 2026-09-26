"""Bounded retrieval-only projection for free-form project documentation queries."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any
from ._docs_context_payload import _payload
from .projection_decision_trace import ProjectionDecisionTrace
from .source_continuation import attach_source_continuation_locators
from .visible_evidence_retention import retains_visible_sources, restore_visible_sources
from .qualified_support_units import DeliveryUnit, VariantFootprint
from .context_variant_retention import (
    is_same_origin_gain, prepare_delivery_inventory, qualified_fragments as _qualified_fragments,
    prefer_same_origin_gain_candidate, replacement_preserves_or_advances_mandatory,
    store_variant_footprint,
)
from .context_query_probes import independent_query_probes, _has_visible_non_path_exact_term, _normalized_path
from docmancer.docs.domain.context_hint_policy import fallback_context_query_ids, has_context_hint_support

from docmancer.docs.application.context_selection import (
    attributable_query_ids, component_coverage_decision,
    component_obligations,
    component_witnesses,
    context_selection_decision,
    merge_query_matches,
    qualified_query_ids,
    bind_visible_assignments,
    visible_assignments,
)
from docmancer.docs.application.model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS,
    INSUFFICIENT_EVIDENCE_MAX_TOKENS,
    MAX_DOCS_SOURCES,
    _docs_source,
    _refresh_estimate,
    _snapshot_entry,
    docs_context_budget_tokens,
    project_insufficient,
)
from .context_candidate_ranking import _context_rank, _facet_aware_candidates, _fully_matched_query_ids, _prefer_missing_baseline_candidate
from .retrieval_need_support import apply_retrieval_need_witness
from docmancer.docs.domain.context_budget import PROJECT_CONTEXT_BUDGET
from docmancer.docs.domain.context_blocks import inline_command_literals, source_block_alternatives
from docmancer.docs.domain.context_windows import (
    _focused_line_range, _focused_snippet, _is_complete_source_span,
    _projection_limits, _query_terms,
)
from docmancer.docs.domain.evidence_qualification import (
    derived_parent_trace,
    evidence_policy_rejection_reason,
    qualify_evidence,
)
from docmancer.docs.domain.query_terms import documentation_exact_terms
from docmancer.docs.domain.lifecycle_policy import lifecycle_intent
from docmancer.docs.domain.normative_language import _FORBIDDEN_RE, _REQUIRED_RE


def _diagnostics_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    """Copy one diagnostic attempt before linking it into another attempt."""
    return copy.deepcopy(value)


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
    selection_diagnostics: dict[str, Any] | None = None,
    _allow_context_hints: bool = False,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Project trusted retrieval as context without claiming answer support."""

    max_tokens = PROJECT_CONTEXT_BUDGET.bounded_tokens(max_tokens)
    projection_diagnostics = {
        "qualified_variants": 0, "budget_rejections": 0,
        "ranked_candidate_ids": [], "considered_variants": [],
        "projection_rejections": [], "final_visible_evidence_ids": [],
    }
    if not isinstance(retrieval.get("retrieval_diagnostics"), dict):
        retrieval["retrieval_diagnostics"] = {}
    retrieval.setdefault("retrieval_diagnostics", {})["docs_context_projection"] = projection_diagnostics
    decision_trace = ProjectionDecisionTrace(projection_diagnostics)
    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    projection_inputs: dict[str, tuple[str, tuple[str, ...], Any]] = {}
    seen_ids: dict[str, int] = {}
    query_plan = dict(retrieval.get("documentation_query_plan") or {})
    obligations = component_obligations(query_plan.get("_component_contract") or ())
    mandatory_component_ids = {item.obligation_id for item in obligations}
    strict_single_attribute = bool(
        query_plan.get("component_scope_complete", True)
        and len(obligations) == 1
        and obligations[0].kind == "attribute"
        and obligations[0].value_kind
    )
    selection = retrieval.get("selection_decision") or {}
    assignments = (
        selection.get("assignments") or () if isinstance(selection, dict) else ()
    )
    assigned_evidence_by_requirement = {
        str(item.get("requirement_id") or ""): str(item.get("evidence_id") or "")
        for item in assignments
        if isinstance(item, dict)
        and item.get("requirement_id")
        and item.get("evidence_id")
    }
    query_plan["assigned_requirement_ids"] = [
        str(item.get("requirement_id") or "")
        for item in assignments if isinstance(item, dict) and item.get("requirement_id")
    ]
    query_plan["missing_requirement_ids"] = list(
        retrieval.get("missing_requirement_ids") or ()
    )
    context_only_relations = {
        str(value).split(":", 1)[1]
        for value in query_plan.get("missing_requirement_ids") or ()
        if str(value).startswith("context_only:")
    }
    intent_context_only = any(
        isinstance(item, dict)
        and item.get("origin") == "canonical_intent"
        and str(item.get("facet_id") or "").startswith("intent-context:")
        for item in query_plan.get("queries") or ()
    )
    broad_context_only = bool(context_only_relations & {
        "architecture", "behavior", "chunking", "contract_fact", "contrast",
        "implementation", "location", "purpose", "procedure",
        "selection_policy", "usage", "workflow",
    }) or bool(query_plan.get("unresolved_parts")) or intent_context_only
    query_plan["broad_context_only"] = broad_context_only
    query_text = {
        str(item.get("query_id") or ""): str(item.get("text") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
    }
    required_query_ids = _required_query_ids(query_plan)
    required_query_id_set = set(required_query_ids)
    required_requirement_ids = {
        str(item.get("requirement_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and str(item.get("query_id") or "") in required_query_id_set
        and item.get("requirement_id")
    }
    required_assigned_evidence_ids = {
        assigned_evidence_by_requirement[requirement_id]
        for requirement_id in required_requirement_ids
        if requirement_id in assigned_evidence_by_requirement
    }
    public_query_ids = _public_query_ids(query_plan)
    public_query_id_set = set(public_query_ids)
    host_query_ids = _query_ids_for_origins(query_plan, {"host_lookup"}); need_query_ids = _query_ids_for_origins(query_plan, {"retrieval_need"})
    exact_anchor_query_ids = _query_ids_for_origins(
        query_plan, {"exact_anchor", "exact_path"},
    )
    canonical_intent_query_ids = _query_ids_for_origins(
        query_plan, {"canonical_intent"},
    )
    audited_rewrite_query_ids = {
        str(item.get("query_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and item.get("relation") == "audited_rewrite"
        and str(item.get("public_parent_query_id") or "") in host_query_ids
        and item.get("query_id")
    }
    compound_priority_query_ids = public_query_id_set
    if len(host_query_ids) > 1:
        compound_priority_query_ids = host_query_ids | audited_rewrite_query_ids
    eligible_query_ids = public_query_id_set | canonical_intent_query_ids | need_query_ids
    fallback_ids = fallback_context_query_ids(query_plan, retrieval, eligible_query_ids)
    context_hint_query_ids = fallback_ids if _allow_context_hints else set()
    eligible_query_ids |= context_hint_query_ids
    original_question = str(query_plan.get("original_question") or retrieval.get("question") or query_text.get("query-original") or "")
    requirements = retrieval.get("requirements") or {}
    requirement_items = requirements.get("requirements", ()) if isinstance(requirements, dict) else ()
    expected_project_identity = retrieval.get("project_identity") or next((
        item.get("value") for item in requirement_items
        if isinstance(item, dict) and item.get("kind") == "project_identity"
    ), None)
    selected_project_identities = {
        item["project_identity"] for item in selection.get("selected_candidates", ())
        if isinstance(item, dict) and item.get("project_identity")
    } if isinstance(selection, dict) else set()
    if not expected_project_identity and len(selected_project_identities) == 1:
        expected_project_identity = next(iter(selected_project_identities))
    request_lifecycle_intent = (
        requirements.get("lifecycle_intent") if isinstance(requirements, dict) else None
    ) or lifecycle_intent(original_question)
    explicit_paths = {
        _normalized_path(value) for value in query_plan.get("explicit_paths") or ()
        if str(value).strip()
    }
    candidates = list(retrieval.get("context_pack") or ())
    initially_ranked = _facet_aware_candidates(
        candidates, query_text=query_text,
        fallback_query_ids=context_hint_query_ids, need_query_ids=need_query_ids,
        host_query_ids=host_query_ids,
        required_query_ids=compound_priority_query_ids - audited_rewrite_query_ids,
        supplemental_query_ids=audited_rewrite_query_ids | need_query_ids,
        canonical_query_ids=canonical_intent_query_ids,
        assigned_evidence_ids=set(assigned_evidence_by_requirement.values()),
        bound_assigned_evidence_ids=required_assigned_evidence_ids,
    )
    projection_diagnostics["ranked_candidate_ids"] = [
        _internal_candidate_id(item) for item in initially_ranked[:32]
        if _internal_candidate_id(item)
    ]
    prepared: list[dict[str, Any]] = []
    variant_inputs: dict[int, tuple[Any, ...]] = {}
    variant_footprints: dict[int, VariantFootprint] = {}
    selected_footprints: dict[str, VariantFootprint] = {}
    for original in initially_ranked:
        if not isinstance(original, dict):
            decision_trace.record('candidate', 'rejected', 'invalid_candidate', original)
            continue
        original = dict(original)
        if str(original.get("source_class") or "") != "project_doc":
            decision_trace.record('candidate', 'rejected', 'wrong_source_class', original)
            continue
        if explicit_paths and _normalized_path(original.get("path") or "") not in explicit_paths:
            decision_trace.record('candidate', 'rejected', 'explicit_path_filter', original)
            continue
        project_identity = str(original.get("project_identity") or "").strip()
        if explicit_paths and _normalized_path(
            original.get("path") or original.get("source") or ""
        ) in explicit_paths:
            matches = merge_query_matches(original.get("retrieval_query_matches"))
            for query_id in exact_anchor_query_ids:
                if query_id.startswith("query-path-"):
                    matches[query_id] = {
                        "mode": "exact_path",
                        "query_text": query_text.get(query_id, ""),
                    }
            original["retrieval_query_matches"] = matches
        original["_qualification_candidate"] = dict(original)
        original["_expected_project_identity"] = expected_project_identity
        original["_lifecycle_intent"] = request_lifecycle_intent
        qualified_original = _requalify_visible_source({
            **original,
            "path_or_url": original.get("path") or "",
            "snippet": original.get("content") or original.get("display_text") or original.get("snippet") or "",
        }, query_text=query_text)
        original["retrieval_query_matches"] = qualified_original["retrieval_query_matches"]
        original["retrieval_query_ids"] = qualified_original["retrieval_query_ids"]
        qualified_ids = qualified_query_ids((original,))
        component_ids = set(component_witnesses(qualified_original, obligations))
        visible_query_ids = qualified_ids & eligible_query_ids
        if strict_single_attribute and not component_ids:
            decision_trace.record('candidate', 'rejected', 'missing_attribute', original)
            continue
        if not visible_query_ids and not component_ids:
            decision_trace.record('candidate', 'rejected', 'no_visible_qualification', original)
            continue
        required_ids = qualified_ids & required_query_id_set
        original_hit = "query-original" in qualified_ids
        host_ids = qualified_ids & host_query_ids
        need_ids = qualified_ids & need_query_ids
        exact_anchor_ids = qualified_ids & exact_anchor_query_ids
        canonical_intent_ids = qualified_ids & canonical_intent_query_ids
        path_only_ids = {
            query_id for query_id in exact_anchor_ids if query_id.startswith("query-path-")
        }
        if (
            path_only_ids
            and qualified_ids <= path_only_ids and not component_ids
            and not _has_visible_non_path_exact_term(
                raw_text=str(original.get("content") or original.get("display_text") or ""),
                original_question=original_question, explicit_paths=explicit_paths,
            )
        ):
            decision_trace.record('candidate', 'rejected', 'path_only', original)
            continue
        if not component_ids and not required_ids and not exact_anchor_ids and not original_hit and not host_ids and not need_ids and not canonical_intent_ids and not (qualified_ids & context_hint_query_ids and has_context_hint_support(qualified_original, question=original_question)):
            decision_trace.record('candidate', 'rejected', 'no_admissible_direction', original)
            continue
        if (
            "contract_fact" in context_only_relations
            and not component_ids
            and not required_ids
            and not host_ids
            and not exact_anchor_ids
        ):
            decision_trace.record('candidate', 'rejected', 'contract_fact_filter', original)
            continue
        raw_snippet = next((
            value
            for value in (
                original.get("code"), original.get("snippet"), original.get("content"),
                original.get("display_text"),
            )
            if isinstance(value, str) and value.strip()
        ), "")
        required_matches = tuple(
            query_text.get(query_id, "")
            for query_id in qualified_ids if query_id in required_query_id_set
        )
        supplemental_matches = tuple(
            str(((original.get("retrieval_query_matches") or {}).get(query_id) or {}).get("query_text") or "")
            for query_id in qualified_ids if query_id.startswith("query-supplemental-") or query_id in need_query_ids
        )
        focus_queries = (
            tuple(value for value in (*required_matches, *supplemental_matches) if value)
            or tuple(query_text.get(query_id, "") for query_id in qualified_ids)
        )
        # Establish source identity before qualified variants cross projection.
        normalized = _docs_source(original, display_snippet=raw_snippet[:520])
        if normalized is None:
            decision_trace.record('candidate', 'rejected', 'invalid_source', original)
            continue
        assigned_requirement_ids = _assigned_requirements_for_source(
            original, assigned_evidence_by_requirement,
        )
        normalized.update({
            "project_identity": project_identity,
            "authority": str(original.get("authority") or "supporting"),
            "scope": str(original.get("doc_scope") or "project"),
            "catalog_role": str(original.get("catalog_role") or ""),
            "retrieval_query_ids": list(original.get("retrieval_query_ids") or ()),
            "retrieval_query_matches": dict(original.get("retrieval_query_matches") or {}),
            "_assigned_requirement_ids": list(assigned_requirement_ids),
            "_qualification_candidate": original["_qualification_candidate"],
            "_independent_query_plan": query_plan,
            "_expected_project_identity": original["_expected_project_identity"],
            "_lifecycle_intent": original["_lifecycle_intent"],
        })
        delivery_units, delivery_raw_start = prepare_delivery_inventory(
            source=original, raw_text=raw_snippet, query_plan=query_plan,
            query_text=query_text,
            eligible_query_ids=frozenset(qualified_ids & eligible_query_ids),
            requalify=_requalify_visible_source,
        )
        variants = _qualified_fragments(
            normalized,
            raw_snippet=raw_snippet,
            query_ids=qualified_ids & eligible_query_ids,
            query_text=query_text,
            source_line_start=original.get("line_start"), requalify=_requalify_visible_source,
            obligations=obligations, assignments=assignments,
            delivery_units=delivery_units, delivery_raw_start=delivery_raw_start,
            footprint_sink=variant_footprints,
        )
        decision_trace.record('candidate', 'prepared' if variants else 'rejected',
                              'prepared' if variants else 'visible_qualification', original)
        projection_diagnostics["qualified_variants"] += len(variants)
        candidate_id = _internal_candidate_id(original)
        if not variants and len(projection_diagnostics["projection_rejections"]) < 32:
            projection_diagnostics["projection_rejections"].append({
                "candidate_id": candidate_id,
                "reason": "visible_qualification",
            })
        for variant in variants[:16]:
            if len(projection_diagnostics["considered_variants"]) >= 32:
                break
            projection_diagnostics["considered_variants"].append({
                "candidate_id": candidate_id,
                "evidence_id": str(variant.get("evidence_id") or ""),
                "qualified_query_ids": sorted(qualified_query_ids((variant,)))[:16],
            })
        for variant in variants:
            prepared.append(variant)
            variant_inputs[id(variant)] = (original, raw_snippet, focus_queries, assigned_requirement_ids)
    selected_host_query_ids: set[str] = set()
    while prepared:
        decision_trace.state["variant_attempts"] += 1
        selected_qualified_public_ids = attributable_query_ids(sources) & public_query_id_set
        selected_public_ids = _fully_matched_query_ids(sources) & public_query_id_set
        selected_canonical_ids = qualified_query_ids(sources) & canonical_intent_query_ids
        selected_authoritative_public_ids = {
            query_id
            for source in sources
            if str(source.get("authority") or "supporting").casefold() == "source_of_truth"
            for query_id in qualified_query_ids((source,))
            if query_id in public_query_id_set
        }
        selected_components = {key for source in sources for key in component_witnesses(source, obligations)}
        missing_compound_priority_ids = (
            compound_priority_query_ids - qualified_query_ids(sources)
        )
        if len(host_query_ids) > 1 and not (
            query_plan.get("component_scope_complete", True) and obligations
        ):
            # Keep a partially matched lookup outstanding only when a complete
            # visible match is still available. Partial-only independent lanes
            # retain their existing diversity priority; none of this is proof.
            available_full_host_ids = set().union(*(
                _fully_matched_query_ids((item,)) for item in prepared
            )) & host_query_ids
            missing_compound_priority_ids |= available_full_host_ids - selected_public_ids
        prepared = _facet_aware_candidates(
            prepared, query_text=query_text,
            fallback_query_ids=context_hint_query_ids, need_query_ids=need_query_ids,
            host_query_ids=host_query_ids,
            required_query_ids=missing_compound_priority_ids - audited_rewrite_query_ids,
            supplemental_query_ids=(audited_rewrite_query_ids | need_query_ids) - qualified_query_ids(sources),
            canonical_query_ids=canonical_intent_query_ids - selected_canonical_ids,
            exact_query_ids=(
                set()
                if len(host_query_ids) > 1 and missing_compound_priority_ids
                else exact_anchor_query_ids - selected_public_ids
            ),
            obligations=obligations, missing_component_ids=mandatory_component_ids - selected_components,
            component_scope_complete=query_plan.get("component_scope_complete", True),
            assigned_evidence_ids=set(assigned_evidence_by_requirement.values()),
            bound_assigned_evidence_ids=required_assigned_evidence_ids,
        )
        _prefer_missing_baseline_candidate(
            prepared, sources, public_query_id_set, host_query_ids, canonical_intent_query_ids,
        )
        missing_required_ids = (
            (compound_priority_query_ids | required_query_id_set | canonical_intent_query_ids | need_query_ids)
            - qualified_query_ids(sources)
        )
        prefer_same_origin_gain_candidate(
            prepared, selected=selected_footprints, footprints=variant_footprints,
            missing_mandatory_ids=missing_required_ids,
            missing_component_ids=mandatory_component_ids - selected_components,
        )
        variant = prepared.pop(0)
        original, raw_snippet, focus_queries, assigned_requirement_ids = variant_inputs[id(variant)]
        candidate_footprint = variant_footprints.get(id(variant))
        candidate_id = _internal_candidate_id(original)
        existing_index = seen_ids.get(variant["evidence_id"])
        if existing_index is not None:
            existing = sources[existing_index]
            start = raw_snippet.find(variant["snippet"])
            previous_start = raw_snippet.find(existing["snippet"])
            disjoint = start >= 0 and previous_start >= 0 and (
                start + len(variant["snippet"]) <= previous_start
                or previous_start + len(existing["snippet"]) <= start
            )
            if (
                disjoint
                and qualified_query_ids((existing,)) <= qualified_query_ids((original,))
                and qualified_query_ids((variant,)) & eligible_query_ids - qualified_query_ids(sources)
            ):
                # A second span needs an independently qualified new direction.
                # Internal component novelty alone cannot multiply one source ID.
                identity = f"{variant['evidence_id']}:{start}:{start + len(variant['snippet'])}"
                variant = {**variant, "evidence_id": "ev-" + hashlib.sha256(identity.encode()).hexdigest()[:16]}
                existing_index = seen_ids.get(variant["evidence_id"])
        candidate_sources = [*sources, variant]
        if existing_index is not None:
            existing = sources[existing_index]
            # Merge attribution, never disconnected text with a fabricated range.
            variant = _requalify_visible_source({
                **variant,
                "retrieval_query_matches": merge_query_matches(
                    existing.get("retrieval_query_matches"), variant.get("retrieval_query_matches"),
                ),
            }, query_text=query_text)
            if not (qualified_query_ids((existing,)) & eligible_query_ids) <= qualified_query_ids((variant,)):
                decision_trace.record('selection', 'rejected', 'replacement_loses_query', original, variant)
                continue
            if not set(component_witnesses(existing, obligations)) <= set(component_witnesses(variant, obligations)):
                decision_trace.record('selection', 'rejected', 'replacement_loses_component', original, variant)
                continue
            if not inline_command_literals(existing["snippet"]) <= inline_command_literals(variant["snippet"]):
                decision_trace.record('selection', 'rejected', 'replacement_loses_command', original, variant)
                continue
            old_footprint = selected_footprints.get(str(variant.get("evidence_id") or ""))
            if not replacement_preserves_or_advances_mandatory(
                old_footprint, candidate_footprint,
                candidate_query_ids=qualified_query_ids((variant,)),
                missing_mandatory_ids=(
                    (compound_priority_query_ids | required_query_id_set | canonical_intent_query_ids | need_query_ids)
                    - qualified_query_ids(sources)
                ),
                candidate_component_ids=set(component_witnesses(variant, obligations)),
                selected_component_ids=selected_components,
            ):
                decision_trace.record('selection', 'rejected', 'replacement_loses_mandatory', original, variant)
                continue
            candidate_sources = [*sources[:existing_index], variant, *sources[existing_index + 1:]]
        same_origin_gain = bool(
            existing_index is not None
            and candidate_footprint is not None
            and (old_footprint := selected_footprints.get(str(variant.get("evidence_id") or ""))) is not None
            and is_same_origin_gain(old_footprint, candidate_footprint)
        )
        decision = context_selection_decision(candidate_sources, public_query_ids)
        packet_cost = docs_context_budget_tokens(_payload(
            candidate_sources, decision=decision, query_plan=query_plan,
        ))
        if packet_cost > max_tokens:
            projection_diagnostics["budget_rejections"] += 1
            if len(projection_diagnostics["projection_rejections"]) < 32:
                projection_diagnostics["projection_rejections"].append({
                    "candidate_id": candidate_id,
                    "evidence_id": str(variant.get("evidence_id") or ""),
                    "reason": "token_budget",
                })
            decision_trace.record('selection', 'rejected', 'token_budget', original, variant, budget_tokens=packet_cost)
            continue
        normalized = variant
        qualified_ids = qualified_query_ids((normalized,))
        attributable_ids = attributable_query_ids((normalized,))
        component_ids = set(component_witnesses(normalized, obligations))
        new_components = component_ids - selected_components
        if not (qualified_ids & eligible_query_ids) and not component_ids:
            decision_trace.record('selection', 'rejected', 'no_visible_qualification', original, variant)
            continue
        dependent_on_covered_parent = {
            str(item.get("query_id") or "")
            for item in query_plan.get("queries") or ()
            if isinstance(item, dict)
            and str(item.get("query_id") or "") in qualified_ids
            and str(item.get("public_parent_query_id") or "") in selected_qualified_public_ids
        }
        novel_independent_public_ids = (
            (attributable_ids & public_query_id_set)
            - selected_qualified_public_ids
            - dependent_on_covered_parent
        )
        # Retrieval attribution is not proof. Anchor children share their parent's
        # direction; only independent lookups can admit a lower-authority duplicate.
        if (
            sources
            and obligations
            and query_plan.get("component_scope_complete", True)
            and selected_authoritative_public_ids
            and str(normalized.get("authority") or "supporting").casefold() != "source_of_truth"
            and not new_components
            and not novel_independent_public_ids
            and not same_origin_gain
            and not (qualified_ids & canonical_intent_query_ids - selected_canonical_ids)
        ):
            decision_trace.record('selection', 'rejected', 'authority_duplicate', original, variant)
            continue
        if sources and not (new_components or
            attributable_ids & public_query_id_set - selected_public_ids or
            qualified_ids & canonical_intent_query_ids - selected_canonical_ids or
            qualified_ids & need_query_ids - qualified_query_ids(sources) or
            qualified_ids & context_hint_query_ids - qualified_query_ids(sources) or
            same_origin_gain
        ):
            decision_trace.record('selection', 'rejected', 'no_new_direction', original, variant)
            continue
        required_ids = qualified_ids & required_query_id_set
        original_hit = "query-original" in qualified_ids
        host_ids = qualified_ids & host_query_ids
        exact_anchor_ids = qualified_ids & exact_anchor_query_ids
        canonical_intent_ids = qualified_ids & canonical_intent_query_ids
        path_only_ids = {
            query_id for query_id in exact_anchor_ids if query_id.startswith("query-path-")
        }
        if (
            path_only_ids
            and qualified_ids <= path_only_ids and not component_ids
            and not _has_visible_non_path_exact_term(
                raw_text=str(normalized.get("snippet") or ""),
                original_question=original_question, explicit_paths=explicit_paths,
            )
        ):
            decision_trace.record('selection', 'rejected', 'path_only', original, variant)
            continue
        # A lexical hit does not complete a host question. Permit a complementary
        # qualified body for one lookup only when it adds two requested terms;
        # a lone topical mention must not spend the remaining source budget.
        if (host_ids and not new_components and not (host_ids - selected_host_query_ids)
            and not same_origin_gain
            and not required_ids and not exact_anchor_ids and not original_hit and not canonical_intent_ids
            and not (any(len(set(normalized["retrieval_query_matches"][key].get("body_matched_terms") or ()) - {
                term for source in sources
                for term in (source.get("retrieval_query_matches", {}).get(key, {}).get("body_matched_terms") or ())
            }) >= (1 if len(host_query_ids) > 1 else 2) for key in host_ids - selected_public_ids))):
            decision_trace.record('selection', 'rejected', 'insufficient_new_host_terms', original, variant)
            continue
        evidence_id = normalized["evidence_id"]
        if evidence_id in seen_ids:
            existing_index = seen_ids[evidence_id]
            candidate_sources = [dict(source) for source in sources]
            candidate_sources[existing_index] = normalized
            candidate_decision = context_selection_decision(candidate_sources, public_query_ids)
            packet_cost = docs_context_budget_tokens(
                _payload(candidate_sources, decision=candidate_decision, query_plan=query_plan)
            )
            if packet_cost <= max_tokens:
                decision_trace.record('selection', 'replaced', 'replaced', original, normalized,
                                      budget_tokens=packet_cost, previous=sources[existing_index])
                sources = candidate_sources
                snapshot[evidence_id] = _snapshot_entry(
                    original, sources[existing_index],
                )
                projection_inputs[evidence_id] = (raw_snippet, focus_queries, original.get("line_start"))
                if candidate_footprint is not None:
                    selected_footprints[evidence_id] = candidate_footprint
                selected_host_query_ids.update(host_ids)
            else:
                decision_trace.record('selection', 'rejected', 'token_budget', original, normalized,
                                      budget_tokens=packet_cost)
            continue
        if len(sources) >= MAX_DOCS_SOURCES:
            # Source cap blocks new rows, not content-preserving replacement of
            # an already selected row. Keep scanning prepared same-origin upgrades.
            decision_trace.record('selection', 'rejected', 'source_cap', original, variant)
            continue
        candidate_sources = [*sources, normalized]
        candidate_decision = context_selection_decision(candidate_sources, public_query_ids)
        candidate_payload = _payload(
            candidate_sources, decision=candidate_decision, query_plan=query_plan,
        )
        packet_cost = docs_context_budget_tokens(candidate_payload)
        if packet_cost > max_tokens:
            decision_trace.record('selection', 'rejected', 'token_budget', original, variant, budget_tokens=packet_cost)
            continue
        decision_trace.record('selection', 'accepted', 'accepted', original, normalized,
                              budget_tokens=packet_cost)
        sources = candidate_sources
        snapshot_source = {
            **original,
            "_assigned_requirement_ids": list(assigned_requirement_ids),
        }
        snapshot[evidence_id] = _snapshot_entry(snapshot_source, normalized)
        projection_inputs[evidence_id] = (
            raw_snippet, focus_queries, original.get("line_start"),
        )
        seen_ids[evidence_id] = len(sources) - 1
        if candidate_footprint is not None:
            selected_footprints[evidence_id] = candidate_footprint
        selected_host_query_ids.update(host_ids)
    if not sources:
        if fallback_ids and not _allow_context_hints:
            # Decide fallback after visible qualification and complete DTO
            # admission. Raw candidates can qualify yet fail that boundary.
            # Conversely, hints must not steal space from a surviving answer.
            primary_attempt = _diagnostics_snapshot(projection_diagnostics)
            result = project_docs_context(
                retrieval=retrieval, max_tokens=max_tokens,
                selection_diagnostics=selection_diagnostics, _allow_context_hints=True,
            )
            hinted_diagnostics = _diagnostics_snapshot(
                retrieval['retrieval_diagnostics']['docs_context_projection']
            )
            hinted_diagnostics['primary_attempt'] = primary_attempt
            retrieval['retrieval_diagnostics']['docs_context_projection'] = hinted_diagnostics
            return result
        if selection_diagnostics is not None:
            selection_diagnostics["component_coverage"] = component_coverage_decision(
                query_plan.get("_component_contract") or (), assignments, (),
                unresolved_residue=query_plan.get("unresolved_parts") or (),
                component_scope_complete=query_plan.get("component_scope_complete", True),
            ).as_payload()
        projection = project_insufficient(
            kind="docs_context",
            missing=["No safe, current, project-scoped documentation context was retrieved."],
            recommended_next_action=None,
            max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
        )
        projection.update({
            "answer_supported": False,
            "answer_available": False,
            "support_status": "insufficient_evidence",
            "context_available": False,
            "edit_ready": False,
        })
        _refresh_estimate(projection)
        return projection, {}
    sources = _expand_selected_snippets(
        sources,
        projection_inputs=projection_inputs,
        query_plan=query_plan,
        public_query_ids=public_query_ids,
        max_tokens=max_tokens,
        obligations=obligations, assignments=assignments,
    )
    for source in sources:
        evidence_id = str(source.get("evidence_id") or "")
        original = snapshot.get(evidence_id, {}).get("source") or {}
        source.update(bind_visible_assignments(original, source, assignments))
        if isinstance(original, dict):
            original["_assigned_requirement_ids"] = list(source["_assigned_requirement_ids"])
    decision = context_selection_decision(sources, public_query_ids)
    component_decision = component_coverage_decision(
        query_plan.get("_component_contract") or (), assignments, sources,
        unresolved_residue=query_plan.get("unresolved_parts") or (),
        component_scope_complete=query_plan.get("component_scope_complete", True),
    )
    payload = _payload(sources, decision=decision, query_plan=query_plan)
    projection_diagnostics["final_visible_evidence_ids"] = [
        str(source.get("evidence_id") or "") for source in payload["sources"][:3]
        if source.get("evidence_id")
    ]
    if selection_diagnostics is not None:
        selection_diagnostics["component_coverage"] = component_decision.as_payload()
    snapshot = {
        source["evidence_id"]: _snapshot_entry(
            snapshot[source["evidence_id"]]["source"], source,
        )
        for source in payload["sources"]
    }
    if (
        fallback_ids
        and not _allow_context_hints
        and len(payload["sources"]) < MAX_DOCS_SOURCES
        and (decision.missing_query_ids or component_decision.missing_component_ids)
    ):
        # A safe retrieval hint is a read-only supplement, not a replacement
        # for already admitted public evidence. Re-run the bounded projector
        # with hints enabled, but accept that packet only when it preserves
        # every primary visible evidence identity and adds a new source.
        primary_diagnostics = projection_diagnostics
        primary_attempt = _diagnostics_snapshot(primary_diagnostics)
        primary_ids = {
            str(source.get("evidence_id") or "")
            for source in payload["sources"]
            if source.get("evidence_id")
        }
        hinted_payload, hinted_snapshot = project_docs_context(
            retrieval=retrieval,
            max_tokens=max_tokens,
            selection_diagnostics=selection_diagnostics,
            _allow_context_hints=True,
        )
        hinted_ids = {
            str(source.get("evidence_id") or "")
            for source in hinted_payload.get("sources") or ()
            if source.get("evidence_id")
        }
        hinted_diagnostics = _diagnostics_snapshot(
            retrieval["retrieval_diagnostics"]["docs_context_projection"]
        )
        hinted_diagnostics['primary_attempt'] = primary_attempt
        if primary_ids < hinted_ids:
            hinted_payload, hinted_snapshot = restore_visible_sources(
                payload, snapshot, hinted_payload, hinted_snapshot,
            )
            _refresh_estimate(hinted_payload)
        if (
            primary_ids < hinted_ids
            and retains_visible_sources(payload, hinted_payload)
            and docs_context_budget_tokens(hinted_payload) <= max_tokens
        ):
            retrieval["retrieval_diagnostics"]["docs_context_projection"] = hinted_diagnostics
            return hinted_payload, hinted_snapshot
        primary_diagnostics['hint_attempt'] = hinted_diagnostics
        retrieval["retrieval_diagnostics"]["docs_context_projection"] = primary_diagnostics
        if selection_diagnostics is not None:
            selection_diagnostics["component_coverage"] = component_decision.as_payload()
    if root := retrieval.get("_source_continuation_project_root"):
        attach_source_continuation_locators(payload, snapshot, root=root, max_tokens=max_tokens)
    return payload, snapshot

def _expand_selected_snippets(
    sources: list[dict[str, Any]], *,
    projection_inputs: dict[str, tuple[str, tuple[str, ...], Any]],
    query_plan: dict[str, Any], public_query_ids: tuple[str, ...], max_tokens: int,
    obligations: tuple[Any, ...] = (),
    assignments: Any = (),
) -> list[dict[str, Any]]:
    expanded = [dict(source) for source in sources]
    for index, source in enumerate(tuple(expanded)):
        values = projection_inputs.get(str(source.get("evidence_id") or ""))
        if values is None:
            continue
        raw_snippet, focus_queries, source_line_start = values
        for limit in _projection_limits(raw_snippet):
            # Each round protects the latest accepted span, not the initial
            # short snippet captured before the expansion loop.
            source = expanded[index]
            snippet, snippet_start, snippet_end = _focused_snippet(
                raw_snippet, focus_queries, limit=limit,
            )
            if len(snippet) <= len(str(source.get("snippet") or "")):
                continue
            # Exact-identifier witnesses need retention even without a normative
            # keyword. Optional fuzzy alias fragments may still be reselected;
            # public attribution, component and assignment guards below apply.
            preserve_span = any(
                trace.get("qualified") is True and trace.get("exact_terms")
                for trace in (source.get("retrieval_query_matches") or {}).values()
            ) or _REQUIRED_RE.search(source["snippet"]) or _FORBIDDEN_RE.search(source["snippet"]) or inline_command_literals(source["snippet"])
            retained_start = raw_snippet.find(source["snippet"])
            if preserve_span and (retained_start < 0
                    or raw_snippet.find(source["snippet"], retained_start + 1) >= 0):
                continue
            if preserve_span and not (snippet_start <= retained_start
                    and retained_start + len(source["snippet"]) <= snippet_end):
                snippet_start = min(snippet_start, retained_start)
                snippet_end = max(snippet_end, retained_start + len(source["snippet"]))
                if snippet_end - snippet_start > limit:
                    continue
                snippet = raw_snippet[snippet_start:snippet_end]
            candidate = dict(source)
            candidate["snippet"] = snippet
            candidate["line_start"], candidate["line_end"] = _focused_line_range(
                raw_snippet, snippet_start, snippet_end, source_line_start,
            )
            candidate = _requalify_visible_source(
                candidate,
                query_text={
                    str(item.get("query_id") or ""): str(item.get("text") or "")
                    for item in query_plan.get("queries") or () if isinstance(item, dict)
                },
            )
            candidate_ids = qualified_query_ids((candidate,))
            if (not candidate_ids and not component_witnesses(candidate, obligations)) or not (
                qualified_query_ids((source,)) & set(public_query_ids)
            ) <= candidate_ids:
                continue
            if not set(component_witnesses(source, obligations)) <= set(component_witnesses(candidate, obligations)):
                continue
            original = source.get("_qualification_candidate", source)
            retained = visible_assignments(original, candidate, assignments)
            if any(item not in retained for item in visible_assignments(original, source, assignments)):
                continue
            candidate = bind_visible_assignments(original, candidate, retained)
            candidate_sources = [*expanded[:index], candidate, *expanded[index + 1:]]
            decision = context_selection_decision(candidate_sources, public_query_ids)
            if docs_context_budget_tokens(_payload(
                candidate_sources, decision=decision, query_plan=query_plan,
            )) <= max_tokens:
                expanded = candidate_sources
    return expanded

def _requalify_visible_source(
    source: dict[str, Any], *, query_text: dict[str, str],
) -> dict[str, Any]:
    visible_text = "\n".join(str(source.get(key) or "") for key in (
        "path_or_url", "section", "snippet",
    ))
    matches: dict[str, dict[str, Any]] = {}
    for query_id, trace in independent_query_probes(source, source.get("_independent_query_plan") or {}).items():
        if not isinstance(trace, dict) or trace.get("derived_from_query_id"):
            continue
        # A physically contiguous continuation of the same structured atom was
        # qualified by source structure upstream, not by lexical coincidence in
        # this child.  Preserve that derived canonical context while still
        # refusing to manufacture original/public coverage.
        if (
            query_id != "query-original"
            and trace.get("qualified") is True
            and trace.get("qualification_route") in {"same_atom_continuation", "same_list_item_continuation"}
            and trace.get("coverage_kind") == "derived"
        ):
            from .context_query_probes import revalidate_structural_continuation
            continuation_trace = revalidate_structural_continuation(trace, source, visible_text)
            matches = merge_query_matches(
                matches, {str(query_id): continuation_trace},
            )
            continue
        # Aggregated lineage belongs to the old window; rebuild it from visible probes.
        probe = {k: v for k, v in trace.items() if k not in {"coverage_kinds", "derived_from_query_ids"}}
        if query_id == "query-original":
            probe["exact_terms"] = list(dict.fromkeys((
                *(probe.get("exact_terms") or ()),
                *(term.normalized_value for term in documentation_exact_terms(
                    query_text.get(str(query_id), ""),
                )),
            )))
        if not probe.get("query_terms") and not probe.get("query_text"):
            planned_text = query_text.get(str(query_id), "")
            if planned_text:
                probe["query_text"] = planned_text
                probe["query_terms"] = sorted(_query_terms((planned_text,)))
        qualification = qualify_evidence(
            probe, query_id=str(query_id), visible_text=visible_text,
            evidence_text=str(source.get("snippet") or ""),
            catalog_role=str(source.get("catalog_role") or ""),
            candidate={**source.get("_qualification_candidate", {}), **source},
            expected_project_identity=source.get("_expected_project_identity"),
            lifecycle_intent=source.get("_lifecycle_intent", "current"),
        )
        qualified_trace = apply_retrieval_need_witness(
            {**probe, "query_id": query_id, "text": query_text.get(str(query_id), "")}, qualification.trace,
            str(source.get("snippet") or ""), source={"verified_owner": qualification.trace.get("bound_subject_context"), "authority": source.get("authority"), "lifecycle_status": "active"})
        matches = merge_query_matches(matches, {str(query_id): qualified_trace})
        parent_trace = derived_parent_trace(
            qualified_trace,
            source_query_id=str(query_id),
            parent_query_id=str(trace.get("public_parent_query_id") or ""),
        )
        if parent_trace is not None and query_id in query_text:
            matches = merge_query_matches(
                matches,
                {str(trace["public_parent_query_id"]): parent_trace},
            )
    qualified_ids = [
        query_id for query_id, trace in matches.items() if trace.get("qualified") is True
    ]
    return {
        **source,
        "retrieval_query_matches": matches,
        "retrieval_query_ids": qualified_ids,
    }


def _required_query_ids(query_plan: dict[str, Any]) -> tuple[str, ...]:
    explicit = query_plan.get("required_query_ids")
    values = explicit if isinstance(explicit, list) else query_plan.get("query_ids") or ()
    return tuple(str(value) for value in values if value)


def _query_ids_for_origins(
    query_plan: dict[str, Any], origins: set[str],
) -> set[str]:
    return {
        str(item.get("query_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and str(item.get("origin") or "") in origins
        and item.get("query_id")
    }


def _public_query_ids(query_plan: dict[str, Any]) -> tuple[str, ...]:
    explicit = query_plan.get("public_query_ids")
    if isinstance(explicit, list):
        return tuple(dict.fromkeys(str(value) for value in explicit if value))
    visible_origins = {"original", "host_lookup", "exact_anchor", "exact_path"}
    values = [
        str(item.get("query_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and str(item.get("origin") or "") in visible_origins
        and item.get("query_id")
    ]
    return tuple(dict.fromkeys(values or _required_query_ids(query_plan)))


def _assigned_requirements_for_source(
    source: dict[str, Any], assignments: dict[str, str],
) -> tuple[str, ...]:
    source_ids = {
        str(source.get(key) or "")
        for key in ("stable_id", "stable_chunk_id", "evidence_id")
        if source.get(key)
    }
    return tuple(
        requirement_id
        for requirement_id, evidence_id in assignments.items()
        if evidence_id in source_ids
    )


def _internal_candidate_id(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    return str(
        source.get("stable_id") or source.get("stable_chunk_id")
        or source.get("evidence_id") or source.get("source") or source.get("path") or ""
    )[:300]


def retrieval_missing_requirements(query_plan: dict[str, Any]) -> tuple[str, ...]:
    """Compatibility hook populated by ``project_docs_context`` before projection."""

    return tuple(query_plan.get("missing_requirement_ids") or ())
