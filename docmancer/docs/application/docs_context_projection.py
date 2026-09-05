"""Bounded retrieval-only projection for free-form project documentation queries."""

from __future__ import annotations

import re
from typing import Any

from docmancer.docs.application.context_selection import (
    context_selection_decision,
    merge_query_matches,
    qualified_query_ids,
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
from docmancer.docs.domain.evidence_qualification import (
    derived_parent_trace,
    qualify_evidence,
)
from docmancer.docs.domain.query_terms import documentation_exact_terms
from docmancer.docs.domain.lifecycle_policy import lifecycle_intent


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Project trusted retrieval as context without claiming answer support."""

    max_tokens = PROJECT_CONTEXT_BUDGET.bounded_tokens(max_tokens)
    projection_diagnostics = {"qualified_variants": 0, "budget_rejections": 0}
    if not isinstance(retrieval.get("retrieval_diagnostics"), dict):
        retrieval["retrieval_diagnostics"] = {}
    retrieval.setdefault("retrieval_diagnostics", {})["docs_context_projection"] = projection_diagnostics
    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    projection_inputs: dict[str, tuple[str, tuple[str, ...], Any]] = {}
    seen_ids: dict[str, int] = {}
    query_plan = dict(retrieval.get("documentation_query_plan") or {})
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
    relation_claim_query_ids = {
        str(item.get("query_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and item.get("facet_id") == "facet-relation-claim"
        and item.get("query_id")
    }
    original_question = str(query_plan.get("original_question") or retrieval.get("question") or query_text.get("query-original") or "")
    requirements = retrieval.get("requirements") or {}
    requirement_items = requirements.get("requirements", ()) if isinstance(requirements, dict) else ()
    expected_project_identity = retrieval.get("project_identity") or next((
        item.get("value") for item in requirement_items
        if isinstance(item, dict) and item.get("kind") == "project_identity"
    ), None)
    request_lifecycle_intent = (
        requirements.get("lifecycle_intent") if isinstance(requirements, dict) else None
    ) or lifecycle_intent(original_question)
    explicit_paths = {
        _normalized_path(value) for value in query_plan.get("explicit_paths") or ()
        if str(value).strip()
    }
    candidates = list(retrieval.get("context_pack") or ())
    selected_host_query_ids: set[str] = set()
    selected_required_ids: set[str] = set()
    while candidates:
        selected_public_ids = qualified_query_ids(sources) & public_query_id_set
        candidates = _facet_aware_candidates(
            candidates, query_text=query_text,
            required_query_ids=public_query_id_set - selected_public_ids,
            assigned_evidence_ids=set(assigned_evidence_by_requirement.values()),
        )
        original = candidates.pop(0)
        if not isinstance(original, dict):
            continue
        original = dict(original)
        if str(original.get("source_class") or "") != "project_doc":
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
        if not qualified_ids:
            continue
        visible_query_ids = qualified_ids & eligible_query_ids
        if not visible_query_ids:
            continue
        required_ids = qualified_ids & required_query_id_set
        original_hit = "query-original" in qualified_ids
        host_ids = qualified_ids & host_query_ids
        exact_anchor_ids = qualified_ids & exact_anchor_query_ids
        canonical_intent_ids = qualified_ids & canonical_intent_query_ids
        relation_claim_ids = qualified_ids & relation_claim_query_ids
        path_only_ids = {
            query_id for query_id in exact_anchor_ids if query_id.startswith("query-path-")
        }
        if (
            path_only_ids
            and qualified_ids <= path_only_ids
            and not _has_visible_non_path_exact_term(
                original,
                raw_text=str(original.get("content") or original.get("display_text") or ""),
                original_question=original_question,
            )
        ):
            continue
        if not required_ids and not exact_anchor_ids and not original_hit and not host_ids and not canonical_intent_ids:
            continue
        if (
            broad_context_only
            and not required_ids
            and not exact_anchor_ids
            and not original_hit
            and not host_ids
            and not canonical_intent_ids
            and not relation_claim_ids
        ):
            continue
        if (
            "contract_fact" in context_only_relations
            and not required_ids
            and not host_ids
            and not exact_anchor_ids
        ):
            continue
        if (
            host_ids
            and not required_ids
            and not original_hit
            and not exact_anchor_ids
            and not canonical_intent_ids
            and not (host_ids - selected_host_query_ids)
        ):
            continue
        # The original question is a fallback for a missing typed facet, not a
        # filler once canonical facet witnesses have already been selected.
        if (
            required_query_id_set
            and not required_ids
            and original_hit
            and selected_required_ids
            and not host_ids
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
        )
        projection_diagnostics["qualified_variants"] += len(variants)
        fitting = []
        for variant in variants:
            existing_index = seen_ids.get(variant["evidence_id"])
            candidate_sources = [*sources, variant]
            if existing_index is not None:
                existing = sources[existing_index]
                # Merge attribution, never disconnected text with a fabricated range.
                variant = _requalify_visible_source({
                    **variant,
                    "retrieval_query_matches": merge_query_matches(
                        existing.get("retrieval_query_matches"),
                        variant.get("retrieval_query_matches"),
                    ),
                }, query_text=query_text)
                if not (qualified_query_ids((existing,)) & public_query_id_set) <= qualified_query_ids((variant,)):
                    continue
                candidate_sources = [*sources[:existing_index], variant, *sources[existing_index + 1:]]
            decision = context_selection_decision(candidate_sources, public_query_ids)
            if estimate_projection_tokens(_payload(
                candidate_sources, decision=decision, query_plan=query_plan,
            )) <= max_tokens:
                fitting.append(variant)
            else:
                projection_diagnostics["budget_rejections"] += 1
        if not fitting:
            continue
        normalized = max(fitting, key=lambda item: (
            len(qualified_query_ids((item,)) & public_query_id_set - selected_public_ids),
            len(qualified_query_ids((item,)) & public_query_id_set),
            -len(item["snippet"]),
        ))
        qualified_ids = qualified_query_ids((normalized,))
        if not qualified_ids or not (qualified_ids & eligible_query_ids):
            continue
        if qualified_ids & public_query_id_set and not (
            qualified_ids & public_query_id_set - selected_public_ids
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
            and qualified_ids <= path_only_ids
            and not _has_visible_non_path_exact_term(
                normalized,
                raw_text=str(normalized.get("snippet") or ""),
                original_question=original_question,
            )
        ):
            continue
        if (
            host_query_ids
            and not (host_ids - selected_host_query_ids)
            and not required_ids
            and not exact_anchor_ids
            and not original_hit
            and not canonical_intent_ids
        ):
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
                selected_required_ids.update(required_ids)
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
        selected_required_ids.update(required_ids)
        selected_host_query_ids.update(host_ids)
        if len(sources) >= MAX_DOCS_SOURCES:
            break
        if public_query_id_set and public_query_id_set.issubset(qualified_query_ids(sources)):
            break

    if not sources:
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
    )
    decision = context_selection_decision(sources, public_query_ids)
    payload = _payload(sources, decision=decision, query_plan=query_plan)
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
) -> list[dict[str, Any]]:
    expanded = [dict(source) for source in sources]
    for limit in (160, 320, 520):
        for index, source in enumerate(tuple(expanded)):
            values = projection_inputs.get(str(source.get("evidence_id") or ""))
            if values is None:
                continue
            raw_snippet, focus_queries, source_line_start = values
            snippet, snippet_start, snippet_end = _focused_snippet(
                raw_snippet, focus_queries, limit=limit,
            )
            if len(snippet) <= len(str(source.get("snippet") or "")):
                continue
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
            if not candidate_ids or not (qualified_query_ids((source,)) & set(public_query_ids)) <= candidate_ids:
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
) -> list[dict[str, Any]]:
    """Retain small qualified alternatives until the actual payload is measured."""
    variants = []
    focuses = tuple(query_text.get(query_id, "") for query_id in sorted(query_ids))
    for limit in (160, 320, 520):
        for focus in (focuses, *((value,) for value in focuses if value)):
            snippet, snippet_start, snippet_end = _focused_snippet(
                raw_snippet, focus, limit=limit,
            )
            candidate = dict(source)
            candidate["snippet"] = snippet
            candidate["line_start"], candidate["line_end"] = _focused_line_range(
                raw_snippet, snippet_start, snippet_end, source_line_start,
            )
            candidate = _requalify_visible_source(candidate, query_text=query_text)
            if snippet and qualified_query_ids((candidate,)) & query_ids:
                variants.append(candidate)
    return variants


def _requalify_visible_source(
    source: dict[str, Any], *, query_text: dict[str, str],
) -> dict[str, Any]:
    visible_text = "\n".join(str(source.get(key) or "") for key in (
        "path_or_url", "section", "snippet",
    ))
    catalog_role = str(source.get("catalog_role") or "")
    matches: dict[str, dict[str, Any]] = {}
    for query_id, trace in (source.get("retrieval_query_matches") or {}).items():
        if not isinstance(trace, dict) or trace.get("derived_from_query_id"):
            continue
        probe = dict(trace)
        if query_id == "query-original":
            probe["exact_terms"] = list(dict.fromkeys((
                *(probe.get("exact_terms") or ()),
                *documentation_exact_terms(query_text.get(str(query_id), "")),
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
            catalog_role=catalog_role,
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
        if parent_trace is not None:
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
    source: dict[str, Any], *, raw_text: str, original_question: str,
) -> bool:
    trace = (source.get("retrieval_query_matches") or {}).get("query-original") or {}
    visible = raw_text.casefold()
    trace_terms = tuple(str(value).strip() for value in trace.get("exact_terms") or ())
    question_terms = tuple(
        token for token in re.findall(r"\b[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*\b", original_question)
        if token.casefold() not in {"docatlas", "docmancer"}
    )
    return any(
        "/" not in term and "\\" not in term
        and re.search(rf"(?<!\w){re.escape(term.strip('.,;:!?').casefold())}(?!\w)", visible)
        for term in (*trace_terms, *question_terms)
        if term
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


_QUERY_STOP_WORDS = frozenset({
    "about", "after", "does", "from", "have", "into", "project", "that",
    "their", "then", "these", "this", "what", "when", "where", "which",
    "with", "работает", "какие", "когда", "проект", "этот",
})


def _query_terms(queries: tuple[str, ...]) -> set[str]:
    return {
        token.casefold()
        for query in queries
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.-]{4,}", query)
        if token.casefold() not in _QUERY_STOP_WORDS
    }


def _focused_snippet(
    text: str, queries: tuple[str, ...], *, limit: int = 520,
) -> tuple[str, int, int]:
    leading = len(text) - len(text.lstrip())
    value = text.strip()
    terms = _query_terms(queries)
    spans = [
        (match.start(), match.end())
        for match in re.finditer(r"\S(?:.*?\S)?(?=(?:\n{2,}|(?<=[.!?])\s+|$))", value, re.S)
    ]
    if not spans:
        paragraph_end = value.find("\n\n")
        end = paragraph_end if 0 < paragraph_end <= limit else limit
        snippet = value[:end].rstrip()
        return snippet, leading, leading + len(snippet)
    best_index = (
        max(
            range(len(spans)),
            key=lambda index: sum(
                term in value[spans[index][0]:spans[index][1]].casefold()
                for term in terms
            ),
        )
        if terms else 0
    )
    start = best_index
    end = best_index
    selected_start, selected_end = spans[best_index]
    if selected_end - selected_start > limit:
        selected_start, selected_end = _bounded_text_window(
            value, selected_start, selected_end, terms=terms, limit=limit,
        )
        selected_start, selected_end = _include_complete_table_row(
            value, selected_start, selected_end, terms=terms, limit=limit,
        )
    for distance in range(1, len(spans)):
        for index in (best_index - distance, best_index + distance):
            if index < 0 or index >= len(spans):
                continue
            adjacent = value[spans[index][0]:spans[index][1]].casefold()
            if terms and not any(term in adjacent for term in terms):
                continue
            candidate_start = min(start, index)
            candidate_end = max(end, index)
            char_start = spans[candidate_start][0]
            char_end = spans[candidate_end][1]
            if char_end - char_start <= limit:
                selected_start, selected_end = char_start, char_end
                start = candidate_start
                end = candidate_end
        if selected_end - selected_start >= limit * 0.7:
            break
    selected_start, selected_end = _include_complete_code_fence(
        value, selected_start, selected_end, limit=limit,
    )
    snippet = value[selected_start:selected_end].strip()
    adjusted_start = value.find(snippet, selected_start, selected_end + 1)
    return snippet, leading + adjusted_start, leading + adjusted_start + len(snippet)


def _include_complete_table_row(
    text: str, start: int, end: int, *, terms: set[str], limit: int,
) -> tuple[int, int]:
    matched = [
        text.casefold().find(term, start, end)
        for term in terms
        if text.casefold().find(term, start, end) >= 0
    ]
    if not matched:
        return start, end
    anchor = min(matched)
    row_start = text.rfind("\n", 0, anchor) + 1
    row_end_match = text.find("\n", anchor)
    row_end = len(text) if row_end_match < 0 else row_end_match
    row = text[row_start:row_end]
    if "|" not in row or row_end - row_start > limit:
        return start, end
    expanded_start = min(start, row_start)
    expanded_end = max(end, row_end)
    if expanded_end - expanded_start <= limit:
        return expanded_start, expanded_end
    return row_start, row_end


def _bounded_text_window(
    text: str, start: int, end: int, *, terms: set[str], limit: int,
) -> tuple[int, int]:
    segment = text[start:end]
    matched_positions = [
        segment.casefold().find(term) for term in terms if term in segment.casefold()
    ]
    anchor = min((position for position in matched_positions if position >= 0), default=0)
    window_start = start + max(0, anchor - limit // 3)
    window_end = min(end, window_start + limit)
    window_start = max(start, window_end - limit)
    return window_start, window_end


def _include_complete_code_fence(
    text: str, start: int, end: int, *, limit: int,
) -> tuple[int, int]:
    blocks = []
    opening = None
    for match in re.finditer(r"^[ \t]*(`{3,}|~{3,})([^\n]*)", text, re.M):
        if opening is None:
            opening = match
        elif (
            match.group(1)[0] == opening.group(1)[0]
            and len(match.group(1)) >= len(opening.group(1))
            and not match.group(2).strip()
        ):
            blocks.append((opening.start(), match.end(), True))
            opening = None
    if opening is not None:
        blocks.append((opening.start(), len(text), False))
    for fence_start, fence_end, closed in blocks:
        if (
            closed and end <= fence_start and not text[end:fence_start].strip()
            and re.search(r"\b(?:following|command|example)\b", text[start:end], re.I)
            and fence_end - start <= limit
        ):
            end = fence_end
        if start < fence_end and end > fence_start:
            expanded_start = min(start, fence_start)
            expanded_end = max(end, fence_end)
            if closed and expanded_end - expanded_start <= limit:
                start, end = expanded_start, expanded_end
                continue
            # A bounded payload must not expose a syntactically broken fence.
            before = text.rfind("\n\n", 0, fence_start)
            safe_start = 0 if before < 0 else before + 2
            if fence_start - safe_start <= limit and fence_start > safe_start:
                return safe_start, fence_start
            return start, start
    return start, end


def _focused_line_range(
    text: str, start: int, end: int, source_line_start: Any,
) -> tuple[int | None, int | None]:
    if not isinstance(source_line_start, int) or source_line_start < 1:
        return None, None
    line_start = source_line_start + text[:start].count("\n")
    line_end = line_start + text[start:end].count("\n")
    return line_start, line_end


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


def _context_rank(
    source: Any, query_text: dict[str, str], required_query_ids: set[str],
    assigned_evidence_ids: set[str] | None = None,
) -> tuple[float, ...]:
    if not isinstance(source, dict):
        return (-1.0,)
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
    return (
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
    assigned_evidence_ids: set[str] | None = None,
) -> list[Any]:
    # Only the caller's accepted visible witnesses remove coverage needs.
    return sorted(candidates, key=lambda source: (
        len(qualified_query_ids((source,)) & required_query_ids),
        _context_rank(source, query_text, required_query_ids, assigned_evidence_ids),
    ), reverse=True)


def _payload(
    sources: list[dict[str, Any]], *, decision: Any = None,
    query_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_queries = {
        str(item.get("query_id") or ""): item
        for item in (query_plan or {}).get("queries") or ()
        if isinstance(item, dict)
    }
    context_only = bool(query_plan.get("broad_context_only"))
    covered_query_ids = set(decision.covered_query_ids if decision else ())
    assigned_requirement_ids = set(
        str(value) for value in query_plan.get("assigned_requirement_ids") or ()
    )
    facets = []
    for query_id, item in plan_queries.items():
        facet_id = str(item.get("facet_id") or "")
        if not facet_id:
            continue
        retrieved = any(
            query_id in qualified_query_ids((source,)) for source in sources
        )
        requirement_id = str(item.get("requirement_id") or "")
        assigned_evidence_ids = [
            str(source.get("evidence_id") or "")
            for source in sources
            if requirement_id
            and requirement_id in set(source.get("_assigned_requirement_ids") or ())
            and query_id in qualified_query_ids((source,))
        ]
        proved = bool(requirement_id and requirement_id in assigned_requirement_ids and assigned_evidence_ids)
        status = (
            "covered" if retrieved and proved and not context_only else
            "retrieval_only" if retrieved else
            "missing"
        )
        retrieved_evidence_ids = [
            str(source.get("evidence_id") or "")
            for source in sources
            if query_id in qualified_query_ids((source,))
        ]
        evidence_ids = assigned_evidence_ids if status == "covered" else retrieved_evidence_ids
        facets.append({
            "id": facet_id,
            "requirement_id": requirement_id or None,
            "question": str(item.get("text") or query_id),
            "status": status,
            "evidence_ids": evidence_ids,
        })
    grouped_facets: dict[str, dict[str, Any]] = {}
    status_rank = {"missing": 0, "retrieval_only": 1, "covered": 2}
    for facet in facets:
        current = grouped_facets.get(facet["id"])
        if current is None:
            grouped_facets[facet["id"]] = dict(facet)
            continue
        current["evidence_ids"] = list(dict.fromkeys((
            *current["evidence_ids"], *facet["evidence_ids"],
        )))
        if status_rank[facet["status"]] > status_rank[current["status"]]:
            current["status"] = facet["status"]
            current["question"] = facet["question"]
            current["requirement_id"] = facet["requirement_id"]
    facets = list(grouped_facets.values())
    covered_facets = [item for item in facets if item["status"] == "covered"]
    missing_facets = [item for item in facets if item["status"] == "missing"]
    facet_coverage = (
        "unverified" if context_only or not facets else
        "full" if len(covered_facets) == len(facets) else
        "partial" if covered_facets else
        "none"
    )
    public_sources = [
        {
            key: value for key, value in source.items()
            if key not in {
                "retrieval_query_ids", "retrieval_query_matches",
                "_assigned_requirement_ids", "catalog_role",
                "_qualification_candidate", "_expected_project_identity", "_lifecycle_intent",
            }
        }
        for source in sources
    ]
    payload = {
        "status": "ok",
        "kind": "docs_context",
        "context_status": "ready",
        "context_available": True,
        "answer_supported": False,
        "answer_available": False,
        "support_status": "retrieval_only",
        "answer_policy": "cite_only",
        "coverage_policy": "retrieval_attribution_only",
        "query_coverage": decision.query_coverage if decision else "partial",
        "retrieval_coverage": decision.query_coverage if decision else "partial",
        "facet_coverage": facet_coverage,
        "covered_query_ids": list(decision.covered_query_ids) if decision else [],
        "missing_query_ids": list(decision.missing_query_ids) if decision else [],
        "missing_facets": missing_facets,
        "facets": facets,
        "sources": public_sources,
        "edit_ready": False,
        "investigation_allowed": True,
        "instruction": (
            "Answer only claims directly grounded in the returned sources, cite their paths, "
            "and do not claim that the context is complete. Never use this retrieval-only "
            "result to authorize an edit."
        ),
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    return payload


def retrieval_missing_requirements(query_plan: dict[str, Any]) -> tuple[str, ...]:
    """Compatibility hook populated by ``project_docs_context`` before projection."""

    return tuple(query_plan.get("missing_requirement_ids") or ())
