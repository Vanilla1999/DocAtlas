from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.evaluators.actionability import evaluate_actionability
from eval.task_level.evaluators.contract import ContractEvaluation
from eval.task_level.schemas import TaskSpec
from eval.task_level.task33_pilot import TASK33C_PILOT_TASK_ID, TASK33C_REQUIRED_TARGET_PATHS


def _task() -> TaskSpec:
    return TaskSpec(
        task_id=TASK33C_PILOT_TASK_ID,
        task_type="curated",
        suite="decisive",
        repo="fixture://task33",
        base_commit="fixture-base",
        issue_text="Problem first. Fix the shared permission gate.",
        language="dart",
        ecosystem="dart",
        dependencies=(),
        setup_command="",
        test_command="pytest",
    )


def test_actionability_uses_model_visible_packet_instead_of_missing_legacy_checklist(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sources = [
        {"evidence_id": "permission", "path": "docs/permission-architecture.md"},
        {"evidence_id": "browser", "path": "docs/browser-flow.md"},
        {"evidence_id": "scan", "path": "docs/scan-flow.md"},
        {"evidence_id": "sync", "path": "docs/offline-sync.md"},
    ]
    projection = {
        "status": "ok",
        "kind": "patch_context",
        "estimated_tokens": 1_944,
        "mutation_ready": True,
        "edit_ready": True,
        "sources": sources,
        "targets": {"likely_files": [{"path": path} for path in TASK33C_REQUIRED_TARGET_PATHS], "symbols": []},
        "invariants": [
            {"text": "PermissionService evaluateFlowEntry returns PermissionDecision.", "evidence_ids": ["permission"]},
            {"text": "BrowserPermissionGate delegates to evaluateFlowEntry.", "evidence_ids": ["browser"]},
            {"text": "ScanPermissionGate delegates to evaluateFlowEntry.", "evidence_ids": ["scan"]},
            {"text": "OfflineSyncGate uses evaluateFlowEntry before accepting work.", "evidence_ids": ["sync"]},
        ],
        "implementation_guidance": [],
        "acceptance_conditions": [],
        "checks": {"compile": [], "tests": [], "semantic_checks": []},
        "omitted_counts": {},
    }
    (run_dir / "model_visible_patch_context.json").write_text(
        json.dumps(projection), encoding="utf-8"
    )
    (run_dir / "patch.diff").write_text("", encoding="utf-8")

    result = evaluate_actionability(
        task=_task(),
        condition_id="docatlas_bounded_direct",
        run_output_dir=run_dir,
        patch_path=run_dir / "patch.diff",
        trajectory_path=None,
        contract=ContractEvaluation(1.0, 1.0, 1.0),
    )

    assert result.metric_source == "model_visible_action_packet"
    assert result.requirement_recall == 1.0
    assert result.requirement_precision == 1.0
    assert result.critical_invariant_recall == 1.0
    assert result.source_coverage == 1.0
    assert result.behavioral_scope_coverage == 1.0
    assert result.citation_fidelity == 1.0
    assert result.projection_status == "ok"
    assert result.projection_tokens == 1_944
    assert result.mutation_ready is True
    assert result.model_visible_omissions == 0
    # Compatibility metrics must no longer become zero merely because the
    # obsolete action_checklist.json artifact was not written.
    assert result.critical_contract_recall == 1.0
    assert result.critical_contract_salience == 1.0
    assert result.action_checklist_precision == 1.0
    assert result.action_checklist_used is True


def test_successful_projection_without_mutation_readiness_is_explicitly_flagged(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "model_visible_patch_context.json").write_text(
        json.dumps({
            "status": "ok",
            "kind": "patch_context",
            "estimated_tokens": 500,
            "mutation_ready": False,
            "edit_ready": False,
            "sources": [],
            "targets": {"likely_files": [], "symbols": []},
            "invariants": [],
            "implementation_guidance": [],
            "acceptance_conditions": [],
            "checks": {},
            "omitted_counts": {"mandatory_requirements": 1},
        }),
        encoding="utf-8",
    )
    (run_dir / "patch.diff").write_text("", encoding="utf-8")

    result = evaluate_actionability(
        task=_task(),
        condition_id="docatlas_bounded_direct",
        run_output_dir=run_dir,
        patch_path=run_dir / "patch.diff",
        trajectory_path=None,
        contract=ContractEvaluation(0.0, 0.0, 0.0),
    )

    assert result.mutation_ready is False
    assert result.model_visible_omissions == 1
    assert "successful_projection_without_mutation_readiness" in result.warnings
