#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.installed_mcp_report import (
    InstalledMCPReportError,
    load_and_verify,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify an installed-MCP Agent benchmark report"
    )
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--expected-origin",
        choices=("reviewed-wheel", "public-pypi"),
    )
    parser.add_argument("--require-public", action="store_true")
    parser.add_argument("--min-task-count", type=int, default=1)
    parser.add_argument("--min-pass-rate", type=float, default=0.0)
    parser.add_argument("--require-schema-repair", action="store_true")
    args = parser.parse_args(argv)
    if args.min_task_count < 1:
        parser.error("--min-task-count must be positive")
    if not 0.0 <= args.min_pass_rate <= 1.0:
        parser.error("--min-pass-rate must be between 0 and 1")
    try:
        summary = load_and_verify(
            args.report,
            expected_origin=args.expected_origin,
            require_public=args.require_public,
            min_task_count=args.min_task_count,
            min_pass_rate=args.min_pass_rate,
            require_schema_repair=args.require_schema_repair,
        )
    except InstalledMCPReportError as exc:
        print(f"Installed MCP report verification: FAIL: {exc}")
        return 1
    print("Installed MCP report verification: PASS")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
