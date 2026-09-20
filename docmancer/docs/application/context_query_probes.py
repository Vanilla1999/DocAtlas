"""Requalify independent public questions regardless of candidate discovery route."""
from __future__ import annotations

import re
from typing import Any

from docmancer.docs.domain.documentation_query_plan import technical_anchors

from docmancer.docs.domain.query_terms import query_constraint_roles
from docmancer.docs.domain.evidence_qualification import qualify_evidence


def independent_query_probes(source, query_plan):
    matches = dict(source.get('retrieval_query_matches') or {})
    queries = [q for q in query_plan.get('queries') or () if q.get('origin') in {'original', 'host_lookup', 'retrieval_need'} and not q.get('public_parent_query_id')]
    terms = {q['query_id']: set(re.findall(r'[A-Za-zА-Яа-яЁё0-9_.-]{4,}', str(q.get('text') or '').casefold())) for q in queries}
    for query in queries:
        query_id = str(query.get('query_id') or '')
        if not query_id or query_id in matches:
            continue
        text = str(query.get('text') or '')
        probe = {
            'query_text': text, 'query_origin': query['origin'],
            'relation': query.get('relation'),
            'exact_terms': list(query_constraint_roles(text).hard_exact),
            'bound_subjects': list(query_constraint_roles(text).bound_subjects),
            'retrieval_anchors': list(query_constraint_roles(text).retrieval_anchors),
            'forbidden_catalog_roles': list(query.get('forbidden_catalog_roles') or ()),
            'forbidden_evidence_terms': list(query.get('forbidden_evidence_terms') or ()),
            'parent_exact_terms': list(query.get('parent_exact_terms') or ()),
            'need_subject': query.get('need_subject'), 'need_relation': query.get('need_relation'),
            'need_context': query.get('need_context'),
        }
        qualified = qualify_evidence(probe, query_id=query_id, visible_text=str(source.get('snippet') or ''),
            evidence_text=str(source.get('snippet') or ''), catalog_role=str(source.get('catalog_role') or ''),
            candidate={**source.get('_qualification_candidate', {}), **source},
            expected_project_identity=source.get('_expected_project_identity'),
            lifecycle_intent=source.get('_lifecycle_intent', 'current'))
        body_matches = set(qualified.trace.get('body_matched_terms') or ())
        if query.get('origin') in {'original', 'retrieval_need'}:
            if qualified.qualified:
                trace = dict(qualified.trace)
                if query.get('origin') == 'original':
                    trace['admission_only'] = True
                matches[query_id] = trace
            continue
        distinctive = terms[query_id] - set().union(*(value for key, value in terms.items() if key != query_id))
        if qualified.qualified and len(body_matches) >= min(2, len(terms[query_id])) and distinctive & body_matches:
            matches[query_id] = dict(qualified.trace)
    return matches


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


def _normalized_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").removeprefix("./").casefold()


def revalidate_structural_continuation(trace, source, visible_text):
    """Derived structural coverage cannot survive source/window substitution."""
    from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
    from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
    candidate = {**source.get("_qualification_candidate", {}), **source}
    result = dict(trace)
    reason = evidence_policy_rejection_reason(trace, visible_text=visible_text,
        catalog_role=str(source.get("catalog_role") or ""), candidate=candidate,
        expected_project_identity=source.get("_expected_project_identity"),
        lifecycle_intent=source.get("_lifecycle_intent", "current"))
    if reason is None:
        result, reason = prepare_reference_probe(result, candidate=candidate,
            evidence_text=str(source.get("snippet") or ""))
    if reason is not None:
        result.update(qualified=False, qualification_reason=reason)
    return result
