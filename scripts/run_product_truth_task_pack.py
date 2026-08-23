#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.product_truth_v1.positive_controls import canonical_json, load_json
from eval.product_truth_v1.task_pack import build_report, verify_report


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "eval" / "product_truth_v1" / "results" / "task-pack.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the P2.1C task-pack inventory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(repo_root=ROOT)
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
                "committed P2.1C task-pack evidence differs from the repository inventory; "
                "run with --write and review the capacity change"
            )
    else:
        raise SystemExit(f"missing committed P2.1C task-pack evidence: {args.output}")

    summary = report["summary"]
    print(
        "P2.1C task pack: PASS; "
        f"fixtures={summary['materialized_fixture_tasks']}; "
        f"structural={summary['structurally_complete_tasks']}; "
        f"valid={summary['valid_tasks']}; ready={summary['task_pack_ready']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
