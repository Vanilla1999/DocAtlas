"""Compare actual installed-MCP artifacts; never replace missing executions."""
from __future__ import annotations
import json
import os
from pathlib import Path


def main():
    temp = Path(os.environ['RUNNER_TEMP'])
    policy = 'default'
    summaries, rows, missing = {}, [], []
    for suite in ('v40', 'holdout', 'fresh'):
        candidate = temp / 'arms' / f'facet-live-{suite}-{policy}-{os.environ["GITHUB_RUN_ID"]}' / 'run'
        baseline = temp / 'baselines' / suite / 'run'
        if not (candidate / 'SUMMARY.json').exists():
            missing.append(suite)
            continue
        a = json.loads((baseline / 'SUMMARY.json').read_text())
        b = json.loads((candidate / 'SUMMARY.json').read_text())
        expected = ('ed61b4d31a3f2d1e8ca72f950fe1ba9d3fba65f0' if suite == 'fresh'
                    else '828bace5d111890dbb8830cc0c478d352f7564ca')
        assert a['head'] == expected and b['head'] == os.environ['GITHUB_SHA']
        assert b['policy'] == policy and b['integrity_pass'] == b['cases']
        old_inputs = json.loads((baseline / 'FREEZE.json').read_text())['inputs']
        new_inputs = json.loads((candidate / 'FREEZE.json').read_text())['inputs']
        prefixes = ('eval/prepared_model_comparison40/', 'eval/adaptive_gap_holdout/', 'eval/fresh_dialogues/')
        assert old_inputs == {k: v for k, v in new_inputs.items() if k.startswith(prefixes)}
        summaries[suite] = {'fixed': a, 'candidate': b}
        aa = {r['case_id']: r for r in json.loads((baseline / 'ASSESSMENTS.json').read_text())}
        bb = {r['case_id']: r for r in json.loads((candidate / 'ASSESSMENTS.json').read_text())}
        assert aa.keys() == bb.keys()
        for cid in aa:
            a, b = aa[cid], bb[cid]
            assert a['question'] == b['question'] and a['search_question'] == b['search_question']
            rows.append({'suite': suite, 'case_id': cid, 'answerability': a['answerability'],
                'fixed_pass': a['passed'], 'candidate_pass': b['passed'],
                'fixed_tokens': a['tokens'], 'candidate_tokens': b['tokens'],
                'fixed_groups': a['selected_groups'], 'candidate_groups': b['selected_groups'],
                'new_loss': a['answerability'] != 'unanswerable' and a['passed'] and not b['passed']})
    totals = {p: {'tokens': sum(r[p + '_tokens'] for r in rows),
        'documented_pass': sum(r[p + '_pass'] for r in rows if r['answerability'] != 'unanswerable'),
        'documented_total': sum(r['answerability'] != 'unanswerable' for r in rows)}
        for p in ('fixed', 'candidate')}
    passed = (not missing and len(rows) == 64 and not any(r['new_loss'] for r in rows)
        and totals['candidate']['documented_pass'] == totals['candidate']['documented_total']
        and totals['candidate']['tokens'] < totals['fixed']['tokens'])
    result = {'head': os.environ['GITHUB_SHA'], 'policy': policy,
        'strategy_revision': 'global-margin-envelope-v2', 'summaries': summaries,
        'cases': rows, 'totals': totals, 'missing_arms': missing, 'regression_gate_passed': passed,
        'answer_model_calls': 0, 'provider_usage': None, 'default_rollout': False,
        'boundary': 'Development-selected margin; 64 known regression questions, not unseen generalization. First retrieval evidence, not final answers or total dialogue cost.'}
    (temp / 'paired/PAIRED.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, ensure_ascii=False, indent=2))
    assert passed, 'documented coverage, source execution or visible-token acceptance failed'


if __name__ == '__main__':
    main()
