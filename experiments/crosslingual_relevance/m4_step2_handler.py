"""M4 Step 2: real dense handler, canonical fact audit, no rescue scorer.

Shares the pinned vector service and evaluator with M5/M6. Existing historical
results are not overwritten. No oracle-selected result or source is injected.
"""
from __future__ import annotations

import argparse
import json
import tempfile
import uuid
from pathlib import Path

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project
from .evaluation_v2 import assess_packet, save_new_report
from .m4_dense_candidates import ALL_TASKS, PROJECTS
from .m5_real_scorer import _build_vector_service, _index_all
from .m6_holdout import _run_condition
from .pinned_embedding_session import pinned_embeddings


def _is_gold_source(source: dict, task: dict) -> bool:
    assessment = assess_packet({'sources': [source]}, task)
    return assessment['all_required_facts'] and not assessment['canonical_errors']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-sections-per-source', type=int, choices=(2, 20), default=20)
    args = parser.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix='m4-step2-reviewed-'))
    manifest = load_protocol()[2]
    roots = {}
    for project in PROJECTS:
        root = tmp / 'projects' / project
        write_project(root, documents_for(project, manifest))
        roots[project] = str(root)

    with pinned_embeddings() as identity:
        service, config, patcher = _build_vector_service(
            tmp, max_sections_per_source=args.max_sections_per_source,
        )
        try:
            _index_all(service, roots)
            rows = [_run_condition(service, roots[task['project']], task, 'dense_baseline')
                    for task in ALL_TASKS]
        finally:
            patcher.stop()
    output = {
        'schema_version': 2,
        'evaluation_kind': 'dense_handler_without_rescue',
        'model_identity': identity,
        'max_sections_per_source': args.max_sections_per_source,
        'gold_oracle_used': False,
        'rows': rows,
        'summary': {
            'total': len(rows),
            'complete_audited_packets': sum(row['assessment']['verdict'] == 'PASS' for row in rows),
        },
    }
    target = Path(__file__).parent / 'review_runs' / f'm4-step2-{uuid.uuid4().hex}.json'
    save_new_report(target, json.loads(json.dumps(output, default=str)))
    print(target)


if __name__ == '__main__':
    main()
