"""Current raw owners, not filenames or fabricated namespace metadata."""
from copy import deepcopy

import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


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

