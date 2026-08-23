#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.product_truth_v1.comparative import build_report, canonical_json
from eval.product_truth_v1.comparative_contract import verify_report
from eval.product_truth_v1.positive_controls import load_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "eval" / "product_truth_v1" / "results" / "comparative-harness.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the P2.2A comparative harness")
    parser.add_argument("--models", default="")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    models = tuple(value.strip() for value in args.models.split(",") if value.strip())
    report = build_report(repo_root=ROOT, model_snapshots=models)
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
                "committed P2.2A harness report differs from the frozen protocol/task-pack derivation; "
                "run with --write and review the authorization change"
            )
    else:
        raise SystemExit(f"missing committed P2.2A harness report: {args.output}")

    print(
        "P2.2A comparative harness: PASS; "
        f"authorized={report['authorization']['task_pack_ready']}; "
        f"canary_runs={report['plans']['canary']['planned_runs']}; "
        f"pilot_runs={report['plans']['full_pilot']['planned_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
