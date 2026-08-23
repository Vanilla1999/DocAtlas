#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.product_truth_v1.product_decision import build_report, verify_report
from eval.product_truth_v1.product_decision_render import (
    render_analysis,
    render_scorecard,
)
from eval.product_truth_v1.protocol import canonical_json, load_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "eval" / "product_truth_v1" / "results" / "product-decision.json"
DEFAULT_ANALYSIS = ROOT / "docs" / "analysis" / "p2.3-product-decision.md"
DEFAULT_SCORECARD = ROOT / "docs" / "product-truth-scorecard.md"


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _check(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing P2.3 generated artifact: {path}")
    if path.read_text(encoding="utf-8") != expected:
        raise SystemExit(
            f"P2.3 generated artifact drift: {path}; "
            "run with --write and review the evidence change"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the P2 Product Truth decision"
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(repo_root=ROOT)
    verify_report(report)
    report_text = _json_text(report)
    analysis_text = render_analysis(report)
    scorecard_text = render_scorecard(report)

    if args.write:
        for path in (args.report, args.analysis, args.scorecard):
            path.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_text, encoding="utf-8")
        args.analysis.write_text(analysis_text, encoding="utf-8")
        args.scorecard.write_text(scorecard_text, encoding="utf-8")
    else:
        committed = load_json(args.report)
        verify_report(committed)
        if canonical_json(committed) != canonical_json(report):
            raise SystemExit(
                "committed P2.3 report differs from the source-bound decision"
            )
        _check(args.report, report_text)
        _check(args.analysis, analysis_text)
        _check(args.scorecard, scorecard_text)

    print(
        "P2.3 Product Truth decision: PASS; "
        f"execution={report['execution_status']}; "
        f"outcome={report['outcome']}; "
        f"valid_tasks={report['measured_facts']['valid_tasks']}; "
        f"scored_runs={report['measured_facts']['full_pilot_executed_runs']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
