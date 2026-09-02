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


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Project trusted retrieval as context without claiming answer support."""

    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, int] = {}
    per_path: dict[str, int] = {}
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
    relation_claim_query_ids = {
        str(item.get("query_id") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
        and item.get("facet_id") == "facet-relation-claim"
        and item.get("query_id")
    }
    original_question = str(query_plan.get("original_question") or "")
    explicit_paths = {
        _normalized_path(value) for value in query_plan.get("explicit_paths") or ()
        if str(value).strip()
    }
    candidates = _facet_aware_candidates(
        list(retrieval.get("context_pack") or ()),
        query_text=query_text,
        required_query_ids=(
            exact_anchor_query_ids | host_query_ids
            if broad_context_only
            else required_query_id_set | exact_anchor_query_ids | host_query_ids
        ),
        assigned_evidence_ids=set(assigned_evidence_by_requirement.values()),
    )
    selected_host_lookup = False
    selected_required_ids: set[str] = set()
    for original in candidates:
        if not isinstance(original, dict):
            continue
        original = dict(original)
        if str(original.get("source_class") or "") != "project_doc":
            continue
        if str(original.get("lifecycle_status") or "active") != "active":
            continue
        if str(original.get("freshness") or "current") != "current":
            continue
        if str(original.get("index_freshness") or "synchronized") != "synchronized":
            continue
        if original.get("risk_flags"):
            continue
        project_identity = str(original.get("project_identity") or "").strip()
        if not project_identity:
            continue
        if explicit_paths and _normalized_path(
            original.get("path") or original.get("source") or ""
        ) in explicit_paths:
            matches = merge_query_matches(original.get("retrieval_query_matches"))
            for query_id in exact_anchor_query_ids:
                if query_id.startswith("query-path-"):
                    matches[query_id] = {
                        "qualified": True,
                        "mode": "exact_path",
                        "query_text": query_text.get(query_id, ""),
                    }
            original["retrieval_query_matches"] = matches
        qualified_ids = qualified_query_ids((original,))
        if not qualified_ids:
            continue
        visible_query_ids = qualified_ids & public_query_id_set
        if not visible_query_ids:
            continue
        required_ids = qualified_ids & required_query_id_set
        original_hit = "query-original" in qualified_ids
        host_ids = qualified_ids & host_query_ids
        exact_anchor_ids = qualified_ids & exact_anchor_query_ids
        canonical_intent_ids = qualified_ids & canonical_intent_query_ids
        relation_claim_ids = qualified_ids & relation_claim_query_ids
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
        ):
            continue
        if host_ids and not required_ids and not original_hit and selected_host_lookup:
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
        focused_snippet, snippet_start, snippet_end = _focused_snippet(
            raw_snippet,
            tuple(value for value in (*required_matches, *supplemental_matches) if value)
            or tuple(query_text.get(query_id, "") for query_id in qualified_ids),
        )
        normalized = _docs_source(original, display_snippet=focused_snippet)
        if normalized is None or len(normalized["snippet"]) < 40:
            continue
        path = normalized["path_or_url"]
        if per_path.get(path, 0) >= 2:
            continue
        assigned_requirement_ids = _assigned_requirements_for_source(
            original, assigned_evidence_by_requirement,
        )
        line_start, line_end = _focused_line_range(
            raw_snippet,
            snippet_start,
            snippet_end,
            original.get("line_start"),
        )
        normalized.update({
            "project_identity": project_identity,
            "line_start": line_start,
            "line_end": line_end,
            "authority": str(original.get("authority") or "supporting"),
            "scope": str(original.get("doc_scope") or "project"),
            "retrieval_query_ids": list(original.get("retrieval_query_ids") or ()),
            "retrieval_query_matches": dict(original.get("retrieval_query_matches") or {}),
            "_assigned_requirement_ids": list(assigned_requirement_ids),
        })
        evidence_id = normalized["evidence_id"]
        if evidence_id in seen_ids:
            existing_index = seen_ids[evidence_id]
            merged_matches = merge_query_matches(
                sources[existing_index].get("retrieval_query_matches"),
                normalized.get("retrieval_query_matches"),
            )
            merged_query_ids = [
                key for key, value in merged_matches.items() if value.get("qualified") is True
            ]
            candidate_sources = [dict(source) for source in sources]
            candidate_sources[existing_index]["retrieval_query_ids"] = merged_query_ids
            candidate_sources[existing_index]["retrieval_query_matches"] = merged_matches
            candidate_decision = context_selection_decision(candidate_sources, public_query_ids)
            if estimate_projection_tokens(
                    _payload(candidate_sources, decision=candidate_decision, query_plan=query_plan)
            ) <= max_tokens:
                sources = candidate_sources
                snapshot[evidence_id] = _snapshot_entry(
                    snapshot[evidence_id]["source"], sources[existing_index],
                )
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
        seen_ids[evidence_id] = len(sources) - 1
        per_path[path] = per_path.get(path, 0) + 1
        selected_required_ids.update(required_ids)
        selected_host_lookup = selected_host_lookup or bool(host_ids)
        if len(sources) >= MAX_DOCS_SOURCES:
            break
        if (
            required_query_id_set
            and required_query_id_set.issubset(selected_required_ids)
            and (not host_query_ids or selected_host_lookup)
        ):
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
    decision = context_selection_decision(sources, public_query_ids)
    payload = _payload(sources, decision=decision, query_plan=query_plan)
    snapshot = {
        source["evidence_id"]: _snapshot_entry(
            snapshot[source["evidence_id"]]["source"], source,
        )
        for source in payload["sources"]
    }
    return payload, snapshot


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


def _normalized_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").removeprefix("./").casefold()


def _public_query_ids(query_plan: dict[str, Any]) -> tuple[str, ...]:
    visible_origins = {"original", "host_lookup", "canonical_intent", "exact_anchor", "exact_path"}
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
    if len(value) <= limit:
        return value, leading, leading + len(value)
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
    for distance in range(1, len(spans)):
        for index in (best_index - distance, best_index + distance):
            if index < 0 or index >= len(spans):
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


def _include_complete_code_fence(
    text: str, start: int, end: int, *, limit: int,
) -> tuple[int, int]:
    fences = [match.start() for match in re.finditer(r"^\s*```", text, re.M)]
    for index in range(0, len(fences) - 1, 2):
        fence_start = fences[index]
        closing_line_end = text.find("\n", fences[index + 1])
        fence_end = len(text) if closing_line_end < 0 else closing_line_end
        if start < fence_end and end > fence_start:
            expanded_start = min(start, fence_start)
            expanded_end = max(end, fence_end)
            if expanded_end - expanded_start <= limit:
                return expanded_start, expanded_end
            # A bounded payload must not expose a syntactically broken fence.
            before = text.rfind("\n\n", 0, fence_start)
            safe_start = 0 if before < 0 else before + 2
            if fence_start - safe_start <= limit and fence_start > safe_start:
                return safe_start, fence_start
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
    remaining = list(candidates)
    ordered: list[Any] = []
    covered: set[str] = set()
    while remaining:
        best_index = max(
            range(len(remaining)),
            key=lambda index: (
                len(
                    qualified_query_ids((remaining[index],))
                    & required_query_ids
                    - covered
                ),
                _context_rank(
                    remaining[index], query_text, required_query_ids,
                    assigned_evidence_ids,
                ),
            ),
        )
        selected = remaining.pop(best_index)
        ordered.append(selected)
        covered.update(qualified_query_ids((selected,)) & required_query_ids)
    return ordered


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
        retrieved = query_id in covered_query_ids
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
                "_assigned_requirement_ids",
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
