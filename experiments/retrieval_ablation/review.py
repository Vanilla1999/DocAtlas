"""Post-execution mechanical review. No semantic judge or retrieval calls."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def _canonical(value):
    def encode(item):
        if isinstance(item, (set, frozenset)) and all(isinstance(x, str) for x in item):
            return sorted(item)
        raise TypeError(type(item).__name__)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'), default=encode).encode('utf-8')


def summarize(results: list[dict]) -> dict:
    """Execution and canonical validation never certify semantic sufficiency."""
    if not results:
        raise ValueError('no runs to review')
    freezes = {r.get('freeze_sha256') for r in results}
    if None in freezes or len(freezes) != 1:
        raise ValueError('different or missing frozen inputs')
    arms = [r.get('arm') for r in results]
    if len(set(arms)) != len(arms):
        raise ValueError('duplicate arm result for one freeze')
    plans = [r.get('planned_arms', ['P', 'A']) for r in results]
    if any(plan != plans[0] for plan in plans):
        raise ValueError('different declared arm plans')
    planned = plans[0]
    supported = {'P', 'A', 'B', 'D_L', 'E_G_L'}
    if not isinstance(planned, list) or not planned or len(set(planned)) != len(planned) or not set(planned) <= supported:
        raise ValueError('invalid arm plan')
    records = []
    for result in results:
        if result.get('quality_status') != 'UNJUDGED':
            raise ValueError('semantic quality is not measured by this stage')
        arm, status = result.get('arm'), result.get('execution_status')
        if arm not in planned or status not in (
                'EXECUTED', 'BLOCKED_ENV', 'HANDLER_FAILED', 'AUDIT_FAILED',
                'BLOCKED_REPRESENTATION', 'BLOCKED_OS_ISOLATION'):
            raise ValueError('unknown arm or execution status')
        if arm != 'P' and status == 'EXECUTED':
            if result.get('packet_contract') == 'source-bound-project-v1':
                from docmancer.docs.application.model_visible_projection import (
                    docs_context_budget_tokens, validate_model_visible_projection)
                packet = result.get('model_visible_packet')
                if (not isinstance(packet, dict) or result.get('packet_status') != 'EXECUTED'
                        or result.get('audit_errors') != []
                        or any(packet.get(k) is not False for k in ('answer_supported', 'answer_available', 'edit_ready'))
                        or docs_context_budget_tokens(packet) != result.get('budget_tokens')
                        or validate_model_visible_projection(packet, snapshot=result.get('packet_snapshot'), max_tokens=800)):
                    raise ValueError('invalid source-bound packet')
            elif (result.get('packet_status') != 'BLOCKED_SAFE_PACKET_ADAPTER'
                    or result.get('model_visible_packet') is not None):
                raise ValueError('diagnostic candidates are not a public packet')
        if arm == 'P' and status == 'EXECUTED':
            if result.get('audit_errors') != [] or not 0 <= result['budget_tokens'] <= 800:
                raise ValueError('executed P must pass the real audit and budget')
        lanes = result.get('lanes', result.get('raw_fts_lanes', []))
        if 'saved_native_pool' in result and hashlib.sha256(_canonical(result['saved_native_pool'])).hexdigest() != result.get('native_pool_sha256'):
            raise ValueError('saved pool digest mismatch')
        records.append({'arm': arm, 'execution_status': status,
            'quality_status': 'UNJUDGED',
            'packet_status': result.get('packet_status', 'REAL_HANDLER_PACKET' if status == 'EXECUTED' else 'NOT_AVAILABLE'),
            'sql_searches_executed': result.get('search_count', len(lanes)),
            'sql_searches_inherited': result.get('inherited_search_count', 0),
            'raw_hits_exposed': sum(len(lane['rows']) for lane in lanes),
            'uncapped_incomplete_lanes': sum(not lane['uncapped_complete'] for lane in lanes),
            'budget_tokens': result.get('budget_tokens')})
    by_arm = {r['arm']: r for r in results if r['execution_status'] == 'EXECUTED'}
    shared = [by_arm[a] for a in ('B', 'D_L', 'E_G_L') if a in by_arm]
    if len(shared) > 1 and len({r.get('native_pool_sha256') for r in shared}) != 1:
        raise ValueError('assembly pair does not share the saved native pool')
    if all(a in by_arm for a in ('D_L', 'E_G_L')):
        left, right = by_arm['D_L'], by_arm['E_G_L']
        if _canonical(left['prepared_candidates']) != _canonical(right['prepared_candidates']):
            raise ValueError('gate pair input changed')
        expected = hashlib.sha256(_canonical(left['prepared_candidates'])).hexdigest()
        if left.get('pre_gate_input_sha256') != expected or right.get('pre_gate_input_sha256') != expected:
            raise ValueError('gate input digest mismatch')
    return {'planned_runs': len(planned), 'supplied_runs': len(results),
            'missing_arms': sorted(set(planned) - set(arms)),
            'execution_counts': dict(Counter(r['execution_status'] for r in records)),
            'semantic_evaluable': 0, 'quality_outcome': 'INCONCLUSIVE',
            'answer_evaluation': 'ANSWER_EVALUATION_NOT_RUN',
            'resource_matched_P_vs_A': False,
            'first_loss': 'NOT_MEASURED', 'runs': records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, nargs='+')
    args = parser.parse_args()
    print(json.dumps(summarize([json.loads(p.read_bytes()) for p in args.results]),
                     indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
