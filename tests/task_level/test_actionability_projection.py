from __future__ import annotations

import json
from pathlib import Path

from docmancer.docs.application.action_packet import build_action_packet
from docmancer.docs.application.model_visible_projection import project_patch_context
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


def _write_valid_projection(run_dir: Path) -> dict:
    doc_rows = [
        (
            "docs/permission-architecture.md",
            "PermissionService.evaluateFlowEntry must return a PermissionDecision.",
        ),
        ("docs/browser-flow.md", "BrowserPermissionGate must delegate to evaluateFlowEntry."),
        ("docs/scan-flow.md", "ScanPermissionGate must delegate to evaluateFlowEntry."),
        ("docs/offline-sync.md", "OfflineSyncGate must use evaluateFlowEntry before accepting work."),
    ]
    evidence = [
        {
            "path": path,
            "source": path,
            "source_class": "project_doc",
            "authority": "project_rule",
            "content": text,
        }
        for path, text in doc_rows
    ]
    evidence.extend({
        "path": path,
        "source": path,
        "source_class": "project_file",
        "authority": "supporting",
        "content": f"class {Path(path).stem} {{}}",
        "matched": True,
    } for path in TASK33C_REQUIRED_TARGET_PATHS)
    packet = build_action_packet(
        question="Problem first. Fix the shared permission gate.",
        context_pack=evidence,
        trust_contract={"selected": [], "risky": [], "rejected": []},
        max_tokens=2_000,
        project_path="/repo",
        required_evidence_paths=[path for path, _ in doc_rows],
        required_target_paths=TASK33C_REQUIRED_TARGET_PATHS,
        behavioral_contract_required=True,
    )
    projection, snapshot = project_patch_context(
        packet=packet,
        evidence_items=evidence,
        max_tokens=2_000,
    )
    (run_dir / "model_visible_patch_context.json").write_text(
        json.dumps(projection), encoding="utf-8"
    )
    (run_dir / "model_visible_evidence_snapshot.json").write_text(
        json.dumps(snapshot), encoding="utf-8"
    )
    return projection


def test_actionability_uses_model_visible_packet_instead_of_missing_legacy_checklist(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    projection = _write_valid_projection(run_dir)
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
    assert result.projection_tokens == projection["estimated_tokens"]
    assert result.mutation_ready is True
    assert result.model_visible_omissions == 0
    assert result.critical_contract_recall == 0.0
    assert result.critical_contract_salience == 0.0
    assert result.action_checklist_precision == 0.0
    assert result.action_checklist_used is False


def test_unvalidated_projection_is_rejected_instead_of_scored(tmp_path: Path):
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

    assert result.metric_source == "invalid_model_visible_projection"
    assert result.projection_status == "invalid"
    assert result.mutation_ready is None
    assert any(
        warning.startswith("invalid_model_visible_projection:")
        for warning in result.warnings
    )
