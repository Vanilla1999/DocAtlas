"""Current raw owners, not filenames or fabricated namespace metadata."""
from copy import deepcopy

import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


def test_same_project_is_not_subject_authority(tmp_path):
    cap = capture_reference_case(tmp_path, {'QueueTasks.md':
        '# OtherQueue\n\nOtherQueue tasks run after returning a response.\n'},
        'When do QueueTasks tasks run relative to returning the response?')
    assert 'OtherQueue tasks run' not in visible(cap)


def test_spacing_is_not_an_alias_certificate(tmp_path):
    cap = capture_reference_case(tmp_path, {'Guide.md':
        '# Queue Tasks\n\nQueue Tasks run after returning the response.\n'},
        'When do QueueTasks tasks run relative to returning the response?')
    assert 'Queue Tasks run' not in visible(cap)


@pytest.mark.parametrize('name', ['QueueTasks', 'LeaseWorkers'])
def test_native_owner_is_bound_to_current_raw_source(tmp_path, name):
    cap = capture_reference_case(tmp_path, {'Guide.md':
        f'# {name}\n\n{name} groups tasks.\n\nTasks execute in order. '
        'If one raises an exception, later tasks stop.\n'},
        f'If one {name} function raises an exception, what happens to later tasks?')
    assert 'later tasks stop' in visible(cap)


@pytest.mark.parametrize('tamper', ['owner_text', 'owner_scope', 'owner_offset'])
def test_fabricated_owner_cannot_bind_a_current_body(tmp_path, tamper):
    question = 'When do QueueTasks tasks run relative to returning the response?'
    cap = capture_reference_case(tmp_path, {'Guide.md':
        '# OtherTasks\n\nTasks run after returning the response.\n'},
        'When do OtherTasks tasks run relative to returning the response?')
    rows = cap['projection_attempts'][0]['before_projection']['context_pack']
    source = deepcopy(rows[0])
    evidence = source['_reference_evidence']
    assert evidence.get('owner')
    # Current source scope/path/hash/window are retained. Only owner claims change.
    if tamper == 'owner_text':
        evidence['owner']['text'] = '# QueueTasks\n'
        evidence['owner']['char_end'] = evidence['owner']['char_start'] + len('# QueueTasks\n')
    elif tamper == 'owner_scope':
        evidence['owner']['scope_end'] += 10000
    else:
        evidence['owner']['char_start'] += 1
        evidence['owner']['char_end'] += 1
    probe = {'query_text': question, 'query_terms': ['tasks', 'response'],
             'bound_subjects': ['QueueTasks'] if tamper == 'owner_text' else ['OtherTasks']}
    result = qualify_evidence(probe, query_id='query-original',
        visible_text=evidence['text'], evidence_text=evidence['text'], candidate=source)
    assert not result.qualified, result.trace
    assert result.reason == 'invalid_subject_owner', result.trace


def test_fake_namespace_cannot_discharge_an_explicit_symbol():
    body = 'OtherClient default timeout is 7 seconds.'
    result = qualify_evidence({'query_text': 'What is the default timeout of class RelayClient?',
        'query_terms': ['default', 'timeout'], 'exact_terms': ['RelayClient']},
        query_id='query-original', visible_text=body, evidence_text=body,
        candidate={'registered_namespace': 'RelayClient', 'namespace_verified': True,
                   'owner': 'RelayClient', 'title': 'RelayClient'})
    assert not result.qualified


def test_direct_identity_cannot_be_satisfied_by_space_collapsing():
    body = 'Queue Tasks has a documented timeout.'
    result = qualify_evidence({'query_text': 'Explain `QueueTasks` timeout',
        'query_terms': ['timeout'], 'exact_terms': ['QueueTasks']},
        query_id='query-original', visible_text=body, evidence_text=body)
    assert not result.qualified


def test_project_title_cannot_bind_another_api_in_body():
    body = 'OtherTasks execute after response delivery.'
    result = qualify_evidence({'query_text': 'Describe the tasks',
        'query_terms': ['tasks', 'execute'], 'bound_subjects': ['QueueTasks']},
        query_id='query-original', visible_text=body, evidence_text=body,
        candidate={'project_identity':'repo', 'title':'QueueTasks', 'owner':'QueueTasks'},
        expected_project_identity='repo')
    assert not result.qualified
