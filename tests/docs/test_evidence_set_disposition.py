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


def test_unknown_relevant_text_is_context_only_not_supported():
    contract, args = context_case()
    result = classify_need_context(contract, **args)
    assert result.state == 'retrieval_only', result
    assert result.need_id == contract.need.need_id
    assert result.set_id is None


def test_current_default_relation_with_visible_dependencies_is_supported():
    contract, args = context_case('What is RelayClient default timeout?',
        '# RelayClient\n\nRelayClient default timeout is 7 seconds.\n')
    result = classify_need_context(contract, **args)
    assert result.state == 'supported', result
    assert result.set_id in {item.set_id for item in args['bundles']}


@pytest.mark.parametrize('field,value', [
    ('project_identity', 'foreign'), ('resolved_version', 'v2'),
    ('generation_id', 'old'), ('path_or_url', 'Other.md'),
    ('freshness', 'stale'), ('risk_flags', ['unsafe']),
    ('_source_snapshot_sha256', '0' * 64), ('char_span', [0, 2]),
])
def test_current_source_guards_cannot_be_rescued_by_relevance(field, value):
    contract, args = context_case()
    args['candidate'][field] = value
    args['candidate'].update(context_eligible=True, semantic_verified=True, model_score=1.0)
    assert classify_need_context(contract, **args).state == 'blocked'


def test_missing_real_identifier_is_blocked_not_context_only():
    contract, args = context_case('Explain the retry scheduling behavior of class MissingClass.', BODY)
    assert classify_need_context(contract, **args).state == 'blocked'


@pytest.mark.parametrize('state', ['enabled', 'not disabled'])
def test_opposite_applicability_is_not_retrieval_only(state):
    contract, args = context_case('What is RelayClient default timeout when preview is disabled?',
        f'# RelayClient\n\nWhen preview is {state}, RelayClient default timeout is 7 seconds.\n')
    assert classify_need_context(contract, **args).state == 'blocked'


def test_unknown_condition_is_not_silently_discarded():
    contract, args = context_case(QUESTION.rstrip('.') + ' only for administrators.', BODY)
    assert classify_need_context(contract, **args).state != 'supported'


def test_equal_words_in_glossary_do_not_prove_precedence():
    q = 'Which takes precedence: nav title or page title?'
    contract, args = context_case(q, '# Titles\n\nNav title and page title are glossary terms about precedence.\n')
    assert classify_need_context(contract, **args).state == 'retrieval_only'


def test_forged_contract_and_set_routing_do_not_mint_support():
    contract, args = context_case()
    assert classify_need_context(replace(contract, interpretation='supported', expected_count=7), **args).state == 'blocked'
    args['bundles'] = tuple(replace(b, proposed_need_ids=('forged-need',)) for b in args['bundles'])
    assert classify_need_context(contract, **args).state == 'blocked'


def test_cached_body_does_not_survive_changed_prepared_source():
    contract, args = context_case()
    assert classify_need_context(contract, **args).state == 'retrieval_only'
    record = next(iter(args['prepared_sources'].values()))
    record['raw_document'] = BODY.replace('RelayClient', 'OtherClient')
    assert classify_need_context(contract, **args).state == 'blocked'


def test_heading_or_single_name_is_not_enough_context():
    contract, args = context_case(body='# RelayClient\n\nRelayClient is a glossary term.\n')
    assert classify_need_context(contract, **args).state == 'blocked'


def test_scoped_contract_does_not_match_a_new_question():
    contract, args = context_case()
    other = deepcopy(args['candidate']['_reference_root_plan'])
    other['question'] = 'What is a different requirement?'
    args['candidate']['_reference_root_plan'] = other
    assert classify_need_context(contract, **args).state == 'blocked'


def test_no_approval_flag_changes_a_current_context_decision():
    contract, args = context_case()
    before = classify_need_context(contract, **args)
    args['candidate'].update(context_eligible=True, qualified=True,
        admission_route='typed_local', semantic_verified=True, model_score=1.0)
    assert classify_need_context(contract, **args) == before


def test_incoming_context_flag_cannot_survive_exact_guard_rejection():
    from docmancer.docs.domain.evidence_qualification import qualify_evidence
    body = 'RelayClient default timeout is 7 seconds.'
    trace = qualify_evidence({'query_text': 'Explain class MissingClass timeout',
        'query_terms': ['timeout'], 'exact_terms': ['MissingClass'],
        'context_eligible': True, 'context_need_ids': ['forged'], '_need_context': {'state': 'supported'}},
        query_id='query-original', visible_text=body, evidence_text=body)
    assert not trace.qualified
    assert trace.trace.get('context_eligible') is not True
    assert not trace.trace.get('context_need_ids')
    assert not trace.trace.get('_need_context')


def test_requested_state_cannot_be_borrowed_from_a_different_subject():
    contract, args = context_case('What is RelayClient default timeout when preview is disabled?',
        '# Clients\n\nWhen preview is disabled, OtherClient default timeout is 7 seconds.\n\n'
        'When preview is enabled, RelayClient default timeout is 7 seconds.\n')
    assert classify_need_context(contract, **args).state == 'blocked'
