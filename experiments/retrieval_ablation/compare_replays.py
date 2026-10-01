"""Fail-closed mechanical comparison of saved development replay artifacts.

Does not evaluate semantics, answers, isolation, or causal identification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(root, name):
    return json.loads((root / name).read_text())


def _packets(root, inputs, arm):
    records = _load(root, 'execution.json')
    expected = {(int(name[1:-5]), repeat) for name in inputs['public_files']
                if name.startswith('q') and name.endswith('.json') and name[1:-5].isdigit()
                for repeat in range(1, inputs['repeats'] + 1)}
    selected = [r for r in records if r['arm'] == arm]
    if len(selected) != len(expected) or {(r['case'], r['repeat']) for r in selected} != expected:
        raise ValueError('missing or duplicate executions')
    packets = {}
    for record in selected:
        if record['status'] != 'EXECUTED' or record['audit_errors'] != []:
            raise ValueError('execution failed or recorded audit is not clean')
        result = _load(root, f"r{record['repeat']}-q{record['case']:02}-{arm}.json")
        if result['execution_status'] != 'EXECUTED' or result['packet_audit_errors'] != []:
            raise ValueError('raw execution failed or recorded audit is not clean')
        budget = result['packet_budget_tokens']
        if type(budget) is not int or not 0 <= budget <= 800 or budget != record['tokens']:
            raise ValueError('invalid recorded DTO budget')
        packets[(record['case'], record['repeat'])] = result['model_visible_packet']
    return packets


def compare_replays(left: Path, right: Path, *, arm='B'):
    left, right = Path(left), Path(right)
    a, b = _load(left, 'inputs.json'), _load(right, 'inputs.json')
    for field in ('public_files', 'runtime_path', 'runtime', 'repeats', 'isolation'):
        if field not in a or field not in b or a[field] != b[field]:
            raise ValueError('uncontrolled comparison: ' + field)
    if arm not in a['arms'] or arm not in b['arms']:
        raise ValueError('arm missing from replay')
    if not a.get('code_files') or not b.get('code_files'):
        raise ValueError('missing recorded code identity')
    x, y = _packets(left, a, arm), _packets(right, b, arm)
    if x.keys() != y.keys():
        raise ValueError('execution inventories differ')
    changed = [{'case': case, 'repeat': repeat} for case, repeat in sorted(x)
               if x[(case, repeat)] != y[(case, repeat)]]
    return {'kind': 'recorded_mechanical_comparison', 'arm': arm,
            'paired_executions': len(x), 'changed_DTO': changed,
            'recorded_code_equal': a['code_files'] == b['code_files'],
            'semantic_quality': 'NOT_EVALUATED', 'answer_quality': 'NOT_EVALUATED',
            'artifact_integrity': 'UNSIGNED_RECORDED_ARTIFACTS',
            'causal_effect': 'NOT_CERTIFIED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    parser.add_argument('--arm', default='B')
    args = parser.parse_args()
    print(json.dumps(compare_replays(args.left, args.right, arm=args.arm), indent=2))


if __name__ == '__main__':
    main()
