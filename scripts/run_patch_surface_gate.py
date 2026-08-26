#!/usr/bin/env python3
"""Run the frozen reviewed PatchRequestPlan surface contract."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docmancer.docs.domain.patch_request_plan import build_patch_request_plan

CASES_PATH = ROOT / "eval" / "patch_request_surface_v1" / "cases.json"


def main() -> int:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise SystemExit("patch surface gate: invalid schema_version")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 20:
        raise SystemExit("patch surface gate: expected exactly 20 cases")
    if [case.get("id") for case in cases] != list(range(1, 21)):
        raise SystemExit("patch surface gate: IDs must be unique and contiguous 1..20")

    failures: list[str] = []
    for case in cases:
        plan = build_patch_request_plan(str(case["question"]))
        observed = {
            "operation": plan.operation,
            "mutation_targets": [item.value for item in plan.mutation_targets],
            "preserve_targets": [item.value for item in plan.preserve_targets],
            "destination": plan.destination.value if plan.destination else None,
            "parent_context": plan.parent_context.value if plan.parent_context else None,
            "language": plan.language,
            "unresolved": list(plan.unresolved_parts),
        }
        expected = {key: case[key] for key in observed}
        if observed != expected:
            failures.append(
                f"case {case['id']:02d} {case['question']!r}: "
                f"observed={observed!r}, expected={expected!r}"
            )

    if failures:
        print("patch surface gate: FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("patch surface gate: PASS (20/20 expected outcomes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
