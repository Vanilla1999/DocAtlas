#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.product_truth_v1.positive_controls import (
    DEFAULT_TASK_IDS,
    build_report,
    canonical_json,
    load_json,
    verify_report,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "eval" / "product_truth_v1" / "results" / "positive-controls.json"
DEFAULT_ORACLE_ROOT = ROOT / "eval" / "product_truth_v1" / "oracle-controls"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run P2.1B Product Truth positive controls")
    parser.add_argument("--tasks", default=",".join(DEFAULT_TASK_IDS))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--oracle-root", type=Path, default=DEFAULT_ORACLE_ROOT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    task_ids = tuple(value.strip() for value in args.tasks.split(",") if value.strip())
    report = build_report(
        repo_root=ROOT,
        task_ids=task_ids,
        oracle_control_root=args.oracle_root,
    )
    verify_report(report)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    elif args.output.is_file():
        committed = load_json(args.output)
        verify_report(committed)
        if canonical_json(committed) != canonical_json(report):
            raise SystemExit(
                "committed P2.1B evidence differs from the two-clean-worktree derivation; "
                "run with --write and review the result"
            )
    else:
        raise SystemExit(f"missing committed P2.1B evidence: {args.output}")

    summary = report["summary"]
    print(
        "P2.1B positive controls: PASS; "
        f"tasks={summary['task_count']}; gold={summary['gold_reproducible']}; "
        f"real_model_oracle={summary['real_model_oracle_passed']}; "
        f"valid={summary['valid_tasks']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
