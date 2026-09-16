"""Candidate preferences for bounded documentation projection; never proof."""
from __future__ import annotations

import re
import math
from typing import Any
from .context_selection import component_witnesses, qualified_query_ids
from docmancer.docs.domain.context_windows import _query_terms
from docmancer.docs.domain.project_doc_ranking import (
    condition_lead_priority, project_question_lane, project_source_lane, technical_anchors,
)
from docmancer.docs.domain.answer_units import extract_answer_units, _NEGATION_RE
from docmancer.docs.domain.normative_language import _FORBIDDEN_RE
from docmancer.docs.domain.evidence_qualification import _visible_term_present, qualify_evidence
from docmancer.docs.domain.question_semantic_frames import match_comparison_frame
from docmancer.docs.domain.context_request_preferences import (
    direct_evidence_preference, recognized_request_parts, recognized_request_satisfied,
)


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
        _visible_term_present(term, identity_text, exact=False)
        for term in _query_terms((original_question,))
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
    fallback_query_ids: set[str] | None = None,
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
        body_text = str(source.get('snippet') or source.get('content') or '')
        relation_preference = _relation_request_priority(
            query_text.get("query-original", ""), body_text,
        )
        continuation_score = int(any(
            isinstance(trace, dict)
            and trace.get("qualified") is True
            and trace.get("qualification_route") in {"same_atom_continuation", "same_list_item_continuation"}
            for trace in (source.get("retrieval_query_matches") or {}).values()
        ))
        # Optional canonical aliases are search hypotheses, not votes. When two
        # candidates serve the same optional direction, prefer the one with the
        # stronger visible qualification before generic source-lane priors.
        # This does not create public coverage or reward the number of aliases.
        canonical_match_ratio = max((
            float(trace.get("match_ratio") or 0.0)
            for key, trace in (source.get("retrieval_query_matches") or {}).items()
            if key in (canonical_query_ids or set())
            and isinstance(trace, dict) and trace.get("qualified") is True
        ), default=0.0)
        relation_group_traces = [
            trace
            for key, trace in (source.get("retrieval_query_matches") or {}).items()
            if str(key).startswith("query-relation-")
            and key in (canonical_query_ids or set())
            and isinstance(trace, dict) and trace.get("qualified") is True
        ]
        # Relation groups are compact probes made only from the user's own
        # comparison sides/axes or condition states. They are stronger visible
        # relevance evidence than a generic topical hit against the full
        # question, but remain retrieval-only and never derive public coverage.
        relation_group_count = len(relation_group_traces)
        relation_group_match_ratio = max((
            float(trace.get("match_ratio") or 0.0) for trace in relation_group_traces
        ), default=0.0)
        relation_group_lexical = max((
            float(trace.get("lexical_score") or 0.0) for trace in relation_group_traces
        ), default=0.0)
        comparison_relation_marker = 0
        if relation_group_traces and re.search(
            r"\b(?:differ|difference|compare|versus|vs\.?)\b",
            query_text.get("query-original", ""), re.I,
        ):
            relation_surface = " ".join(str(identity.get(key) or "") for key in (
                "heading_path", "title", "snippet", "content",
            ))
            comparison_relation_marker = int(bool(re.search(
                r"\b(?:separate|different|differ|distinct|versus|vs\.?|rather than|not the same)\b",
                relation_surface, re.I,
            )))
        direct_required_traces = [
            trace
            for key, trace in (source.get("retrieval_query_matches") or {}).items()
            if key in required_query_ids
            and isinstance(trace, dict)
            and trace.get("qualified") is True
            and trace.get("query_origin") == "host_lookup"
            and not trace.get("derived_from_query_id")
        ]
        # A domain-owned rewrite may legitimately derive retrieval coverage for
        # a host facet, but it is still a search hypothesis. When the direct
        # host lookup itself produced a qualified candidate, keep that evidence
        # ahead of a rewrite-derived candidate for the same missing facet.
        # This changes selection order only; it does not create coverage/proof.
        direct_required_count = len(direct_required_traces)
        direct_required_lexical = max((
            float(trace.get("lexical_score") or 0.0)
            for trace in direct_required_traces
        ), default=0.0)
        original_body_overlap = sum(
            weight for term, weight in term_weights.items()
            if _visible_term_present(term, body_text.casefold(), exact=False)
        ) if qualified_ids & required_query_ids and not exact_count else 0
        request_preference = (
            direct_evidence_preference(query_text.get("query-original", ""), body_text)
            if qualified_ids & required_query_ids else (0, 0, 0, 0)
        )
        required_relation_preference = max((
            _relation_request_priority(query_text.get(key, ""), body_text)
            for key in qualified_ids & required_query_ids
        ), default=(0.0,) * 8)
        host_condition_priority = max((
            _condition_body_priority(query_text.get(key, ""), body_text)
            for key in qualified_ids & required_query_ids
        ), default=0)
        comparison_action_priority = max((
            _comparison_action_priority(query_text.get(key, ""), body_text)
            for key in qualified_ids & required_query_ids
        ), default=0)
        return (
            condition_lead_priority(query_text.get("query-original", ""), str(source.get("snippet") or "")),
            required_relation_preference,
            comparison_relation_marker,
            relation_group_count,
            relation_group_match_ratio,
            relation_group_lexical,
            host_condition_priority,
            comparison_action_priority,
            role_tiebreak,
            direct_required_count,
            direct_required_lexical,
            relation_preference,
            continuation_score,
            int(exact_count > 0),
            component_count,
            bound_assignment,
            rank[3] if exact_count else 0.0,
            exact_count,
            len(_fully_matched_query_ids((source,)) & required_query_ids),
            len(qualified_ids & required_query_ids),
            request_preference,
            original_body_overlap,
            len(qualified_ids & (supplemental_query_ids or set())),
            rank[0],
            match_ratio,
            canonical_match_ratio,
            int(bool(qualified_ids & (canonical_query_ids or set()))),
            rank[1:3] + rank[5:],
        )

    ranked = sorted(candidates, key=candidate_key, reverse=True)
    if not fallback_query_ids:
        return ranked
    # Partial context has no qualified public direction to break a tie. Within
    # one source, prefer a strict superset of original-question body matches;
    # a heading or extra discovery hint must not consume its bounded slot.
    # This changes order only, never qualification or certified coverage.
    facts = {}
    for source in ranked:
        ids = qualified_query_ids((source,))
        if ids & required_query_ids or not ids & fallback_query_ids:
            continue
        body = str(source.get('snippet') or source.get('content') or '')
        trace = qualify_evidence({'query_text': query_text.get('query-original', '')},
            query_id='query-original', visible_text=body, evidence_text=body).trace
        facts[id(source)] = (
            str(source.get('path_or_url') or source.get('path') or source.get('source') or ''),
            candidate_key(source)[:9], set(trace.get('body_matched_terms') or ()),
        )
    for index in range(len(ranked)):
        best = index
        for other in range(index + 1, len(ranked)):
            left, right = facts.get(id(ranked[other])), facts.get(id(ranked[best]))
            if left and right and left[:2] == right[:2] and right[2] < left[2]:
                best = other
        ranked.insert(index, ranked.pop(best))
    return ranked


_COMPOUND_INTERROGATIVE_RE = re.compile(
    r"\b(?:which|what|how|when)\b.+?\b(?:and|or)\s+(?:which|what|how|when)\b",
    re.I,
)
_LIST_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_-]*(?:\s*,\s*[A-Za-z][A-Za-z0-9_-]*)+"
    r"\s*,?\s*(?:and|or)\s+[A-Za-z][A-Za-z0-9_-]*)\b",
    re.I,
)


def _relation_request_priority(question: str, snippet: str) -> tuple[float, ...]:
    """Prefer visible relation-bearing text without turning it into proof.

    Exact identifiers and aliases are retrieval aids.  For an explicitly
    conditional or multi-part question they must not crowd out an already
    qualified span that visibly preserves the user's condition/alternatives.
    This is a deterministic ordering hint only; it neither qualifies evidence
    nor changes component coverage or ``checked`` semantics.
    """
    if not question or not snippet:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    # Narrow request shapes (code/signature/default-timeout/origin comparison)
    # already have a stronger dedicated selector. Do not let this generic
    # relation hint compete with those explicit parts.
    if recognized_request_parts(question):
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    body = snippet.casefold()

    # Preserve an explicitly requested retrieval->proof relation.  A span that
    # visibly says whether a retrieval/search hit is proof is stronger than one
    # that merely contains both topical words in unrelated clauses.  Either
    # polarity is accepted; this is relation visibility, not answer injection.
    proof_relation_score = 0.0
    if (
        re.search(r"\b(?:retriev\w*|search|passage|text|hit)\b", question, re.I)
        and re.search(r"\b(?:proof|certif\w*|sufficien\w*)\b", question, re.I)
    ):
        if re.search(
            r"\b(?:retriev\w*(?:\s+\w+){0,3}|search(?:\s+\w+){0,3}|hit|passage)\b"
            r"[^.!?\n]{0,80}\b(?:is|are|does|alone|not|never|sufficien\w*)\b"
            r"[^.!?\n]{0,40}\b(?:proof|certif\w*)\b",
            body, re.I,
        ):
            proof_relation_score = 1.0

    # A question asking how a system decides/selects/resolves something needs
    # the mechanism span, not merely a taxonomy of possible states.  The
    # preference is relation-shaped and does not encode a particular answer.
    decision_mechanism_score = 0.0
    decision_question = bool(
        re.search(r"\bhow\b[^?]{0,120}\b(?:decid|choos|select|resolv)\w*\b", question, re.I)
        or re.search(r"\bwhat\s+decision\b[^?]{0,120}\b(?:make|mak|take|use)\w*\b", question, re.I)
    )
    if decision_question and re.search(
        r"\b(?:decision|decid\w*|choos\w*|select\w*|resolv\w*)\b", body, re.I,
    ):
        decision_mechanism_score = 1.0

    # An action question about an explicit insufficient-evidence state needs a
    # procedural span, not merely a definition saying that the state exists.
    # The signal is intentionally generic: it rewards action language but does
    # not encode which recovery action is correct.
    recovery_action_score = 0.0
    action_question = bool(
        re.search(r"\bwhat\s+should\b[^?]{0,100}\bdo\b", question, re.I)
        or re.search(r"\bчто\s+долж\w*\s+(?:сдел|предприн)\w*", question, re.I)
    )
    insufficient_state = bool(
        re.search(r"\binsufficient[_ ]evidence\b", question, re.I)
        or re.search(r"\bнедостаточно\s+(?:доказательств|данных)\b", question, re.I)
    )
    if action_question and insufficient_state and "insufficient_evidence" in body:
        if re.search(
            r"\b(?:follow|continue|stop|retry|do\s+not|must\s+not|"
            r"should\s+not|ask|call|use)\b",
            body, re.I,
        ):
            recovery_action_score = 1.0

    # Once a broad permission rule has been selected, a complementary caveat
    # (approval/confirmation) is more useful than another example of the same
    # returned-action path.  Requiring the requested technical subject keeps
    # unrelated safety prose from receiving this preference.
    permission_caveat_score = 0.0
    if re.match(
        r"^\s*(?:when\b.*\b(?:allowed|permitted)\b|"
        r"under (?:what|which) conditions\b|"
        r"когда\b.*(?:разреш|можно|допуст)|при каких условиях\b)",
        question, re.I,
    ):
        anchors = technical_anchors(question)
        if len(anchors) == 1 and _visible_term_present(anchors[0], body, exact=True):
            if re.search(
                r"\b(?:approval|confirmation|opt[ -]?in|ask(?:s|ed)?\s+(?:the\s+)?user|"
                r"user\s+(?:approval|confirmation))\b",
                body, re.I,
            ):
                permission_caveat_score = 1.0

    # Preserve the state named in a conditional question in either common
    # surface order: "what happens if X is stale" and "if X is stale, what
    # happens ...".  The state is user text, never an inferred outcome.
    condition = None
    for pattern in (
        r"\bwhat\s+happens\s+(?:when|if)\s+(.+?)(?:[?.]|$)",
        r"^\s*(?:when|if)\s+(.+?)[,;]\s*what\s+happens\b",
    ):
        match = re.search(pattern, question, re.I)
        if match is not None:
            condition = match.group(1)
            break
    state_score = 0.0
    if condition:
        state_match = re.search(
            r"\b(?:is|are|was|were|becomes?|gets?)\s+([A-Za-z][A-Za-z0-9_-]{2,})\b",
            condition,
            re.I,
        )
        if state_match and _visible_term_present(
            state_match.group(1), body, exact=False,
        ):
            state_score = 1.0

    # Questions that explicitly enumerate alternatives (exact / declared-only /
    # unbound; new / changed / stale / deleted) should prefer a single visible
    # span retaining more of those user-named alternatives.
    alternative_score = 0.0
    list_match = _LIST_RE.search(question)
    if list_match is not None:
        alternatives = tuple(dict.fromkeys(
            token.casefold()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", list_match.group(1))
            if token.casefold() not in {"and", "or"}
        ))
        if len(alternatives) >= 3:
            alternative_score = float(sum(
                _visible_term_present(term, body, exact=False)
                for term in alternatives
            )) / len(alternatives)

    # Repeated interrogatives form explicit sibling clauses.  Reward balanced
    # coverage (the weakest clause) rather than a topical span that saturates one
    # side and omits the other.  This remains lexical and source-local.
    clause_score = 0.0
    clause_average = 0.0
    if _COMPOUND_INTERROGATIVE_RE.search(question):
        clauses = tuple(
            part.strip(" ,;?")
            for part in re.split(
                r"\s*,?\s+(?:and|or)\s+(?=(?:which|what|how|when)\b)",
                question,
                flags=re.I,
            )
            if part.strip(" ,;?")
        )
        ratios: list[float] = []
        for clause in clauses:
            terms = _query_terms((clause,))
            if not terms:
                continue
            ratios.append(sum(
                _visible_term_present(term, body, exact=False) for term in terms
            ) / len(terms))
        if len(ratios) >= 2:
            clause_score = min(ratios)
            clause_average = sum(ratios) / len(ratios)
    return (
        proof_relation_score, decision_mechanism_score, recovery_action_score, permission_caveat_score,
        state_score, alternative_score, clause_score, clause_average,
    )


def _fully_matched_query_ids(sources: Any) -> set[str]:
    # Partial lexical attribution must not crowd out a complete visible match.
    # Recognized request shapes may stop *selection* once all of their literal
    # requested parts survive in one visible candidate. This remains a ranking
    # heuristic; it is never a public answer-completeness/``checked`` proof.
    result: set[str] = set()
    for source in sources:
        body = str(source.get("snippet") or source.get("content") or "")
        for query_id, trace in (source.get("retrieval_query_matches") or {}).items():
            if not isinstance(trace, dict) or trace.get("qualified") is not True:
                continue
            question = str(trace.get("query_text") or "")
            if recognized_request_parts(question):
                # Matching every lexical term cannot close a multi-part request
                # while one of its explicit requested parts is still absent.
                if recognized_request_satisfied(question, body):
                    result.add(query_id)
            elif trace.get("mode") == "exact_path":
                result.add(query_id)
            elif (
                trace.get("match_ratio") == 1.0
                and (
                    trace.get("coverage_kind") != "derived"
                    or "direct" in set(trace.get("coverage_kinds") or ())
                )
            ):
                # A rewrite may derive retrieval coverage for its parent, but
                # lexical completeness against the rewrite is not evidence that
                # the original host wording is visibly complete. Keep the facet
                # open for a direct/complementary witness.
                result.add(query_id)
    return result


def _condition_body_priority(question: str, snippet: str) -> int:
    """Keep the stated triggering event ahead of a merely topical procedure.

    This bounded preference does not qualify a source or infer an outcome.
    Temporal ordering stays in the original question and visible evidence.
    """
    condition = re.fullmatch(r"\s*what\s+happens\s+(?:when|if)\s+(.+?)[?]?\s*", question, re.I)
    if not condition:
        return 0
    event = re.split(r"\b(?:before|after|while)\b", condition[1], maxsplit=1, flags=re.I)[0]
    terms = _query_terms((event,))
    trace = qualify_evidence(
        {"query_terms": sorted(terms)}, query_id="condition-preference",
        visible_text=snippet, evidence_text=snippet,
    ).trace
    return int(len(terms) >= 2 and terms <= set(trace.get("body_matched_terms") or ()))


def _comparison_action_priority(question: str, snippet: str) -> int:
    """Prefer the named operation in a comparison over its surrounding nouns.

    Reuse the domain comparison frame. This only orders already qualified
    evidence; mentioning an operation cannot prove the requested distinction.
    """
    frame = match_comparison_frame(question)
    if frame is None:
        return 0
    actions = {
        match[0].casefold() for side in (frame.left, frame.right)
        if (match := re.match(r"[a-z]{4,}ing\b", side, re.I))
    }
    if not actions:
        return 0
    trace = qualify_evidence(
        {"query_terms": sorted(actions)}, query_id="comparison-preference",
        visible_text=snippet, evidence_text=snippet,
    ).trace
    return len(actions & set(trace.get("body_matched_terms") or ()))
