from __future__ import annotations

import copy
from pathlib import Path

import pytest

from eval.agent_developer_v1.contract_v2_ablation import (
    build_ablation,
    load_json,
    render_markdown,
    validate_ablation,
)


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "eval/agent_developer_v1/results/first-divergence-atlas.json"
REPORT = ROOT / "eval/agent_developer_v1/results/contract-v2-ablation.json"
MARKDOWN = ROOT / "docs/analysis/p1.3-agent-contract-v2-ablation.md"


def generated() -> dict:
    return build_ablation(load_json(ATLAS))


def test_committed_ablation_is_exactly_reproducible() -> None:
    report = generated()
    assert report == load_json(REPORT)
    assert MARKDOWN.read_text(encoding="utf-8") == render_markdown(report)


def test_working_path_visibility_has_zero_incremental_gain() -> None:
    report = generated()
    by_id = {row["id"]: row for row in report["candidates"]}
    row = by_id["working_path_visible"]
    assert row["counterfactual_primary_divergences_addressed"] == 0
    assert row["decision"] == "reject_as_redundant"
    assert report["source"]["task_count"] == 11


def test_host_selector_normalization_addresses_the_dominant_class() -> None:
    report = generated()
    by_id = {row["id"]: row for row in report["candidates"]}
    row = by_id["host_selector_normalization"]
    assert row["counterfactual_primary_divergences_addressed"] == 8
    assert row["counterfactual_residual_primary_divergences"] == 3
    assert row["public_contract_change"] is False
    assert row["server_authority_expansion"] is False
    assert row["decision"] == "accept_for_next_live_ablation"


def test_server_inference_and_continuation_token_are_rejected() -> None:
    report = generated()
    by_id = {row["id"]: row for row in report["candidates"]}
    inference = by_id["server_owned_scope_module_inference"]
    token = by_id["opaque_continuation_token"]
    assert inference["decision"] == "reject"
    assert inference["server_authority_expansion"] is True
    assert inference["public_contract_change"] is True
    assert token["decision"] == "reject"
    assert token["counterfactual_primary_divergences_addressed"] == 0
    assert token["new_state_surface"] is True


def test_no_public_contract_change_is_approved() -> None:
    report = generated()
    assert report["decision"]["accepted_public_contract_changes"] == []
    assert report["decision"]["public_agent_contract_v2"] == "no_change"
    assert report["safety"]["candidate_false_support_delta_claimed"] is False
    assert report["safety"]["candidate_contamination_delta_claimed"] is False
    assert report["claim_boundary"]["autonomous_agent_truth_closed"] is False
    assert report["claim_boundary"]["product_maturity"] == "Beta"


def test_ablation_mutations_fail_closed() -> None:
    report = generated()

    unsafe = copy.deepcopy(report)
    unsafe["decision"]["accepted_public_contract_changes"] = [
        "server_owned_scope_module_inference"
    ]
    with pytest.raises(ValueError, match="public contract change"):
        validate_ablation(unsafe)

    false_safety = copy.deepcopy(report)
    false_safety["safety"]["candidate_false_support_delta_claimed"] = True
    with pytest.raises(ValueError, match="false-support safety"):
        validate_ablation(false_safety)

    closed = copy.deepcopy(report)
    closed["claim_boundary"]["autonomous_agent_truth_closed"] = True
    with pytest.raises(ValueError, match="Autonomous Agent Truth"):
        validate_ablation(closed)
