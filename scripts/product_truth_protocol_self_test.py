#!/usr/bin/env python3
from __future__ import annotations

import copy
from pathlib import Path

from eval.product_truth_v1.protocol import (
    load_json,
    validate_ledger,
    validate_protocol,
    validate_repository,
    validate_result_semantics,
    validate_task_run_binding,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "eval" / "product_truth_v1"


def expect_error(fragment: str, action) -> None:
    try:
        action()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(f"expected {fragment!r}, got {str(exc)!r}") from exc
    else:
        raise AssertionError(f"expected verifier error containing {fragment!r}")


def main() -> int:
    validate_repository(REPO_ROOT)
    protocol = load_json(ROOT / "protocol.lock.json")
    task = load_json(ROOT / "fixtures" / "sample-task.json")
    run = load_json(ROOT / "fixtures" / "sample-run.json")
    result = load_json(ROOT / "fixtures" / "sample-result.json")
    ledger = load_json(ROOT / "fixtures" / "sample-ledger.json")

    mutated = copy.deepcopy(protocol)
    mutated["canary"]["product_claim_allowed"] = True
    mutated["protocol_sha256"] = protocol["protocol_sha256"]
    expect_error("digest mismatch", lambda: validate_protocol(mutated))

    mutated = copy.deepcopy(protocol)
    mutated["decision_rules"]["correctness_path"][
        "minimum_absolute_correct_patch_gain"
    ] = 0.0
    mutated.pop("protocol_sha256")
    from eval.product_truth_v1.protocol import protocol_sha256

    mutated["protocol_sha256"] = protocol_sha256(mutated)
    expect_error("gain threshold", lambda: validate_protocol(mutated))

    broken_run = copy.deepcopy(run)
    broken_run["budget_enforcement"]["observed_turns"] = (
        broken_run["budgets"]["max_turns"] + 1
    )
    expect_error(
        "exceeded hard budget",
        lambda: validate_task_run_binding(task, broken_run),
    )

    broken_result = copy.deepcopy(result)
    broken_result["gates"]["hidden_tests_passed"] = False
    expect_error(
        "six-gate outcome",
        lambda: validate_result_semantics(broken_result),
    )

    broken_ledger = copy.deepcopy(ledger)
    broken_ledger["events"][1]["previous_event_sha256"] = "f" * 64
    expect_error("hash chain", lambda: validate_ledger(broken_ledger))

    print("P2 Product Truth protocol self-test: PASS (5 fail-closed mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
