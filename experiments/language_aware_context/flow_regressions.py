"""Unchanged focused product assertions with baseline or explicit flow ordering.

Fresh process per condition. No test/rubric edits, no automatic failure waiver.
The raw pytest exit code and JUnit are retained, including baseline failures.
"""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from pathlib import Path
from .packing_regressions import MODULES


def main() -> int:
    import pytest
    from .flow_experiment import flow_experiment
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', required=True, choices=('baseline', 'flow'))
    parser.add_argument('--junit', required=True, type=Path)
    args = parser.parse_args()
    if args.junit.exists():
        raise FileExistsError(args.junit)
    with (flow_experiment() if args.condition == 'flow' else nullcontext()):
        return int(pytest.main([*(f'tests/docs/{name}.py' for name in MODULES),
                               '-q', f'--junitxml={args.junit}']))


if __name__ == '__main__':
    raise SystemExit(main())
