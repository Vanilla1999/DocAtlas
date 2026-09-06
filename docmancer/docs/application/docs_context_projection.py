"""Bounded retrieval-only projection for free-form project documentation queries."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from ._docs_context_payload import _payload

from docmancer.docs.application.context_selection import (
    component_coverage_decision,
    component_obligations,
    component_witnesses,
    context_selection_decision,
    merge_query_matches,
    qualified_query_ids,
    visible_assignment_hashes,
)
from docmancer.docs.application.model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS,
    INSUFFICIENT_EVIDENCE_MAX_TOKENS,
    MAX_DOCS_SOURCES,
    _docs_source,
    _refresh_estimate,
    _snapshot_entry,
    estimate_projection_tokens,
    project_insufficient,
)
from docmancer.docs.domain.project_doc_ranking import (
    project_question_lane,
    project_source_lane,
)
from docmancer.docs.domain.context_budget import PROJECT_CONTEXT_BUDGET
from docmancer.docs.domain.context_windows import (
    _focused_line_range, _focused_snippet, _is_complete_source_span,
    _projection_limits, _query_terms,
)
from docmancer.docs.domain.evidence_qualification import (
    derived_parent_trace,
    qualify_evidence,
)
from docmancer.docs.domain.query_terms import documentation_exact_terms
from docmancer.docs.domain.documentation_query_plan import technical_anchors
from docmancer.docs.domain.lifecycle_policy import lifecycle_intent
from docmancer.docs.domain.answer_units import extract_answer_units, _NEGATION_RE
from docmancer.docs.domain.normative_language import _FORBIDDEN_RE, _REQUIRED_RE


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
    selection_diagnostics: dict[str, Any] | None = None,
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
    host_query_ids = _query_ids_for_origins(query_plan, {"host_lookup"})
    exact_anchor_query_ids = _query_ids_for_origins(
        query_plan, {"exact_anchor", "exact_path"},
    )
    canonical_intent_query_ids = _query_ids_for_origins(
        query_plan, {"canonical_intent"},
    )
    eligible_query_ids = public_query_id_set | canonical_intent_query_ids
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
        required_query_ids=public_query_id_set,
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
    for original in initially_ranked:
        if not isinstance(original, dict):
            continue
        original = dict(original)
        if str(original.get("source_class") or "") != "project_doc":
            continue
        if explicit_paths and _normalized_path(original.get("path") or "") not in explicit_paths:
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
            continue
        if not visible_query_ids and not component_ids:
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
                raw_text=str(original.get("content") or original.get("display_text") or ""),
                original_question=original_question, explicit_paths=explicit_paths,
            )
        ):
            continue
        if not component_ids and not required_ids and not exact_anchor_ids and not original_hit and not host_ids and not canonical_intent_ids:
            continue
        if (
            "contract_fact" in context_only_relations
            and not component_ids
            and not required_ids
            and not host_ids
            and not exact_anchor_ids
        ):
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
            for query_id in qualified_ids if query_id.startswith("query-supplemental-")
        )
        focus_queries = (
            tuple(value for value in (*required_matches, *supplemental_matches) if value)
            or tuple(query_text.get(query_id, "") for query_id in qualified_ids)
        )
        # Establish source identity first; only qualified complete variants cross
        # the projection boundary below.
        normalized = _docs_source(original, display_snippet=raw_snippet[:520])
        if normalized is None:
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
            "_expected_project_identity": original["_expected_project_identity"],
            "_lifecycle_intent": original["_lifecycle_intent"],
        })
        variants = _qualified_fragments(
            normalized,
            raw_snippet=raw_snippet,
            query_ids=qualified_ids & eligible_query_ids,
            query_text=query_text,
            source_line_start=original.get("line_start"),
            obligations=obligations, assignments=assignments,
        )
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
        selected_qualified_public_ids = qualified_query_ids(sources) & public_query_id_set
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
        prepared = _facet_aware_candidates(
            prepared, query_text=query_text,
            required_query_ids=public_query_id_set - (qualified_query_ids(sources) if len(host_query_ids) > 1 else selected_public_ids),
            canonical_query_ids=canonical_intent_query_ids - selected_canonical_ids,
            exact_query_ids=exact_anchor_query_ids - selected_public_ids,
            obligations=obligations, missing_component_ids=mandatory_component_ids - selected_components,
            assigned_evidence_ids=set(assigned_evidence_by_requirement.values()),
            bound_assigned_evidence_ids=required_assigned_evidence_ids,
        )
        variant = prepared.pop(0)
        original, raw_snippet, focus_queries, assigned_requirement_ids = variant_inputs[id(variant)]
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
                and (qualified_query_ids((variant,)) & eligible_query_ids - qualified_query_ids(sources)
                     or set(component_witnesses(variant, obligations)) - selected_components)
            ):
                # Distinct visible spans may prove different facts in one chunk.
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
                continue
            if not set(component_witnesses(existing, obligations)) <= set(component_witnesses(variant, obligations)):
                continue
            candidate_sources = [*sources[:existing_index], variant, *sources[existing_index + 1:]]
        decision = context_selection_decision(candidate_sources, public_query_ids)
        if estimate_projection_tokens(_payload(
            candidate_sources, decision=decision, query_plan=query_plan,
        )) > max_tokens:
            projection_diagnostics["budget_rejections"] += 1
            if len(projection_diagnostics["projection_rejections"]) < 32:
                projection_diagnostics["projection_rejections"].append({
                    "candidate_id": candidate_id,
                    "evidence_id": str(variant.get("evidence_id") or ""),
                    "reason": "token_budget",
                })
            continue
        normalized = variant
        qualified_ids = qualified_query_ids((normalized,))
        component_ids = set(component_witnesses(normalized, obligations))
        new_components = component_ids - selected_components
        if not (qualified_ids & eligible_query_ids) and not component_ids:
            continue
        dependent_on_covered_parent = {
            str(item.get("query_id") or "")
            for item in query_plan.get("queries") or ()
            if isinstance(item, dict)
            and str(item.get("query_id") or "") in qualified_ids
            and str(item.get("public_parent_query_id") or "") in selected_qualified_public_ids
        }
        novel_independent_public_ids = (
            (qualified_ids & public_query_id_set)
            - selected_qualified_public_ids
            - dependent_on_covered_parent
        )
        # Query coverage is retrieval attribution, not a second semantic proof.
        # Generated exact-anchor children inherit their public parent's direction:
        # once that parent is already qualified, those children cannot by themselves
        # admit a lower-authority duplicate source. Explicit host lookups with no
        # covered parent still count as genuinely new independent directions.
        if (
            sources
            and obligations
            and query_plan.get("component_scope_complete", True)
            and selected_authoritative_public_ids
            and str(normalized.get("authority") or "supporting").casefold() != "source_of_truth"
            and not new_components
            and not novel_independent_public_ids
            and not (qualified_ids & canonical_intent_query_ids - selected_canonical_ids)
        ):
            continue
        if sources and not (new_components or
            qualified_ids & public_query_id_set - selected_public_ids or
            qualified_ids & canonical_intent_query_ids - selected_canonical_ids
        ):
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
            continue
        # Compound reads may supplement a partial lead; single-direction reads retain it.
        if (host_ids and not new_components and not (host_ids - selected_host_query_ids)
            and not required_ids and not exact_anchor_ids and not original_hit and not canonical_intent_ids
            and not (len(host_query_ids) > 1 and any(set(normalized["retrieval_query_matches"][key].get("matched_terms") or ()) - {
                term for source in sources
                for term in (source.get("retrieval_query_matches", {}).get(key, {}).get("matched_terms") or ())
            } for key in host_ids - selected_public_ids))):
            continue
        evidence_id = normalized["evidence_id"]
        if evidence_id in seen_ids:
            existing_index = seen_ids[evidence_id]
            candidate_sources = [dict(source) for source in sources]
            candidate_sources[existing_index] = normalized
            candidate_decision = context_selection_decision(candidate_sources, public_query_ids)
            if estimate_projection_tokens(
                    _payload(candidate_sources, decision=candidate_decision, query_plan=query_plan)
            ) <= max_tokens:
                sources = candidate_sources
                snapshot[evidence_id] = _snapshot_entry(
                    original, sources[existing_index],
                )
                projection_inputs[evidence_id] = (raw_snippet, focus_queries, original.get("line_start"))
                selected_host_query_ids.update(host_ids)
            continue
        candidate_sources = [*sources, normalized]
        candidate_decision = context_selection_decision(candidate_sources, public_query_ids)
        candidate_payload = _payload(
            candidate_sources, decision=candidate_decision, query_plan=query_plan,
        )
        if estimate_projection_tokens(candidate_payload) > max_tokens:
            continue
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
        selected_host_query_ids.update(host_ids)
        if len(sources) >= MAX_DOCS_SOURCES:
            break

    if not sources:
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
        visible_hashes = visible_assignment_hashes(
            original, source, assignments,
        )
        source["_visible_assignment_hashes"] = list(visible_hashes)
        source["_assigned_requirement_ids"] = [
            str(assignment.get("requirement_id") or "")
            for assignment in assignments
            if isinstance(assignment, dict)
            and assignment.get("requirement_id")
            and assignment.get("projected_content_hash") in visible_hashes
            and str(assignment.get("requirement_id"))
            in set(source.get("_assigned_requirement_ids") or ())
        ]
        if isinstance(original, dict):
            original["_assigned_requirement_ids"] = list(source["_assigned_requirement_ids"])
    decision = context_selection_decision(sources, public_query_ids)
    payload = _payload(sources, decision=decision, query_plan=query_plan)
    projection_diagnostics["final_visible_evidence_ids"] = [
        str(source.get("evidence_id") or "") for source in payload["sources"][:3]
        if source.get("evidence_id")
    ]
    if selection_diagnostics is not None:
        selection_diagnostics["component_coverage"] = component_coverage_decision(
            query_plan.get("_component_contract") or (), assignments, sources,
            unresolved_residue=query_plan.get("unresolved_parts") or (),
            component_scope_complete=query_plan.get("component_scope_complete", True),
        ).as_payload()
    snapshot = {
        source["evidence_id"]: _snapshot_entry(
            snapshot[source["evidence_id"]]["source"], source,
        )
        for source in payload["sources"]
    }
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
            ) or _REQUIRED_RE.search(source["snippet"]) or _FORBIDDEN_RE.search(source["snippet"])
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
            if not set(source.get("_visible_assignment_hashes") or ()) <= set(visible_assignment_hashes(
                source.get("_qualification_candidate", source), candidate, assignments,
            )):
                continue
            candidate_sources = [*expanded[:index], candidate, *expanded[index + 1:]]
            decision = context_selection_decision(candidate_sources, public_query_ids)
            if estimate_projection_tokens(_payload(
                candidate_sources, decision=decision, query_plan=query_plan,
            )) <= max_tokens:
                expanded = candidate_sources
    return expanded


def _qualified_fragments(
    source: dict[str, Any], *, raw_snippet: str, query_ids: set[str],
    query_text: dict[str, str], source_line_start: Any,
    obligations: tuple[Any, ...] = (),
    assignments: Any = (),
) -> list[dict[str, Any]]:
    """Retain small qualified alternatives until the actual payload is measured."""
    variants = []
    seen_spans = set()
    focuses = (*tuple(query_text.get(query_id, "") for query_id in sorted(query_ids)),
               *component_witnesses({**source, "snippet": raw_snippet}, obligations).values())
    for limit in _projection_limits(raw_snippet):
        for focus in (focuses, *((value,) for value in focuses if value)):
            snippet, snippet_start, snippet_end = _focused_snippet(
                raw_snippet, focus, limit=limit,
            )
            if (snippet_start, snippet_end) in seen_spans:
                continue
            seen_spans.add((snippet_start, snippet_end))
            candidate = dict(source)
            candidate["snippet"] = snippet
            candidate["line_start"], candidate["line_end"] = _focused_line_range(
                raw_snippet, snippet_start, snippet_end, source_line_start,
            )
            candidate = _requalify_visible_source(candidate, query_text=query_text)
            hashes = visible_assignment_hashes(source.get("_qualification_candidate", source), candidate, assignments)
            candidate["_visible_assignment_hashes"] = list(hashes)
            candidate["_assigned_requirement_ids"] = [
                item["requirement_id"] for item in assignments
                if item.get("projected_content_hash") in hashes
                and item.get("requirement_id") in set(source.get("_assigned_requirement_ids") or ())
            ]
            if snippet and (qualified_query_ids((candidate,)) & query_ids or component_witnesses(candidate, obligations)):
                variants.append(candidate)
    # Variants of one evidence item compete before global source selection.
    # Prefer a bounded, structurally complete contiguous span when coverage is
    # otherwise equivalent, so a shorter mid-sentence prefix cannot consume the
    # slot and later block a safe expansion under the same 800-token budget.
    variants.sort(
        key=lambda candidate: (
            len(qualified_query_ids((candidate,)) & query_ids),
            len(component_witnesses(candidate, obligations)),
            len(candidate.get("_visible_assignment_hashes") or ()),
            int(_is_complete_source_span(
                raw_snippet, str(candidate.get("snippet") or ""),
            )),
            -len(str(candidate.get("snippet") or "")),
        ),
        reverse=True,
    )
    return variants


def _requalify_visible_source(
    source: dict[str, Any], *, query_text: dict[str, str],
) -> dict[str, Any]:
    visible_text = "\n".join(str(source.get(key) or "") for key in (
        "path_or_url", "section", "snippet",
    ))
    matches: dict[str, dict[str, Any]] = {}
    for query_id, trace in (source.get("retrieval_query_matches") or {}).items():
        if not isinstance(trace, dict) or trace.get("derived_from_query_id"):
            continue
        probe = dict(trace)
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
            probe,
            query_id=str(query_id),
            visible_text=visible_text,
            evidence_text=str(source.get("snippet") or ""),
            catalog_role=str(source.get("catalog_role") or ""),
            candidate=source.get("_qualification_candidate", source),
            expected_project_identity=source.get("_expected_project_identity"),
            lifecycle_intent=source.get("_lifecycle_intent", "current"),
        )
        matches[str(query_id)] = dict(qualification.trace)
        parent_trace = derived_parent_trace(
            qualification.trace,
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


def _has_visible_non_path_exact_term(
    *, raw_text: str, original_question: str, explicit_paths: set[str],
) -> bool:
    # Use whole anchors, not CamelCase substrings extracted from a file path.
    # A heading such as "Reference" is not evidence for a topic merely because
    # the requested file is named REFERENCE.md. Apply the ordinary body qualifier
    # here too; headings, links and identifier prefixes cannot satisfy a topic.
    terms = (
        term for term in technical_anchors(original_question)
        if "/" not in term and "\\" not in term
        and _normalized_path(term) not in explicit_paths
    )
    return any(
        qualify_evidence(
            {"query_text": term, "query_terms": [term], "exact_terms": [term]},
            query_id="exact-topic", visible_text=raw_text, evidence_text=raw_text,
        ).qualified
        for term in terms
    )


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


def _normalized_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").removeprefix("./").casefold()


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


def _context_rank(
    source: Any, query_text: dict[str, str], required_query_ids: set[str],
    assigned_evidence_ids: set[str] | None = None,
) -> tuple[float, ...]:
    if not isinstance(source, dict):
        return (-1.0,)
    source = {**source.get("_qualification_candidate", {}), **source}
    matches = source.get("retrieval_query_matches") or {}
    qualified = [
        query_id for query_id, trace in matches.items()
        if isinstance(trace, dict) and trace.get("qualified") is True
    ]
    lexical = sum(
        float((matches.get(query_id) or {}).get("lexical_score") or 0.0)
        for query_id in qualified
    )
    required = [query_id for query_id in qualified if query_id in required_query_ids]
    required_lexical = sum(
        float((matches.get(query_id) or {}).get("lexical_score") or 0.0)
        for query_id in required
    )
    authority = str(source.get("authority") or "supporting").casefold()
    authority_score = 2.0 if authority == "source_of_truth" else 1.0
    catalog_role = str(source.get("catalog_role") or "")
    preferred_role_score = float(sum(
        catalog_role in set((matches.get(query_id) or {}).get("preferred_catalog_roles") or ())
        for query_id in qualified
    ))
    path = str(source.get("path") or source.get("source") or "")
    original_question = query_text.get("query-original", "")
    requested_lane = project_question_lane(original_question)
    source_lane = project_source_lane(path)
    lane_score = 2.0 if source_lane == requested_lane else 1.0 if source_lane == "operational" else 0.0
    identity_text = " ".join(str(source.get(key) or "") for key in (
        "path", "source", "heading_path", "title", "catalog_description", "description",
        "content", "display_text", "snippet",
    )).casefold()[:2_000]
    identity_score = float(sum(
        term in identity_text for term in _query_terms((original_question,))
    ))
    source_ids = {
        str(source.get(key) or "")
        for key in ("stable_id", "stable_chunk_id", "evidence_id")
        if source.get(key)
    }
    assigned_score = float(bool(source_ids & (assigned_evidence_ids or set())))
    # A visible imperative is a better procedural lead than a topical mention.
    action_score = 0.0
    for query_id in required:
        action = re.match(r"how\s+(?:do|can|should)\s+i\s+(\w+)\b", query_text.get(query_id, ""), re.I)
        if not action and re.match(r"(?:what|which)\b", query_text.get(query_id, ""), re.I):
            action = re.search(r"\b(run|use|call|invoke)\b", query_text[query_id], re.I)
        if action and not (_NEGATION_RE.search(query_text[query_id]) or _FORBIDDEN_RE.search(query_text[query_id])) and any(unit.proposition and not (_NEGATION_RE.search(unit.text) or _FORBIDDEN_RE.search(unit.text)) and re.search(
            rf"(?:^|[.!?]\s+|^\s*\|[^|\n]*\|\s*){re.escape(action[1])}\b|\b(?:use|run|call|invoke)\s+[^.!?\n`]{{0,80}}`[^`\n]+`",
            unit.text, re.I | re.M,
        ) for unit in extract_answer_units(str(source.get("snippet") or source.get("content") or ""))):
            action_score += 1.0
    return (
        action_score,
        lane_score,
        float(len(required)),
        assigned_score,
        preferred_role_score,
        authority_score,
        identity_score,
        float("query-original" in qualified),
        required_lexical,
        float(len(qualified) - len(required)),
        lexical,
        float((source.get("project_ranking") or {}).get("final_score") or 0.0),
        float(source.get("score") or 0.0),
    )


def _facet_aware_candidates(
    candidates: list[Any], *, query_text: dict[str, str], required_query_ids: set[str],
    canonical_query_ids: set[str] | None = None,
    assigned_evidence_ids: set[str] | None = None,
    bound_assigned_evidence_ids: set[str] | None = None,
    exact_query_ids: set[str] | None = None,
    obligations: tuple[Any, ...] = (), missing_component_ids: set[str] | None = None,
) -> list[Any]:
    # Exact-anchor lanes are identity-sensitive: when two candidates both
    # visibly qualify, preserve the upstream assigned witness before rewarding
    # extra lexical mentions. General host/original lanes keep action and
    # relevance ranking first so assignments cannot crowd out procedural facts.
    def candidate_key(source: Any) -> tuple[Any, ...]:
        qualified_ids = qualified_query_ids((source,))
        exact_count = len(qualified_ids & (exact_query_ids or set()))
        component_count = len(
            set(component_witnesses(source, obligations)) & (missing_component_ids or set())
        )
        rank = _context_rank(source, query_text, required_query_ids, assigned_evidence_ids)
        identity = {**source.get("_qualification_candidate", {}), **source}
        source_ids = {
            str(identity.get(key) or "")
            for key in ("stable_id", "stable_chunk_id", "evidence_id")
            if identity.get(key)
        }
        bound_assignment = int(bool(source_ids & (bound_assigned_evidence_ids or set())))
        match_ratio = sum(
            float(trace.get("match_ratio") or 0.0)
            for key, trace in (source.get("retrieval_query_matches") or {}).items()
            if key in required_query_ids and trace.get("qualified") is True
        )
        return (
            int(exact_count > 0),
            component_count,
            bound_assignment,
            rank[3] if exact_count else 0.0,
            exact_count,
            len(_fully_matched_query_ids((source,)) & required_query_ids),
            len(qualified_ids & required_query_ids),
            rank[0],
            match_ratio,
            len(qualified_ids & (canonical_query_ids or set())),
            rank[1:3] + rank[4:],
        )

    return sorted(candidates, key=candidate_key, reverse=True)


def _fully_matched_query_ids(sources: Any) -> set[str]:
    # Partial lexical attribution must not crowd out a complete visible match.
    # This is a selection preference, not a semantic completeness claim.
    return {
        query_id for source in sources
        for query_id, trace in (source.get("retrieval_query_matches") or {}).items()
        if isinstance(trace, dict) and trace.get("qualified") is True
        and (trace.get("match_ratio") == 1.0 or trace.get("mode") == "exact_path")
    }


def retrieval_missing_requirements(query_plan: dict[str, Any]) -> tuple[str, ...]:
    """Compatibility hook populated by ``project_docs_context`` before projection."""

    return tuple(query_plan.get("missing_requirement_ids") or ())
