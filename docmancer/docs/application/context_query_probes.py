"""Requalify independent public questions regardless of candidate discovery route."""
from __future__ import annotations

import re

from docmancer.docs.domain.query_terms import documentation_exact_terms
from docmancer.docs.domain.evidence_qualification import qualify_evidence


def independent_query_probes(source, query_plan):
    matches = dict(source.get('retrieval_query_matches') or {})
    queries = [q for q in query_plan.get('queries') or () if q.get('origin') in {'host_lookup'}]
    terms = {q['query_id']: set(re.findall(r'[A-Za-zА-Яа-яЁё0-9_.-]{4,}', str(q.get('text') or '').casefold())) for q in queries}
    for query in queries:
        if query.get('origin') not in {'host_lookup'} or query.get('public_parent_query_id'):
            continue
        query_id = str(query.get('query_id') or '')
        if not query_id or query_id in matches:
            continue
        text = str(query.get('text') or '')
        probe = {
            'query_text': text, 'query_origin': query['origin'],
            'relation': query.get('relation'),
            'exact_terms': [term.normalized_value for term in documentation_exact_terms(text)],
            'forbidden_catalog_roles': list(query.get('forbidden_catalog_roles') or ()),
            'forbidden_evidence_terms': list(query.get('forbidden_evidence_terms') or ()),
            'parent_exact_terms': list(query.get('parent_exact_terms') or ()),
        }
        qualified = qualify_evidence(probe, query_id=query_id, visible_text=str(source.get('snippet') or ''),
            evidence_text=str(source.get('snippet') or ''), catalog_role=str(source.get('catalog_role') or ''),
            candidate=source.get('_qualification_candidate', source),
            expected_project_identity=source.get('_expected_project_identity'),
            lifecycle_intent=source.get('_lifecycle_intent', 'current'))
        distinctive = terms[query_id] - set().union(*(value for key, value in terms.items() if key != query_id))
        body_matches = set(qualified.trace.get('body_matched_terms') or ())
        if qualified.qualified and len(body_matches) >= min(2, len(terms[query_id])) and distinctive & body_matches:
            matches[query_id] = dict(qualified.trace)
    return matches
