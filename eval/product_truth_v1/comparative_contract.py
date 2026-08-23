from __future__ import annotations

from typing import Any

from eval.product_truth_v1.comparative import EXPECTED_CONDITIONS, verify_report as verify_base_report


EXPECTED_FLAGS = {
    "A_repo_only": {
        "docatlas": False,
        "external_docs": False,
        "code_context_engine": False,
    },
    "B_repo_plus_docatlas": {
        "docatlas": True,
        "external_docs": False,
        "code_context_engine": False,
    },
    "C_repo_plus_external_docs": {
        "docatlas": False,
        "external_docs": True,
        "code_context_engine": False,
    },
    "D_code_context_plus_docatlas": {
        "docatlas": True,
        "external_docs": False,
        "code_context_engine": True,
    },
}
EXPECTED_RANDOMIZATION = {
    "blinding": "hidden tests and gold/oracle artifacts remain evaluator-only",
    "condition_order": "deterministic_balanced_permutation",
    "seed": "docatlas-product-truth-v1",
    "unit": "task_model_repeat_block",
}


def verify_report(report: dict[str, Any]) -> None:
    """Verify the complete P2.2A cell contract even when no runs are authorized."""

    verify_base_report(report)
    conditions = report.get("conditions")
    if not isinstance(conditions, list) or tuple(
        row.get("id") for row in conditions
    ) != EXPECTED_CONDITIONS:
        raise ValueError("P2.2A condition identity or order changed")
    for row in conditions:
        condition_id = str(row["id"])
        actual = {
            key: row.get(key)
            for key in ("docatlas", "external_docs", "code_context_engine")
        }
        if actual != EXPECTED_FLAGS[condition_id]:
            raise ValueError(f"P2.2A condition capability drift: {condition_id}")
    if report.get("randomization") != EXPECTED_RANDOMIZATION:
        raise ValueError("P2.2A randomization contract mismatch")


__all__ = ["EXPECTED_FLAGS", "EXPECTED_RANDOMIZATION", "verify_report"]
