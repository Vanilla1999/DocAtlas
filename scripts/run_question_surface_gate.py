#!/usr/bin/env python3
"""Run the frozen 100-case Project Docs question-surface contract."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_plan import compile_question_plan

CASES_PATH = ROOT / "eval" / "project_answer_surface_v1" / "cases.json"
SIGNATURE_FIELDS = (
    "kind", "subject", "attribute", "relation", "target", "value_kind",
    "expected_value", "item_kind", "cardinality", "response_mode", "context",
)


def _signature(contract: Any) -> list[dict[str, Any]]:
    return [
        {field: getattr(row, field) for field in SIGNATURE_FIELDS}
        for row in contract.proof_obligations
    ]


def _owner(question: str, contract: Any) -> str:
    if contract.unresolved_parts:
        return "unsupported"
    plan = compile_question_plan(question)
    if plan.facets:
        return "question_plan"
    if contract.proof_obligations:
        return "legacy"
    return "silent_empty"


def main() -> int:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise SystemExit("question surface gate: invalid schema_version")
    if tuple(payload.get("signature_fields", ())) != SIGNATURE_FIELDS:
        raise SystemExit("question surface gate: signature field schema drift")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 100:
        raise SystemExit("question surface gate: expected exactly 100 cases")
    ids = [case.get("id") for case in cases]
    if ids != list(range(1, 101)):
        raise SystemExit("question surface gate: IDs must be unique and contiguous 1..100")
    categories = Counter(str(case.get("category", "")) for case in cases)
    if len(categories) != 10 or set(categories.values()) != {10}:
        raise SystemExit(
            f"question surface gate: expected ten 10-case categories, got {dict(categories)}"
        )

    failures: list[str] = []
    observed_owners: Counter[str] = Counter()
    passed_by_category: Counter[str] = Counter()
    for case in cases:
        ident = int(case["id"])
        category = str(case["category"])
        question = str(case["question"])
        contract = build_project_answer_contract(question)
        owner = _owner(question, contract)
        observed_owners[owner] += 1
        signature = _signature(contract)
        unresolved = list(contract.unresolved_parts)

        errors: list[str] = []
        if owner == "silent_empty":
            errors.append("silent-empty contract")
        if owner != case["expected_owner"]:
            errors.append(f"owner={owner!r}, expected={case['expected_owner']!r}")
        if signature != case["expected_signature"]:
            errors.append(
                f"signature={signature!r}, expected={case['expected_signature']!r}"
            )
        if unresolved != case["expected_unresolved"]:
            errors.append(
                f"unresolved={unresolved!r}, expected={case['expected_unresolved']!r}"
            )
        if errors:
            failures.append(f"case {ident:03d} {question!r}: " + "; ".join(errors))
        else:
            passed_by_category[category] += 1

    for category in sorted(categories):
        print(f"{category}: {passed_by_category[category]}/{categories[category]}")
    print("owners:", ", ".join(f"{k}={v}" for k, v in sorted(observed_owners.items())))

    if failures:
        print("question surface gate: FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("question surface gate: PASS (100/100 expected outcomes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
