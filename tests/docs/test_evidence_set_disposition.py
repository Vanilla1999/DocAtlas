"""Current-byte relevance is not authority or semantic support."""
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256

import pytest

from docmancer.docs.application.need_context_disposition import classify_need_context
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import CatalogSource, ScopeKey, resolve_references
from docmancer.docs.domain.evidence_set_types import SourceKey
from docmancer.docs.domain.evidence_set_validation import build_dependency_sets

QUESTION = 'Please explain the documented retry scheduling behavior of RelayClient and its interaction with worker pressure.'
BODY = '# RelayClient\n\nRelayClient retry scheduling uses a bounded queue.\n'


def context_case(question=QUESTION, body=BODY):
    scope = ScopeKey('project', 'v1', 'g1')
    digest = sha256(body.encode()).hexdigest()
    catalog = CatalogSource('doc1', scope, 'Guide.md', digest)
    references = resolve_references(question, catalog=(catalog,), scope=scope)
    contract = compile_need_contracts(question, references)[0]
    key = SourceKey(scope, 'doc1', 'Guide.md', digest)
    evidence = {'schema_version': 1, 'source': asdict(catalog),
        'raw_document': body, 'text': body, 'char_start': 0, 'char_end': len(body), 'owner': None}
    candidate = {'source_class': 'project_doc', 'project_identity': 'project',
        'resolved_version': 'v1', 'generation_id': 'g1', 'path_or_url': 'Guide.md',
        'char_span': [0, len(body)], 'snippet': body, 'authority': 'source_of_truth',
        '_reference_evidence': evidence, '_reference_root_plan': asdict(references),
        '_reference_plans': {question: asdict(references)}}
    bundles, _ = build_dependency_sets(body, key, 0, len(body),
                                      proposed_need_ids=(contract.need.need_id,))
    sources = {key: {'source': asdict(catalog), 'raw_document': body}}
    return contract, {'reference_plan': references, 'candidate': candidate,
        'bundles': bundles, 'prepared_sources': sources}

