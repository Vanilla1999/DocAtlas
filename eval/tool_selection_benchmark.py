from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from docmancer.docs.domain.tool_selection import select_public_docs_tool


DEFAULT_GOLDEN = Path(__file__).with_name("tool_selection_golden.yaml")


def load_cases(path: Path = DEFAULT_GOLDEN) -> list[dict[str, str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases: list[dict[str, str]] = []
    for group in data.get("groups") or []:
        expected = str(group["expected_tool"])
        for template in group.get("templates") or []:
            for subject in group.get("subjects") or []:
                cases.append({
                    "prompt": str(template).format(subject=subject),
                    "expected_tool": expected,
                })
    return cases


def evaluate(cases: list[dict[str, str]]) -> dict[str, Any]:
    rows = []
    correct = 0
    for case in cases:
        decision = select_public_docs_tool(case["prompt"])
        passed = decision.tool == case["expected_tool"]
        correct += int(passed)
        rows.append({
            **case,
            "selected_tool": decision.tool,
            "reason_code": decision.reason_code,
            "confidence": decision.confidence,
            "passed": passed,
        })
    total = len(rows)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "failures": [row for row in rows if not row["passed"]],
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--min-accuracy", type=float, default=0.95)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = evaluate(load_cases(args.golden))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["accuracy"] >= args.min_accuracy else 1


if __name__ == "__main__":
    raise SystemExit(main())
