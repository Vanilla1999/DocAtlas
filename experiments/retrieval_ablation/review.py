"""Review execution artifacts only. No semantic judge or retrieval imports."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def summarize(results: list[dict]) -> dict:
    """Keep packet readiness, execution, and unmeasured quality separate."""
    if not results:
        raise ValueError('no runs to review')
    freezes = {r.get('freeze_sha256') for r in results}
    if None in freezes or len(freezes) != 1:
        raise ValueError('different or missing frozen inputs')
    arms = [r.get('arm') for r in results]
    if len(set(arms)) != len(arms):
        raise ValueError('duplicate arm result for one freeze')
    records = []
    for result in results:
        if result.get('quality_status') != 'UNJUDGED':
            raise ValueError('semantic quality is not measured by this stage')
        arm, status = result.get('arm'), result.get('execution_status')
        if arm not in ('P', 'A') or status not in (
                'EXECUTED', 'BLOCKED_ENV', 'HANDLER_FAILED', 'AUDIT_FAILED'):
            raise ValueError('unknown arm or execution status')
        if arm == 'A' and status == 'EXECUTED':
            if (result.get('packet_status') != 'BLOCKED_SAFE_PACKET_ADAPTER'
                    or result.get('model_visible_packet') is not None):
                raise ValueError('diagnostic candidates are not a public packet')
        if arm == 'P' and status == 'EXECUTED':
            if result.get('audit_errors') != [] or not 0 <= result['budget_tokens'] <= 800:
                raise ValueError('executed P must pass the real audit and budget')
        lanes = result.get('lanes', result.get('raw_fts_lanes', []))
        records.append({'arm': arm, 'execution_status': status,
            'quality_status': 'UNJUDGED',
            'packet_status': result.get('packet_status', 'REAL_HANDLER_PACKET' if status == 'EXECUTED' else 'NOT_AVAILABLE'),
            'sql_searches': len(lanes),
            'raw_hits': sum(len(lane['rows']) for lane in lanes),
            'uncapped_incomplete_lanes': sum(not lane['uncapped_complete'] for lane in lanes)})
    return {'planned_runs': 2, 'supplied_runs': len(results),
            'missing_arms': sorted({'P', 'A'} - set(arms)),
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
