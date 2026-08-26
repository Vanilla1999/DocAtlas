#!/usr/bin/env python3
"""Run the frozen reviewed Russian semantic-question surface contract."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract

CASES_PATH = ROOT / "eval" / "project_answer_surface_v2" / "cases.json"
SEMANTIC_RELATIONS = {
    "decision_for_action", "argument_value", "applicable_contract",
    "purpose_behavior", "behavior_before",
}


def main() -> int:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise SystemExit("question surface v2 gate: invalid schema_version")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 12:
        raise SystemExit("question surface v2 gate: expected exactly 12 cases")
    if [case.get("id") for case in cases] != list(range(1, 13)):
        raise SystemExit("question surface v2 gate: IDs must be unique and contiguous 1..12")

    failures: list[str] = []
    for case in cases:
        contract = build_project_answer_contract(str(case["question"]))
        rows = [
            row for row in contract.proof_obligations
            if row.relation in SEMANTIC_RELATIONS
        ]
        expected_relation = case["relation"]
        errors: list[str] = []
        if expected_relation is None:
            if rows:
                errors.append(f"unexpected semantic rows={rows!r}")
        elif len(rows) != 1:
            errors.append(f"semantic row count={len(rows)}, expected=1")
        else:
            row = rows[0]
            observed = (row.relation, row.subject, row.target)
            expected = (expected_relation, case["subject"], case["target"])
            if observed != expected:
                errors.append(f"signature={observed!r}, expected={expected!r}")
            if (row.query_span_start, row.query_span_end) != (0, len(case["question"])):
                errors.append("semantic row is not rebound to the exact full source span")
            if not any(
                trace.startswith("surface:semantic:")
                for trace in contract.parse_trace
            ):
                errors.append("missing semantic surface trace")
        if errors:
            failures.append(
                f"case {case['id']:02d} {case['question']!r}: " + "; ".join(errors)
            )

    if failures:
        print("question surface v2 gate: FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("question surface v2 gate: PASS (12/12 expected outcomes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
