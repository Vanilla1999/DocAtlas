import copy
import json

import pytest

from experiments.retrieval_ablation.compare_replays import compare_replays


def replay(root):
    root.mkdir()
    inputs = {'public_files': {'q01.json': 'hash'}, 'runtime_path': '/fixed',
              'runtime': 'python', 'repeats': 1, 'isolation': 'ordinary',
              'arms': ['B'], 'code_files': {'adapter.py': 'hash'}}
    records = [{'case': 1, 'repeat': 1, 'arm': 'B', 'status': 'EXECUTED',
                'audit_errors': [], 'tokens': 40}]
    result = {'execution_status': 'EXECUTED', 'packet_audit_errors': [],
              'packet_budget_tokens': 40, 'model_visible_packet': {'sources': []}}
    for name, value in [('inputs.json', inputs), ('execution.json', records),
                        ('r1-q01-B.json', result)]:
        (root / name).write_text(json.dumps(value))
    return inputs, records, result


def test_comparison_does_not_promote_mechanical_identity_to_quality(tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    replay(left)
    _, _, result = replay(right)
    report = compare_replays(left, right)
    assert report['changed_DTO'] == []
    assert report['semantic_quality'] == report['answer_quality'] == 'NOT_EVALUATED'
    result['model_visible_packet'] = {'sources': [{'snippet': 'different'}]}
    (right / 'r1-q01-B.json').write_text(json.dumps(result))
    assert compare_replays(left, right)['changed_DTO'] == [{'case': 1, 'repeat': 1}]


def test_comparison_rejects_uncontrolled_or_failed_replays(tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    replay(left)
    inputs, records, result = replay(right)
    for field in ('runtime_path', 'public_files', 'runtime', 'repeats', 'isolation'):
        changed = copy.deepcopy(inputs)
        changed[field] = 'different'
        (right / 'inputs.json').write_text(json.dumps(changed))
        with pytest.raises(ValueError, match='uncontrolled'):
            compare_replays(left, right)
    (right / 'inputs.json').write_text(json.dumps(inputs))
    for changed in ([], records * 2, [{**records[0], 'status': 'HANDLER_FAILED'}],
                    [{**records[0], 'audit_errors': ['unsafe']} ]):
        (right / 'execution.json').write_text(json.dumps(changed))
        with pytest.raises(ValueError):
            compare_replays(left, right)
    (right / 'execution.json').write_text(json.dumps(records))
    for field, value in [('packet_budget_tokens', 801), ('packet_audit_errors', ['unsafe']),
                         ('execution_status', 'HANDLER_FAILED')]:
        changed = {**result, field: value}
        (right / 'r1-q01-B.json').write_text(json.dumps(changed))
        with pytest.raises(ValueError):
            compare_replays(left, right)
