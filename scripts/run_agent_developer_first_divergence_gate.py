#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.first_divergence import (
    canonical_json,
    derive_from_paths,
    load_json,
    sha256_json,
    verify_atlas,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
DEFAULT_REPORT = PROTOCOL_ROOT / "results" / "model-benchmark.json"
DEFAULT_ORACLE = PROTOCOL_ROOT / "expected_trajectories.json"
DEFAULT_TASKS = PROTOCOL_ROOT / "tasks.json"
DEFAULT_ATLAS = PROTOCOL_ROOT / "results" / "first-divergence-atlas.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the frozen Agent Developer 0/11 first-divergence atlas"
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    derived = derive_from_paths(
        repo_root=REPO_ROOT,
        report_path=args.report,
        oracle_path=args.oracle,
        tasks_path=args.tasks,
    )
    verify_atlas(derived)
    if args.write:
        args.atlas.parent.mkdir(parents=True, exist_ok=True)
        args.atlas.write_text(
            json.dumps(derived, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        committed = load_json(args.atlas)
        verify_atlas(committed)
        if canonical_json(committed) != canonical_json(derived):
            raise SystemExit(
                "committed first-divergence atlas differs from the frozen report/oracle derivation; "
                "run with --write and review the evidence change"
            )

    counts = derived["summary"]["failure_class_counts"]
    print(
        "P1.2 first-divergence atlas: PASS; "
        f"tasks={derived['summary']['task_count']}; "
        f"classes={counts}; sha256={sha256_json(derived)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
