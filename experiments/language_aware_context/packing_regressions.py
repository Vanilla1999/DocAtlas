"""Run unchanged focused product tests with one explicit process-local condition.

The same module list is used in both conditions. This is not the full repository
regression gate and does not change collection, diagnostic inventory or markers.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from pathlib import Path
from .packing_experiment import packing_experiment

MODULES = (
    'test_admission_guard_composition', 'test_admission_local_binding',
    'test_admission_mapping_assignments', 'test_admission_meaning',
    'test_admission_pipeline_invariants', 'test_admission_relation_safety',
    'test_admission_role_boundaries', 'test_admission_subject_binding',
    'test_context_projection_boundaries', 'test_docs_context_compound_projection',
    'test_evidence_admission_sufficiency', 'test_model_visible_projection',
    'test_model_visible_projection_part02', 'test_projection_decision_trace',
    'test_projection_facade_hooks', 'test_reference_projection_retention',
    'test_requested_evidence_retention', 'test_support_retention_integration',
    'test_joint_context_invariants', 'test_query_block_guards',
    'test_relation_preserving_projection', 'test_source_continuation',
)


def main() -> int:
    import pytest
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', required=True, choices=('baseline', 'candidate'))
    parser.add_argument('--junit', type=Path, required=True)
    args = parser.parse_args()
    if args.junit.exists():
        raise FileExistsError(args.junit)
    with (packing_experiment() if args.condition == 'candidate' else nullcontext()):
        return int(pytest.main([*(f'tests/docs/{m}.py' for m in MODULES),
            '-q', f'--junitxml={args.junit}']))


if __name__ == '__main__':
    raise SystemExit(main())
