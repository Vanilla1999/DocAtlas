from __future__ import annotations

from eval.task_level.context.patch_constraints import PatchConstraint, PatchConstraintPacket
from eval.task_level.evaluators.constraint_validation import validate_patch_against_constraints


def _packet(constraint: PatchConstraint) -> PatchConstraintPacket:
    return PatchConstraintPacket(
        task_id="t",
        constraints=[constraint],
        suggested_checks=[],
        warnings=[],
        source_summary=[],
        token_estimate=10,
    )


def test_constraint_validation_detects_generated_file_edit():
    packet = _packet(PatchConstraint(
        id="generated",
        type="generated_file",
        instruction="Do not hand-edit generated files.",
        source="docs/generated-files.md",
        severity="must",
        confidence="high",
        symbols=["*.g.dart"],
        files=["docs/generated-files.md"],
    ))

    result = validate_patch_against_constraints(packet=packet, changed_files=["lib/model/permission_info.g.dart"])

    assert result["constraint_validation"]["violated"] == 1


def test_constraint_validation_detects_lockfile_edit():
    packet = _packet(PatchConstraint(
        id="dep",
        type="dependency_version",
        instruction="Use pinned permission_handler version.",
        source="pubspec.lock",
        severity="must",
        confidence="high",
        symbols=["permission_handler"],
        files=["pubspec.lock"],
    ))

    result = validate_patch_against_constraints(packet=packet, changed_files=["pubspec.lock"])

    assert result["constraint_validation"]["violated"] == 1


def test_constraint_validation_detects_forbidden_provider_policy_edit():
    packet = _packet(PatchConstraint(
        id="owner",
        type="architecture",
        instruction="Policy says service/source of truth owns behavior; provider/UI layers should delegate.",
        source="docs/permission-architecture.md",
        severity="must",
        confidence="high",
        symbols=["PermissionService"],
        files=["lib/modules/permission/application/permission_service.dart"],
    ))

    result = validate_patch_against_constraints(packet=packet, changed_files=["lib/modules/permission/presentation/permission_provider.dart"])

    assert result["constraint_validation"]["violated"] == 1


def test_constraint_validation_allows_source_of_truth_edit():
    packet = _packet(PatchConstraint(
        id="source",
        type="source_of_truth",
        instruction="Edit the service source of truth.",
        source="docs/permission-architecture.md",
        severity="must",
        confidence="high",
        symbols=["PermissionService"],
        files=["lib/modules/permission/application/permission_service.dart"],
    ))

    result = validate_patch_against_constraints(packet=packet, changed_files=["lib/modules/permission/application/permission_service.dart"])

    assert result["constraint_validation"]["satisfied"] == 1
    assert result["constraint_validation"]["violated"] == 0


def test_constraint_validation_marks_unknown_when_not_deterministic():
    packet = _packet(PatchConstraint(
        id="manual-review",
        type="forbidden_edit",
        instruction="Do not duplicate policy in unrelated code.",
        source="docs/permission-architecture.md",
        severity="must",
        confidence="medium",
        symbols=[],
        files=[],
    ))

    result = validate_patch_against_constraints(packet=packet, changed_files=["lib/modules/permission/domain/service.dart"])

    assert result["constraint_validation"]["unknown"] == 1
