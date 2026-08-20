#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.model_report_contract import (
    ReportContractError,
    seal_report,
    self_test,
    validate_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seal and verify an Agent Developer model benchmark report",
    )
    parser.add_argument("report", nargs="?", type=Path)
    parser.add_argument("--expected-model")
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        print("Agent Developer model report contract: SELF-TEST PASS")
        return 0
    if args.report is None:
        parser.error("report path is required unless --self-test is used")
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if args.seal:
            report = seal_report(report)
            args.report.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        summary = validate_report(
            report,
            expected_model=args.expected_model,
            min_pass_rate=args.min_pass_rate,
            require_full=not args.allow_partial,
        )
    except (OSError, json.JSONDecodeError, ReportContractError) as exc:
        print(f"Agent Developer model report contract: FAIL: {exc}")
        return 1

    print(
        "Agent Developer model report contract: PASS; "
        f"{summary['passed_tasks']}/{summary['task_count']} tasks; "
        f"scope={summary['scope_accuracy']:.3f}; "
        f"recovery={summary['recovery_accuracy']:.3f}; "
        f"model={summary['model']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
