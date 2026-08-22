#!/usr/bin/env python3
"""Generate or verify the P1.4 paraphrase/proofability evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.agent_developer_v1.paraphrase_robustness import (
    load_json,
    render_markdown,
    run_protocol,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "eval/agent_developer_v1/paraphrase_robustness_cases.json"
DEFAULT_REPORT = ROOT / "eval/agent_developer_v1/results/paraphrase-robustness.json"
DEFAULT_MARKDOWN = ROOT / "docs/analysis/p1.4-paraphrase-proofability.md"


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _check(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing P1.4 generated artifact: {path}")
    if path.read_text(encoding="utf-8") != expected:
        raise SystemExit(f"P1.4 generated artifact drift: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build P1.4 robustness evidence")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    report = run_protocol(load_json(args.corpus))
    report_text = _json_text(report)
    markdown_text = render_markdown(report)
    if args.check:
        _check(args.report, report_text)
        _check(args.markdown, markdown_text)
        print("P1.4 paraphrase/proofability robustness: CHECK PASS")
        return 0

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text, encoding="utf-8")
    args.markdown.write_text(markdown_text, encoding="utf-8")
    print(json.dumps(report["categories"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
