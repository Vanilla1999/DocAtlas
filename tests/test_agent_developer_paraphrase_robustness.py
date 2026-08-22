from __future__ import annotations

import copy
from pathlib import Path

import pytest

from eval.agent_developer_v1.paraphrase_robustness import (
    load_json,
    render_markdown,
    run_protocol,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "eval/agent_developer_v1/paraphrase_robustness_cases.json"
REPORT = ROOT / "eval/agent_developer_v1/results/paraphrase-robustness.json"
MARKDOWN = ROOT / "docs/analysis/p1.4-paraphrase-proofability.md"


def generated() -> dict:
    return run_protocol(load_json(CORPUS))


def test_committed_paraphrase_report_is_reproducible() -> None:
    report = generated()
    assert report == load_json(REPORT)
    assert MARKDOWN.read_text(encoding="utf-8") == render_markdown(report)


def test_core_categories_and_negative_controls_close() -> None:
    report = generated()
    for category in (
        "exact_identifier",
        "behavior",
        "requirements",
        "policy",
        "negative_control",
    ):
        metric = report["categories"][category]
        assert metric["rate"] == 1.0
        assert metric["threshold_met"] is True
    assert report["all_thresholds_met"] is True


def test_typo_and_alias_metrics_are_independent() -> None:
    report = generated()
    for category in ("typo", "alias"):
        metric = report["categories"][category]
        assert metric["case_count"] == 2
        assert metric["rate"] >= 0.5
        assert metric["threshold_met"] is True


def test_negative_controls_never_become_supported() -> None:
    report = generated()
    negatives = [row for row in report["cases"] if not row["positive"]]
    assert len(negatives) == 3
    assert all(row["status"] != "ok" for row in negatives)
    assert report["false_supported"] == 0


def test_source_scope_contamination_is_zero() -> None:
    report = generated()
    assert report["forbidden_source_contamination"] == 0
    assert all(not row["forbidden_source_contamination"] for row in report["cases"])
    positives = [row for row in report["cases"] if row["positive"] and row["passed"]]
    assert all(row["required_source"] in row["sources"] for row in positives)


def test_paraphrase_report_mutations_fail_closed() -> None:
    report = generated()

    unsafe = copy.deepcopy(report)
    unsafe["false_supported"] = 1
    with pytest.raises(ValueError, match="false support"):
        validate_report(unsafe)

    relaxed = copy.deepcopy(report)
    relaxed["claim_boundary"]["support_precision_relaxed"] = True
    with pytest.raises(ValueError, match="support precision"):
        validate_report(relaxed)

    promoted = copy.deepcopy(report)
    promoted["claim_boundary"]["product_maturity"] = "Stable"
    with pytest.raises(ValueError, match="maturity"):
        validate_report(promoted)
