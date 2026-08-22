from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval.agent_developer_v1.first_divergence import (
    EXPECTED_FAILURE_COUNTS,
    build_atlas,
    load_json,
    render_markdown,
    validate_atlas,
)


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "eval/agent_developer_v1/tasks.json"
ORACLE = ROOT / "eval/agent_developer_v1/expected_trajectories.json"
REPORT = ROOT / "eval/agent_developer_v1/results/model-benchmark.json"
ATLAS = ROOT / "eval/agent_developer_v1/results/first-divergence-atlas.json"
MARKDOWN = ROOT / "docs/analysis/p1.2-agent-developer-first-divergence.md"


def generated() -> dict:
    return build_atlas(load_json(TASKS), load_json(ORACLE), load_json(REPORT))


def test_committed_atlas_is_exactly_reproducible() -> None:
    atlas = generated()
    assert atlas == load_json(ATLAS)
    assert MARKDOWN.read_text(encoding="utf-8") == render_markdown(atlas)


def test_all_frozen_tasks_have_complete_first_divergence_records() -> None:
    atlas = generated()
    validate_atlas(atlas)
    assert atlas["summary"]["task_count"] == 11
    assert atlas["summary"]["passed_tasks"] == 0
    assert atlas["summary"]["failure_class_counts"] == dict(
        sorted(EXPECTED_FAILURE_COUNTS.items())
    )
    assert atlas["summary"]["false_supported"] == 0
    assert atlas["summary"]["forbidden_source_contamination"] == 0
    assert all(row["expected_trajectory"] for row in atlas["tasks"])
    assert all(row["request_evidence"]["turn_count"] >= 1 for row in atlas["tasks"])


def test_dominant_failure_is_pre_mcp_selector_validation() -> None:
    atlas = generated()
    selector_rows = [
        row
        for row in atlas["tasks"]
        if row["first_divergence"]["failure_class"]
        == "selector_cardinality_invalid"
    ]
    assert len(selector_rows) == 8
    assert all(row["actual_trajectory"] == [] for row in selector_rows)
    assert all(
        row["first_divergence"]["stage"] == "model_format"
        for row in selector_rows
    )
    assert all(
        row["first_divergence"]["repair_surface"]
        == "agent_or_host_argument_normalization"
        for row in selector_rows
    )


def test_working_path_hypothesis_is_not_rewritten_as_a_fact() -> None:
    atlas = generated()
    findings = atlas["findings"]
    assert findings["working_path_was_model_visible"] is True
    assert findings["missing_working_path_is_established_root_cause"] is False
    assert findings["public_api_change_is_justified_by_p1_2"] is False
    assert atlas["claim_boundary"]["autonomous_agent_truth_closed"] is False
    assert all(
        row["first_divergence"]["public_api_change_required"] is False
        for row in atlas["tasks"]
    )


def test_report_identity_or_false_support_drift_fails_closed() -> None:
    tasks = load_json(TASKS)
    oracle = load_json(ORACLE)
    report = load_json(REPORT)

    missing = copy.deepcopy(report)
    missing["tasks"] = missing["tasks"][:-1]
    with pytest.raises(ValueError, match="identities differ"):
        build_atlas(tasks, oracle, missing)

    unsafe = copy.deepcopy(report)
    unsafe["false_supported"] = 1
    with pytest.raises(ValueError, match="false support"):
        build_atlas(tasks, oracle, unsafe)


def test_atlas_mutation_cannot_authorize_public_api_or_agent_truth() -> None:
    atlas = generated()

    public_api = copy.deepcopy(atlas)
    public_api["tasks"][0]["first_divergence"]["public_api_change_required"] = True
    with pytest.raises(ValueError, match="public API change"):
        validate_atlas(public_api)

    closed = copy.deepcopy(atlas)
    closed["claim_boundary"]["autonomous_agent_truth_closed"] = True
    with pytest.raises(ValueError, match="Autonomous Agent Truth"):
        validate_atlas(closed)


def test_markdown_preserves_historical_evidence_boundary() -> None:
    text = render_markdown(generated())
    assert "committed historical real-model" in text
    assert "does not reconstruct rejected model actions" in text
    assert "8/11" in text
    assert "does **not** establish missing working-path visibility" in text
    assert "Fresh installed provider capture" in text
    assert "Product maturity: remains Beta" in text
