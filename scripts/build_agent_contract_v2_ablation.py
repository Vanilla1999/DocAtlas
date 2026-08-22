#!/usr/bin/env python3
"""Generate or verify the reproducible P1.3 ablation decision."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.contract_v2_ablation import (
    build_ablation,
    load_json,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ATLAS = ROOT / "eval/agent_developer_v1/results/first-divergence-atlas.json"
DEFAULT_REPORT = ROOT / "eval/agent_developer_v1/results/contract-v2-ablation.json"
DEFAULT_MARKDOWN = ROOT / "docs/analysis/p1.3-agent-contract-v2-ablation.md"


def _json_text(value: object) -> str:
    """Use one stable representation for generation and drift checking."""
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _check(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing generated P1.3 artifact: {path}")
    if path.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"generated P1.3 artifact drift: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the P1.3 contract ablation")
    parser.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    report = build_ablation(load_json(args.atlas))
    report_text = _json_text(report)
    markdown_text = render_markdown(report)
    if args.check:
        _check(args.report, report_text)
        _check(args.markdown, markdown_text)
        print("Agent Contract v2 ablation: CHECK PASS")
        return 0

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text, encoding="utf-8")
    args.markdown.write_text(markdown_text, encoding="utf-8")
    print(json.dumps(report["decision"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
