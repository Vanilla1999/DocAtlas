"""Adversarial relation binding and current-byte/pipeline contracts."""
from dataclasses import asdict
import json
import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence
from tests.docs.test_admission_relation_witnesses import CASES, qualify, probe
from tests.docs._reference_binding_fixtures import capture_reference_case


@pytest.mark.parametrize('origin', ['original', 'host_lookup', 'retrieval_need', 'canonical_intent', 'lexical_topic'])
def test_same_supported_demand_cannot_escape_its_witness_in_another_lane(origin):
    question, _, text, *_ = CASES[0]
    p = {**probe(question), 'query_origin': origin}
    for body, expected in ((text, True), ('The nav title and page title glossary describes precedence.', False)):
        result = qualify_evidence(p, query_id='query-lane-1', visible_text=body, evidence_text=body)
        assert result.qualified is expected, result.trace
        if expected:
            assert result.trace.get('admission_route') == 'typed_local'


@pytest.mark.parametrize('body', [
    '```text\n| Transport key | Protocol |\n|---|---|\n| A | B |\n```',
    '| Transport key | Protocol |\n|---|---|',
    '| Transport key | Protocol |\n|---|---|\n| A | |',
    '| Transport key | Protocol |\n|---|---|\n\n| Other key | Other value |\n|---|---|\n| A | B |',
])
def test_mapping_requires_current_structural_data_row(body):
    assert not qualify(CASES[4][0], body).qualified


@pytest.mark.parametrize('label', ['Example:', 'Examples:', 'Aliases:'])
def test_nested_example_is_not_an_independent_enumerated_method(label):
    body = f'Strict mode can be enabled in these ways:\n\n- {label}\n  - An unrelated sample.'
    assert not qualify(CASES[3][0], body).qualified


@pytest.mark.parametrize('question,body', [(c[0],c[2]) for c in CASES[:3]])
def test_soft_wrapped_prose_and_bullets_do_not_change_relation(question, body):
    split = body.find(' ', max(1, len(body)//2))
    wrapped = '- ' + body[:split] + '\n  ' + body[split+1:]
    result = qualify(question, wrapped)
    assert result.qualified and result.trace.get('admission_route') == 'typed_local'


@pytest.mark.parametrize('index', [3, 4])
def test_list_relations_preserve_requested_condition(index):
    q = CASES[index][0].rstrip('?') + ' when preview is disabled?'
    source = CASES[index][3]
    assert not qualify(q, source).qualified
    assert not qualify(q, 'When preview is enabled, ' + source).qualified
    result = qualify(q, 'When preview is disabled, ' + source)
    assert result.qualified and result.trace.get('admission_route') == 'typed_local', result.trace


def test_unrecognized_default_coordination_cannot_be_declared_a_complete_typed_need():
    question = 'What is RelayClient default timeout and retry delay?'
    result = qualify(question, 'RelayClient default timeout is 7 seconds.')
    assert result.trace.get('admission_route') != 'typed_local'


def test_normal_is_not_a_synonym_for_synchronous_outside_callable_syntax():
    question = 'Can the operating temperature be normal?'
    result = qualify_evidence({'query_text':question, 'query_origin':'original',
         'query_terms':['operating','temperature','normal']}, query_id='query-original',
         visible_text='The operating temperature must be asynchronous.')
    assert result.trace.get('admission_route') != 'typed_local'


@pytest.mark.parametrize('index', range(5))
def test_replaying_old_approval_recomputes_relation_after_crop(index):
    from copy import deepcopy
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles

    q, _, body, *_ = CASES[index]
    # A deliberately explicit literal lookup isolates current-byte attribution.
    # The unchanged original-only native quality cases receive no credit from it.
    plan = build_documentation_query_plan(q, lookup_queries=(body,))
    original, lookup = plan.queries
    assert (original.query_id, original.text, original.origin, original.public_parent_query_id) == (
        'query-original', q, 'original', None,
    )
    assert (lookup.query_id, lookup.text, lookup.origin, lookup.relation, lookup.public_parent_query_id) == (
        'query-lookup-1', body, 'host_lookup', 'host_lookup', None,
    )
    roles = query_constraint_roles(lookup.text)
    data = {
        **asdict(lookup), 'query_text': lookup.text, 'query_origin': lookup.origin,
        'query_terms': list(documentation_query_terms(lookup.text)),
        'exact_terms': list(roles.hard_exact), 'bound_subjects': list(roles.bound_subjects),
    }
    authoritative = asdict(lookup)
    old = qualify_evidence(
        data, query_id=lookup.query_id, visible_text=body, evidence_text=body,
        authoritative_query=authoritative,
    )
    assert old.qualified and old.reason == 'visible_fields', 'critical_relation_crop_healthy'
    assert old.covered_query_ids == ('query-lookup-1',) and old.coverage_kind == 'direct'
    assert old.trace['context_only'] is True and not old.trace.get('public_parent_query_id')
    anonymous = qualify_evidence(data, query_id=lookup.query_id, visible_text=body, evidence_text=body)
    assert anonymous.qualified and anonymous.trace['context_only'] is True
    assert (anonymous.covered_query_ids == () and anonymous.coverage_kind is None
            and anonymous.trace.get('admission_only') is True), 'critical_relation_lookup_no_borrowed_credit'

    inherited = {
        'need_local_witness': True, 'admission_route': 'typed_local',
        'matched_need_ids': ['query-need-1'], 'need_witness_spans': [[0, len(body)]],
        'need_witness_source_key': 'previous-source', '_admission_demands': [{'matched': True}],
        'context_eligible': True, 'context_need_ids': ['query-need-1'],
        '_need_context': {'qualified': True},
    }
    fake = {**old.trace, **inherited}
    before = deepcopy((data, authoritative, fake))
    crop = 'The source contains a glossary only.'
    current = qualify_evidence(
        fake, query_id=lookup.query_id, visible_text=crop, evidence_text=crop,
        authoritative_query=authoritative,
    )
    assert (current.qualified is False and current.reason == 'insufficient_visible_match'
            and current.covered_query_ids == () and current.coverage_kind is None), 'critical_relation_current_crop'
    assert all(key not in current.trace for key in inherited), 'critical_relation_crop_no_inherited_credit'
    assert current.trace['query_text'] == body and current.trace['query_origin'] == 'host_lookup'
    assert not current.trace.get('public_parent_query_id')
    assert (data, authoritative, fake) == before


def test_raw_owner_documents_and_private_meanings_never_leak_to_public_dto(tmp_path):
    q, _, body, *_ = CASES[0]
    cap = capture_reference_case(tmp_path, {'Guide.md':'# Rules\n\n'+body}, q)
    wire = json.dumps(cap['public_payload'])
    assert all(term not in wire for term in ('raw_document', '_admission_demands', 'need_witness_spans', '_reference_evidence'))
    from eval.agent_developer_v1.relation_source_context_controls import run_relation_source_context_controls
    run_relation_source_context_controls(tmp_path / 'current-source-context')


def test_compiled_queries_and_relations_are_pure_without_source_io(monkeypatch):
    from pathlib import Path
    import socket
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles

    q, _, body, *_ = CASES[0]
    lookup, = build_documentation_query_plan(q).queries
    roles = query_constraint_roles(lookup.text)
    data = {
        **asdict(lookup), 'query_text': lookup.text, 'query_origin': lookup.origin,
        'query_terms': list(documentation_query_terms(lookup.text)),
        'exact_terms': list(roles.hard_exact), 'bound_subjects': list(roles.bound_subjects),
    }
    healthy = qualify_evidence(
        data, query_id=lookup.query_id, visible_text=body, evidence_text=body,
        authoritative_query=asdict(lookup),
    )
    assert healthy.qualified and healthy.covered_query_ids == ('query-original',), 'critical_relation_pure_healthy'
    assert healthy.trace['context_only'] is True
    def forbidden(*args, **kwargs):
        raise AssertionError('critical_relation_qualification_no_io')
    with monkeypatch.context() as blocked:
        blocked.setattr('builtins.open', forbidden)
        blocked.setattr(Path, 'read_text', forbidden)
        blocked.setattr(Path, 'read_bytes', forbidden)
        blocked.setattr(socket, 'socket', forbidden)
        current_lookup, = build_documentation_query_plan(q).queries
        current_roles = query_constraint_roles(current_lookup.text)
        current_data = {
            **asdict(current_lookup), 'query_text': current_lookup.text, 'query_origin': current_lookup.origin,
            'query_terms': list(documentation_query_terms(current_lookup.text)),
            'exact_terms': list(current_roles.hard_exact), 'bound_subjects': list(current_roles.bound_subjects),
        }
        assert current_data == data
        current = qualify_evidence(
            current_data, query_id=current_lookup.query_id, visible_text=body, evidence_text=body,
            authoritative_query=asdict(current_lookup),
        )
    assert current == healthy, 'critical_relation_qualification_no_io'
