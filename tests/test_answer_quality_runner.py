from __future__ import annotations

import json
from pathlib import Path

from eval import answer_quality_runner as runner


def test_patch_source_path_validation_is_snapshot_bound():
    projection = {"sources": [{"evidence_id": "ev-1", "path": "src/auth.py"}]}
    snapshot = {"ev-1": {"path": "src/auth.py"}}
    contract = {"acceptable_evidence": ["src/auth.py"]}

    assert runner._validate_patch_source_paths(projection, snapshot, contract) == []

    projection["sources"][0]["path"] = "src/legacy_auth.py"
    assert runner._validate_patch_source_paths(projection, snapshot, contract) == [
        "citation:path_mismatch",
        "citation:unacceptable_evidence:src/legacy_auth.py",
        "citation:acceptable_evidence_missing:src/auth.py",
    ]


def test_integrity_gate_requires_the_specific_snapshot_binding_error(monkeypatch):
    inputs = {
        "docs_answer": (
            {"sources": [{"path_or_url": "docs/auth.md"}]},
            {},
            800,
        ),
        "patch_context": (
            {"sources": [{"path": "src/auth.py"}]},
            {},
            800,
        ),
    }
    monkeypatch.setattr(
        runner,
        "validate_model_visible_projection",
        lambda *_args, **_kwargs: ["projection estimate mismatch or budget exceeded"],
    )

    report = runner._run_integrity_mutation_gate(inputs)

    assert report["status"] == "FAIL"
    assert report["checks"]["docs_answer"]["passed"] is False
    assert report["checks"]["patch_context"]["passed"] is False


def test_integrity_gate_accepts_explicit_snapshot_binding_rejections(monkeypatch):
    inputs = {
        "docs_answer": (
            {"sources": [{"path_or_url": "docs/auth.md"}]},
            {},
            800,
        ),
        "patch_context": (
            {"sources": [{"path": "src/auth.py"}]},
            {},
            800,
        ),
    }

    def reject_path(projection, **_kwargs):
        source = projection["sources"][0]
        key = "path" if "path" in source else "path_or_url"
        return [f"projection source {key} does not match the internal snapshot"]

    monkeypatch.setattr(runner, "validate_model_visible_projection", reject_path)

    report = runner._run_integrity_mutation_gate(inputs)

    assert report["status"] == "PASS"
    assert report["checks"]["docs_answer"]["passed"] is True
    assert report["checks"]["patch_context"]["passed"] is True


def test_checked_provider_free_observation_fails_closed():
    data = Path("eval/answer_quality")
    result = json.loads((data / "result_v1.json").read_text(encoding="utf-8"))
    baseline = json.loads((data / "baseline_v1.json").read_text(encoding="utf-8"))
    human = json.loads(
        (data / "human_review_inputs_v1.json").read_text(encoding="utf-8")
    )

    failed = {row["contract_id"] for row in result["results"] if not row["passed"]}
    assert failed == {
        "t39-adv-legal-distractor",
        "t42-patch-identifier-boundary",
    }
    assert result["provider_free_verdict"] == "FAIL"
    assert result["integrity_mutation_gate"]["status"] == "FAIL"
    assert result["frozen_baseline_pareto_gate"]["status"] == "FAIL"
    assert result["lower_layers"]["task39"]["status"] == "PASS"
    assert result["lower_layers"]["task42"]["status"] == "PASS"
    assert (
        result["lower_layers"]["task42"]["candidate_order_permutation_gate"]
        == "PASS"
    )
    assert "retrieval_projection_p95_ms" not in result["groups"]["docs_answer"]
    assert "retrieval_projection_p95_ms" in baseline["groups"]["docs_answer"]
    assert human["review_status"] == "PENDING_HUMAN_REVIEW"
    assert baseline["deterministic_result_digest"] == result[
        "deterministic_result_digest"
    ] == human["deterministic_result_digest"]
