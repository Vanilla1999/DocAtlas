"""Review-tool correctness; not model/retrieval quality evidence."""
from copy import deepcopy
import pytest
from experiments.language_aware_context.pilot_review import blind_records, join_judgments


def inputs():
    tasks = {'task-1': {'question': 'Can it run?', 'answerable': True,
                       'facts': ['It runs after response.'], 'query_language': 'en', 'family': 'demo'}}
    record = {'task_id': 'task-1', 'condition': 'A', 'question': 'Can it run?',
              'evidence': [{'id': 'S1', 'path': 'docs/demo.md', 'text': 'It runs after response.'}],
              'answer': {'text': 'It runs after response. [S1]'}, 'observed': {'secret': 'hidden'},
              'plan_valid': True}
    return tasks, record


def exported():
    tasks, record = inputs()
    return blind_records([record], tasks, token=lambda: 'opaque')


def judgment(packet):
    return {'id': packet['id'], 'packet_sha256': packet['packet_sha256'],
            'packet_complete': True, 'factually_correct': True, 'grounded': True,
            'citations_valid': True, 'language_ok': True, 'reason': 'All facts are visible.'}


def test_blind_export_has_no_arm_trace_id_or_plan():
    packets, key = exported()
    assert len(packets) == 1
    packet = packets[0]
    assert set(packet) == {'id', 'question', 'answerable', 'expected_facts', 'evidence', 'answer', 'packet_sha256'}
    assert packet['id'] == 'opaque'
    assert len(packet['packet_sha256']) == 64
    assert key[0]['condition'] == 'A'
    assert 'hidden' not in repr(packet)


def test_identical_review_content_is_deduplicated_not_counted_as_new_call():
    tasks, a = inputs(); b = deepcopy(a); b['condition'] = 'B'
    packets, key = blind_records([a, b], tasks, token=lambda: 'opaque')
    assert len(packets) == 1 and len(key) == 2
    assert key[0]['id'] == key[1]['id']


def test_distinct_content_with_id_collision_fails():
    tasks, a = inputs(); b = deepcopy(a); b['condition'] = 'B'; b['answer']['text'] = 'Insufficient evidence.'
    with pytest.raises(ValueError, match='collision'):
        blind_records([a, b], tasks, token=lambda: 'opaque')


def test_changed_question_fails():
    tasks, a = inputs(); a['question'] = 'Changed'
    with pytest.raises(ValueError):
        blind_records([a], tasks, token=lambda: 'opaque')


def test_duplicate_task_condition_fails():
    tasks, a = inputs()
    with pytest.raises(ValueError):
        blind_records([a, a], tasks, token=lambda: 'opaque')


def test_unknown_task_fails():
    _, a = inputs()
    with pytest.raises(ValueError):
        blind_records([a], {}, token=lambda: 'opaque')


def test_complete_review_joins_and_derives_success():
    packets, key = exported()
    rows = join_judgments(packets, key, [judgment(packets[0])])
    assert len(rows) == 1 and rows[0]['condition'] == 'A'
    assert rows[0]['primary_success'] is True


def test_correct_but_unsupported_is_not_primary_success():
    packets, key = exported(); j = judgment(packets[0]); j['grounded'] = False
    rows = join_judgments(packets, key, [j])
    assert rows[0]['primary_success'] is False
    assert rows[0]['factually_correct'] is True


def test_missing_citation_is_not_forgiven():
    packets, key = exported(); j = judgment(packets[0]); j['citations_valid'] = False
    assert join_judgments(packets, key, [j])[0]['primary_success'] is False


def test_missing_judgment_fails():
    packets, key = exported()
    with pytest.raises(ValueError):
        join_judgments(packets, key, [])


def test_duplicate_judgment_fails():
    packets, key = exported(); j = judgment(packets[0])
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j, j])


def test_unknown_judgment_fails():
    packets, key = exported(); j = judgment(packets[0]); j['id'] = 'other'
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])


def test_changed_review_packet_fails():
    packets, key = exported(); j = judgment(packets[0]); packets[0]['answer'] = 'Modified'
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])


def test_changed_key_binding_fails():
    packets, key = exported(); j = judgment(packets[0]); key[0]['packet_sha256'] = '0' * 64
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])


def test_numeric_boolean_not_accepted():
    packets, key = exported(); j = judgment(packets[0]); j['grounded'] = 1
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])


def test_unanswerable_packet_complete_must_be_null():
    tasks, a = inputs(); tasks['task-1']['answerable'] = False
    packets, key = blind_records([a], tasks, token=lambda: 'opaque'); j = judgment(packets[0])
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])
    j['packet_complete'] = None
    assert join_judgments(packets, key, [j])[0]['packet_complete'] is None


def test_answerable_packet_complete_cannot_be_null():
    packets, key = exported(); j = judgment(packets[0]); j['packet_complete'] = None
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])


def test_reason_is_required():
    packets, key = exported(); j = judgment(packets[0]); j['reason'] = ' '
    with pytest.raises(ValueError):
        join_judgments(packets, key, [j])
