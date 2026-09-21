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
    q, _, body, *_ = CASES[index]
    old = qualify(q, body)
    fake = {**old.trace, '_admission_demands': [{'matched': True}], 'need_local_witness': True}
    crop = 'The source contains a glossary only.'
    current = qualify_evidence(fake, query_id='query-need-1', visible_text=crop, evidence_text=crop)
    assert not current.qualified and not current.trace.get('need_local_witness')
    assert not current.trace.get('matched_need_ids')


def test_raw_owner_documents_and_private_meanings_never_leak_to_public_dto(tmp_path):
    q, _, body, *_ = CASES[0]
    cap = capture_reference_case(tmp_path, {'Guide.md':'# Rules\n\n'+body}, q)
    wire = json.dumps(cap['public_payload'])
    assert all(term not in wire for term in ('raw_document', '_admission_demands', 'need_witness_spans', '_reference_evidence'))


def test_compiled_queries_and_relations_are_pure_without_source_io(monkeypatch):
    from pathlib import Path
    import socket
    q, _, body, *_ = CASES[0]
    assert qualify(q, body).qualified
    def forbidden(*args, **kwargs):
        raise AssertionError('relation proof or query compiler performed I/O')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    assert qualify(q, body).qualified
