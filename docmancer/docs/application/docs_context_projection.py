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


def project_docs_context(
    *, retrieval: dict[str, Any], max_tokens: int = DOCS_CONTEXT_MAX_TOKENS,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Project trusted retrieval as context without claiming answer support."""

    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, int] = {}
    per_path: dict[str, int] = {}
    query_plan = retrieval.get("documentation_query_plan") or {}
    query_text = {
        str(item.get("query_id") or ""): str(item.get("text") or "")
        for item in query_plan.get("queries") or ()
        if isinstance(item, dict)
    }
    required_query_ids = _required_query_ids(query_plan)
    required_query_id_set = set(required_query_ids)
    candidates = sorted(
        retrieval.get("context_pack") or (),
        key=lambda item: _context_rank(item, query_text, required_query_id_set),
        reverse=True,
    )
    for original in candidates:
        if not isinstance(original, dict):
            continue
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
        qualified_ids = qualified_query_ids((original,))
        if not qualified_ids:
            continue
        raw_snippet = str(
            original.get("code") or original.get("snippet") or original.get("content")
            or original.get("display_text") or ""
        )
        required_matches = tuple(
            query_text.get(query_id, "")
            for query_id in qualified_ids if query_id in required_query_id_set
        )
        supplemental_matches = tuple(
            str(((original.get("retrieval_query_matches") or {}).get(query_id) or {}).get("query_text") or "")
            for query_id in qualified_ids if query_id.startswith("query-supplemental-")
        )
        focused_snippet = _focused_snippet(
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
        normalized.update({
            "project_identity": project_identity,
            "line_start": original.get("line_start"),
            "line_end": original.get("line_end"),
            "authority": str(original.get("authority") or "supporting"),
            "scope": str(original.get("doc_scope") or "project"),
            "retrieval_query_ids": list(original.get("retrieval_query_ids") or ()),
            "retrieval_query_matches": dict(original.get("retrieval_query_matches") or {}),
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
            candidate_decision = context_selection_decision(
                candidate_sources, required_query_ids,
            )
            if estimate_projection_tokens(
                    _payload(candidate_sources, decision=candidate_decision, query_plan=query_plan)
            ) <= max_tokens:
                sources = candidate_sources
                snapshot[evidence_id] = _snapshot_entry(
                    snapshot[evidence_id]["source"], sources[existing_index],
                )
            continue
        candidate_sources = [*sources, normalized]
        candidate_decision = context_selection_decision(
            candidate_sources, required_query_ids,
        )
        candidate_payload = _payload(
            candidate_sources, decision=candidate_decision, query_plan=query_plan,
        )
        if estimate_projection_tokens(candidate_payload) > max_tokens:
            continue
        sources = candidate_sources
        snapshot[evidence_id] = _snapshot_entry(original, normalized)
        seen_ids[evidence_id] = len(sources) - 1
        per_path[path] = per_path.get(path, 0) + 1
        if len(sources) >= MAX_DOCS_SOURCES:
            break

    if not sources:
        return project_insufficient(
            kind="docs_context",
            missing=["No safe, current, project-scoped documentation context was retrieved."],
            recommended_next_action=None,
            max_tokens=min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens),
        ), {}
    decision = context_selection_decision(sources, required_query_ids)
    return _payload(sources, decision=decision, query_plan=query_plan), snapshot


def _required_query_ids(query_plan: dict[str, Any]) -> tuple[str, ...]:
    explicit = query_plan.get("required_query_ids")
    values = explicit if isinstance(explicit, list) else query_plan.get("query_ids") or ()
    return tuple(str(value) for value in values if value)


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


def _focused_snippet(text: str, queries: tuple[str, ...], *, limit: int = 420) -> str:
    value = text.strip()
    if len(value) <= limit:
        return value
    terms = _query_terms(queries)
    spans = [span.strip() for span in re.split(r"(?<=[.!?])\s+|\n{2,}", value) if span.strip()]
    if not spans or not terms:
        return value[:limit].rstrip()
    best_index = max(
        range(len(spans)),
        key=lambda index: sum(term in spans[index].casefold() for term in terms),
    )
    start = best_index
    end = best_index
    selected = spans[best_index]
    for distance in range(1, len(spans)):
        for index in (best_index - distance, best_index + distance):
            if index < 0 or index >= len(spans):
                continue
            candidate_start = min(start, index)
            candidate_end = max(end, index)
            candidate = " ".join(spans[candidate_start:candidate_end + 1])
            if len(candidate) <= limit:
                selected = candidate
                start = candidate_start
                end = candidate_end
        if len(selected) >= limit * 0.7:
            break
    return selected[:limit].rstrip()


def _context_rank(
    source: Any, query_text: dict[str, str], required_query_ids: set[str],
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
    path = str(source.get("path") or source.get("source") or "").casefold()
    question = " ".join(query_text.values()).casefold()
    plan_penalty = 0.0
    evaluation_intent = bool(re.search(
        r"\b(?:eval(?:uation)?|benchmarks?|protocols?|metrics?|quality gates?|"
        r"test results?|оценк\w*|бенчмарк\w*|протокол\w*|метрик\w*)\b",
        question,
        re.I,
    ))
    planning_intent = bool(re.search(
        r"\b(?:plans?|roadmap|milestones?|task\s+\d+|task status|"
        r"план\w*|дорожн\w+\s+карт\w*|статус\w*\s+задач\w*)\b",
        question,
        re.I,
    ))
    if path.startswith("eval/") and not evaluation_intent:
        plan_penalty -= 3.0
    if ("/.hermes/plans/" in f"/{path}" or "roadmap" in path) and not re.search(
        r"\b(?:histor|history)\b", question,
    ):
        if not planning_intent:
            plan_penalty -= 3.0
    reference_score = 1.0 if path.startswith(("docs/", "wiki/")) else 0.0
    return (
        float(len(required)), required_lexical,
        authority_score + reference_score + plan_penalty,
        float(len(qualified) - len(required)), lexical,
        float((source.get("project_ranking") or {}).get("final_score") or 0.0),
        float(source.get("score") or 0.0),
    )


def _payload(
    sources: list[dict[str, Any]], *, decision: Any = None,
    query_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_queries = {
        str(item.get("query_id") or ""): item
        for item in (query_plan or {}).get("queries") or ()
        if isinstance(item, dict)
    }
    missing_facets = [
        {
            "query_id": query_id,
            "text": str((plan_queries.get(query_id) or {}).get("text") or query_id),
            "origin": str((plan_queries.get(query_id) or {}).get("origin") or "unknown"),
        }
        for query_id in (decision.missing_query_ids if decision else ())
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
        "facet_coverage": "unverified",
        "covered_query_ids": list(decision.covered_query_ids) if decision else [],
        "missing_query_ids": list(decision.missing_query_ids) if decision else [],
        "missing_facets": missing_facets,
        "sources": sources,
        "edit_ready": False,
        "investigation_allowed": True,
        "safe_to_answer": False,
        "safe_to_answer_from_sources": True,
        "required_next_step": "answer_from_returned_context",
        "agent_instruction": (
            "Answer only claims directly grounded in the returned sources, cite their paths, "
            "and do not claim that the context is complete. Never use this retrieval-only "
            "result to authorize an edit."
        ),
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    return payload
