"""Candidate preferences for bounded documentation projection; never proof."""
from __future__ import annotations

import re
import math
from typing import Any
from .context_selection import component_witnesses, qualified_query_ids
from docmancer.docs.domain.context_windows import _query_terms
from docmancer.docs.domain.project_doc_ranking import project_question_lane, project_source_lane, condition_lead_priority
from docmancer.docs.domain.answer_units import extract_answer_units, _NEGATION_RE
from docmancer.docs.domain.normative_language import _FORBIDDEN_RE
from docmancer.docs.domain.evidence_qualification import _visible_term_present


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
    supplemental_query_ids: set[str] | None = None,
    assigned_evidence_ids: set[str] | None = None,
    bound_assigned_evidence_ids: set[str] | None = None,
    exact_query_ids: set[str] | None = None,
    host_query_ids: set[str] | None = None,
    obligations: tuple[Any, ...] = (), missing_component_ids: set[str] | None = None,
) -> list[Any]:
    # Audited directions break public-coverage ties; they are not public queries.
    # Exact-anchor lanes are identity-sensitive: when two candidates both
    # visibly qualify, preserve the upstream assigned witness before rewarding
    # extra lexical mentions. General host/original lanes keep action and
    # relevance ranking first so assignments cannot crowd out procedural facts.
    # Count a source once even when it supplies many alternative windows.
    # Rare question terms distinguish the requested procedure from generic
    # instructions that happen to match the host's paraphrase.
    original_terms = (_query_terms((query_text.get('query-original', ''),))
                      if required_query_ids & (host_query_ids or set()) else set())
    term_sources: dict[str, set[str]] = {term: set() for term in original_terms}
    source_paths: set[str] = set()
    for candidate in candidates:
        path = str(candidate.get('path_or_url') or candidate.get('path') or candidate.get('source') or '')
        source_paths.add(path)
        body = str(candidate.get('snippet') or candidate.get('content') or '').casefold()
        for term in original_terms:
            if _visible_term_present(term, body, exact=False):
                term_sources[term].add(path)
    term_weights = {term: math.log1p(len(source_paths) / (1 + len(paths)))
                    for term, paths in term_sources.items()}

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
        # A catalog-role preference may break ties between candidates serving an
        # outstanding public direction. Once all public directions are covered,
        # it must not outrank validated supplemental lineage and spend the final
        # source slot on a merely topical document.
        role_tiebreak = rank[4] if qualified_ids & required_query_ids else 0.0
        # A host paraphrase can match an incidental procedure very well.
        # Among candidates serving the same outstanding direction, preserve
        # the original question's body terms before topical/authority ties.
        original_body_overlap = sum(
            weight for term, weight in term_weights.items()
            if _visible_term_present(term, str(source.get('snippet') or source.get('content') or '').casefold(), exact=False)
        ) if qualified_ids & required_query_ids and not exact_count else 0
        return (
            int(exact_count > 0),
            condition_lead_priority(query_text.get("query-original", ""), str(source.get("snippet") or "")),
            component_count,
            bound_assignment,
            rank[3] if exact_count else 0.0,
            exact_count,
            len(_fully_matched_query_ids((source,)) & required_query_ids),
            role_tiebreak,
            len(qualified_ids & required_query_ids),
            original_body_overlap,
            len(qualified_ids & (supplemental_query_ids or set())),
            rank[0],
            match_ratio,
            len(qualified_ids & (canonical_query_ids or set())),
            rank[1:3] + rank[5:],
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
