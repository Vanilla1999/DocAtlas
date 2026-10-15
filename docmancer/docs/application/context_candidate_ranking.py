"""Lexical/structural preferences for bounded projection; never proof."""
from __future__ import annotations

import math
from typing import Any
from .context_selection import attributable_query_ids, qualified_query_ids
from docmancer.docs.domain.context_windows import _query_terms
from docmancer.docs.domain.project_doc_ranking import technical_anchors
from docmancer.docs.domain.evidence_qualification import _visible_term_present, qualify_evidence


def _prefer_missing_baseline_candidate(
    candidates: list[Any], selected: list[dict[str, Any]], public_query_ids: set[str],
    host_query_ids: set[str], canonical_query_ids: set[str],
) -> None:
    """Protect baseline evidence without starving independent host lookups."""
    if not host_query_ids:
        return
    selected_ids = attributable_query_ids(selected)
    missing_host = host_query_ids - selected_ids
    preserve_lookup_diversity = len(host_query_ids) > 1 and bool(missing_host)

    def protects(candidate: Any, wanted_ids: set[str]) -> bool:
        candidate_ids = attributable_query_ids((candidate,))
        return bool(candidate_ids & wanted_ids) and (
            not preserve_lookup_diversity or bool(candidate_ids & missing_host)
        )

    missing_public = (public_query_ids - host_query_ids) - selected_ids
    protected = next((i for i, candidate in enumerate(candidates)
                      if protects(candidate, missing_public)), None)
    if protected is None:
        missing_canonical = canonical_query_ids - selected_ids
        protected = next((i for i, candidate in enumerate(candidates)
                          if protects(candidate, missing_canonical)
                          and not (qualified_query_ids((candidate,)) & host_query_ids)), None)
    if protected not in (None, 0):
        candidates.insert(0, candidates.pop(protected))


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
        and trace.get("admission_only") is not True
    ]
    lexical = sum(float((matches.get(key) or {}).get("lexical_score") or 0.0)
                  for key in qualified)
    required = [key for key in qualified if key in required_query_ids]
    required_lexical = sum(float((matches.get(key) or {}).get("lexical_score") or 0.0)
                           for key in required)
    authority_score = 2.0 if str(source.get("authority") or "supporting").casefold() == "source_of_truth" else 1.0
    catalog_role = str(source.get("catalog_role") or "")
    preferred_role_score = float(sum(
        catalog_role in set((matches.get(key) or {}).get("preferred_catalog_roles") or ())
        for key in qualified
    ))
    identity_text = " ".join(str(source.get(key) or "") for key in (
        "path", "source", "heading_path", "title", "catalog_description", "description",
        "content", "display_text", "snippet",
    )).casefold()[:2_000]
    identity_score = float(sum(
        _visible_term_present(term, identity_text, exact=False)
        for term in _query_terms((query_text.get("query-original", ""),))
    ))
    source_ids = {str(source[key]) for key in ("stable_id", "stable_chunk_id", "evidence_id")
                  if source.get(key)}
    assigned_score = float(bool(source_ids & (assigned_evidence_ids or set())))
    # Preserve positional consumers; removed action and NL lane slots are inert.
    return (
        0.0, 0.0, float(len(required)), assigned_score, preferred_role_score,
        authority_score, identity_score, float("query-original" in qualified),
        required_lexical, float(len(qualified) - len(required)), lexical,
        float((source.get("project_ranking") or {}).get("final_score") or 0.0),
        float(source.get("score") or 0.0),
    )


def _facet_aware_candidates(
    candidates: list[Any], *, query_text: dict[str, str], required_query_ids: set[str],
    canonical_query_ids: set[str] | None = None,
    supplemental_query_ids: set[str] | None = None,
    assigned_evidence_ids: set[str] | None = None,
    bound_assigned_evidence_ids: set[str] | None = None,
    exact_query_ids: set[str] | None = None,
    host_query_ids: set[str] | None = None,
    fallback_query_ids: set[str] | None = None,
    need_query_ids: set[str] | None = None,
    obligations: tuple[Any, ...] = (), missing_component_ids: set[str] | None = None,
    component_scope_complete: bool = True,
) -> list[Any]:
    # Count each source once for lexical rarity, including alternative windows.
    original_terms = (_query_terms((query_text.get("query-original", ""),))
                      if required_query_ids & (host_query_ids or set()) else set())
    term_sources: dict[str, set[str]] = {term: set() for term in original_terms}
    source_paths: set[str] = set()
    for candidate in candidates:
        path = str(candidate.get("path_or_url") or candidate.get("path") or candidate.get("source") or "")
        source_paths.add(path)
        body = str(candidate.get("snippet") or candidate.get("content") or "").casefold()
        for term in original_terms:
            if _visible_term_present(term, body, exact=False):
                term_sources[term].add(path)
    term_weights = {term: math.log1p(len(source_paths) / (1 + len(paths)))
                    for term, paths in term_sources.items()}

    def candidate_key(source: Any) -> tuple[Any, ...]:
        qualified_ids = attributable_query_ids((source,))
        exact_count = len(qualified_ids & (exact_query_ids or set()))
        need_count = len(qualified_ids & (need_query_ids or set()))
        # Semantic component witnesses depend on proposition certification and
        # are not a ranking signal. Keep their historical tuple slot inert.
        component_count = 0
        rank = _context_rank(source, query_text, required_query_ids, assigned_evidence_ids)
        identity = {**source.get("_qualification_candidate", {}), **source}
        source_ids = {str(identity[key]) for key in ("stable_id", "stable_chunk_id", "evidence_id")
                      if identity.get(key)}
        bound_assignment = int(bool(source_ids & (bound_assigned_evidence_ids or set())))
        traces = source.get("retrieval_query_matches") or {}
        eligible_traces = {
            key: trace for key, trace in traces.items()
            if isinstance(trace, dict) and trace.get("qualified") is True
            and trace.get("admission_only") is not True
        }
        match_ratio = sum(float(trace.get("match_ratio") or 0.0)
                          for key, trace in eligible_traces.items() if key in required_query_ids)
        role_tiebreak = rank[4] if qualified_ids & required_query_ids else 0.0
        body_text = str(source.get("snippet") or source.get("content") or "")
        continuation_score = int(any(
            trace.get("qualification_route") in {"same_atom_continuation", "same_list_item_continuation"}
            for trace in eligible_traces.values()
        ))
        canonical_match_ratio = max((float(trace.get("match_ratio") or 0.0)
            for key, trace in eligible_traces.items() if key in (canonical_query_ids or set())), default=0.0)
        relation_group_traces = [trace for key, trace in eligible_traces.items()
            if str(key).startswith("query-relation-") and key in (canonical_query_ids or set())]
        relation_group_count = len(relation_group_traces)
        relation_group_match_ratio = max((float(trace.get("match_ratio") or 0.0)
            for trace in relation_group_traces), default=0.0)
        relation_group_lexical = max((float(trace.get("lexical_score") or 0.0)
            for trace in relation_group_traces), default=0.0)
        direct_required_traces = [trace for key, trace in eligible_traces.items()
            if key in required_query_ids and trace.get("query_origin") == "host_lookup"
            and not trace.get("derived_from_query_id")]
        direct_required_count = len(direct_required_traces)
        direct_required_lexical = max((float(trace.get("lexical_score") or 0.0)
            for trace in direct_required_traces), default=0.0)
        original_body_overlap = sum(weight for term, weight in term_weights.items()
            if _visible_term_present(term, body_text.casefold(), exact=False)
        ) if qualified_ids & required_query_ids and not exact_count else 0
        # Keep all tuple dimensions, notably the fallback prefix key[:9]. No
        # removed semantic preference is replaced with manufactured coverage.
        return (
            need_count, 0.0, 0, 0.0, (0.0,) * 9, 0,
            relation_group_count, relation_group_match_ratio, relation_group_lexical,
            0, 0,
            (len(_fully_matched_query_ids((source,)) & required_query_ids & (host_query_ids or set()))
             if len(host_query_ids or ()) > 1 and not (component_scope_complete and obligations) else 0),
            role_tiebreak, direct_required_count, direct_required_lexical, (0.0,) * 9,
            continuation_score, int(exact_count > 0), component_count, bound_assignment,
            rank[3] if exact_count else 0.0, exact_count,
            len(_fully_matched_query_ids((source,)) & required_query_ids),
            len(qualified_ids & required_query_ids), (0, 0, 0, 0), original_body_overlap,
            len(qualified_ids & (supplemental_query_ids or set())), rank[0], match_ratio,
            canonical_match_ratio, int(bool(qualified_ids & (canonical_query_ids or set()))),
            rank[1:3] + rank[5:],
        )

    ranked = sorted(candidates, key=candidate_key, reverse=True)
    if not fallback_query_ids:
        return ranked
    # Within a source and equal structural prefix, prefer a strict superset of
    # original-question body matches. This never creates qualified attribution.
    facts = {}
    for source in ranked:
        ids = attributable_query_ids((source,))
        if ids & required_query_ids or not ids & fallback_query_ids:
            continue
        body = str(source.get("snippet") or source.get("content") or "")
        trace = qualify_evidence({"query_text": query_text.get("query-original", "")},
            query_id="query-original", visible_text=body, evidence_text=body).trace
        facts[id(source)] = (
            str(source.get("path_or_url") or source.get("path") or source.get("source") or ""),
            candidate_key(source)[:9], set(trace.get("body_matched_terms") or ()),
        )
    for index in range(len(ranked)):
        best = index
        for other in range(index + 1, len(ranked)):
            left, right = facts.get(id(ranked[other])), facts.get(id(ranked[best]))
            if left and right and left[:2] == right[:2] and right[2] < left[2]:
                best = other
        ranked.insert(index, ranked.pop(best))
    return ranked


def _relation_request_priority(question: str, snippet: str) -> tuple[float, ...]:
    """Compatibility shape only; no NL relation interpretation or boosts."""
    return (0.0,) * 9


def _fully_matched_query_ids(sources: Any) -> set[str]:
    """Read eligible literal match attribution, never semantic completeness."""
    result: set[str] = set()
    for source in sources:
        for query_id, trace in (source.get("retrieval_query_matches") or {}).items():
            if (not isinstance(trace, dict) or trace.get("qualified") is not True
                    or trace.get("admission_only") is True):
                continue
            if trace.get("mode") == "exact_path":
                result.add(query_id)
            elif trace.get("match_ratio") == 1.0 and (
                trace.get("coverage_kind") != "derived"
                or "direct" in set(trace.get("coverage_kinds") or ())
            ):
                result.add(query_id)
    return result


def _condition_body_priority(question: str, snippet: str) -> int:
    """Compatibility slot; condition wording receives no special ranking."""
    return 0


def _comparison_action_priority(question: str, snippet: str) -> int:
    """Compatibility slot; action wording receives no special ranking."""
    return 0
