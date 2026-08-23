#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.product_truth_v1.execution_gate import build_report, verify_report
from eval.product_truth_v1.positive_controls import canonical_json, load_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "eval" / "product_truth_v1" / "results" / "execution-gate.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the P2.2B/C execution gate")
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
                "committed P2.2B/C execution evidence differs from the authorization gate; "
                "run with --write and review the transition"
            )
    else:
        raise SystemExit(f"missing committed P2.2B/C execution evidence: {args.output}")

    print(
        "P2.2B/C execution gate: PASS; "
        f"authorized={report['authorization']['scored_execution_authorized']}; "
        f"scored_runs={report['decision']['scored_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
