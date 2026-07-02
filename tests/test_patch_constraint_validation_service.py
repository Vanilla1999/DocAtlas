from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from docmancer.docs.application.patch_constraint_validation_service import PatchConstraintValidationService
from docmancer.docs.models import PatchConstraint, PatchConstraintPacket


def _constraint(
    constraint_id: str,
    type_: str,
    instruction: str,
    *,
    source: str = "docs/architecture.md",
    severity: str = "must",
    confidence: str = "high",
    evidence: str | None = None,
    files: list[str] | None = None,
    symbols: list[str] | None = None,
) -> PatchConstraint:
    return PatchConstraint(
        id=constraint_id,
        type=type_,
        instruction=instruction,
        source=source,
        severity=severity,
        confidence=confidence,
        evidence=evidence or instruction,
        files=files or [],
        symbols=symbols or [],
    )


def _service() -> PatchConstraintValidationService:
    return PatchConstraintValidationService()


def test_detects_generated_file_edit_violation():
    constraint = _constraint("generated", "generated_file", "Generated files *.g.dart must not be edited by hand.", files=["*.g.dart"])

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/user/user.g.dart"])

    assert result.violated == 1
    assert result.results[0].status == "violated"
    assert "generated" in result.results[0].reason.lower()


def test_detects_freezed_file_edit_violation():
    constraint = _constraint("generated", "generated_file", "Generated files *.freezed.dart must not be modified.", files=["*.freezed.dart"])

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/user/user.freezed.dart"])

    assert result.violated == 1
    assert result.results[0].files == ["lib/user/user.freezed.dart"]


def test_detects_lockfile_edit_violation():
    constraint = _constraint("lock", "forbidden_edit", "Do not change lockfile unless explicitly upgrading dependencies.", files=["pubspec.lock"])

    result = _service().validate_patch_against_constraints([constraint], changed_files=["pubspec.lock"])

    assert result.violated == 1
    assert "lockfile" in result.results[0].reason.lower()


def test_allows_lockfile_edit_for_explicit_dependency_upgrade_task():
    constraint = _constraint("lock", "forbidden_edit", "Do not change lockfile unless explicitly upgrading dependencies.", files=["pubspec.lock"])
    packet = PatchConstraintPacket(task="Upgrade permission_handler dependency", constraints=[constraint])

    result = _service().validate_patch_against_constraints(packet, changed_files=["pubspec.lock"])

    assert result.violated == 0
    assert result.unknown == 1
    assert "dependency-upgrade allowance" in result.results[0].reason.lower()


def test_allows_source_of_truth_file_edit():
    constraint = _constraint("owner", "source_of_truth", "Permission policy belongs in PermissionService / service layer, not provider/UI.", symbols=["PermissionService"])

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/permission/application/permission_service.dart"])

    assert result.satisfied == 1
    assert result.results[0].status == "satisfied"


def test_detects_provider_policy_edit_when_forbidden():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate permission policy; delegate to PermissionService.")
    diff = """
+ if (status == PermissionStatus.denied) {
+   canProceed = role == 'admin';
+ }
"""

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/permission/presentation/permission_provider.dart"], patch_diff=diff)

    assert result.violated == 1
    assert "provider/ui" in result.results[0].reason.lower()


def test_marks_provider_change_unknown_without_diff():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate permission policy; delegate to PermissionService.")

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/permission/presentation/permission_provider.dart"])

    assert result.unknown == 1
    assert result.results[0].status == "unknown"
    assert "diff unavailable" in result.results[0].reason.lower()


def test_marks_verification_constraint_unknown_without_test_evidence():
    constraint = _constraint("checks", "verification", "Run permission tests after editing.")

    result = _service().validate_patch_against_constraints([constraint], changed_files=["tests/test_permission.py"])

    assert result.unknown == 1
    assert "test evidence" in result.results[0].reason.lower()


def test_marks_semantic_behavior_constraint_for_manual_review_with_source_refs():
    constraint = _constraint(
        "designer-input",
        "behavior",
        "Keep the redesigned menu behavior aligned with the designer-approved interaction.",
    )
    constraint = PatchConstraint(
        **{**asdict(constraint), "source_refs": [{"path": "docs/menu.md", "line_start": 12, "line_end": 15}]}
    )

    result = _service().validate_patch_against_constraints(
        [constraint],
        changed_files=["lib/presentation/menu_view.dart"],
        patch_diff="+ showRedesignedMenu();\n",
    )

    assert result.manual_review == 1
    assert result.unknown == 0
    assert result.results[0].status == "manual_review"
    assert result.results[0].constraint_type == "behavior"
    assert result.results[0].source_refs == [{"path": "docs/menu.md", "line_start": 12, "line_end": 15}]
    assert "not mechanically decidable" in result.results[0].reason
    assert result.results[0].remediation


def test_deterministic_violation_cites_constraint_metadata_and_remediation():
    constraint = _constraint(
        "generated",
        "generated_file",
        "Generated files *.g.dart must not be edited by hand.",
        files=["*.g.dart"],
    )

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/user/user.g.dart"])

    assert result.violated == 1
    assert result.results[0].constraint_type == "generated_file"
    assert result.results[0].evidence == "Generated files *.g.dart must not be edited by hand."
    assert "Revert hand edits" in (result.results[0].remediation or "")


def test_summarizes_satisfied_violated_unknown_counts():
    constraints = [
        _constraint("generated", "generated_file", "Generated files *.g.dart must not be edited.", files=["*.g.dart"]),
        _constraint("owner", "source_of_truth", "Permission policy belongs in PermissionService / service layer, not provider/UI."),
        _constraint("checks", "verification", "Run tests."),
    ]

    result = _service().validate_patch_against_constraints(
        constraints,
        changed_files=["lib/user/user.g.dart", "lib/permission/service/permission_service.dart"],
    )

    assert result.total_constraints == 3
    assert result.satisfied == 1
    assert result.violated == 1
    assert result.unknown == 1


def test_strict_mode_adds_manual_review_warning_for_unknowns():
    constraint = _constraint("checks", "verification", "Run tests.")

    result = _service().validate_patch_against_constraints([constraint], strict=True)

    assert result.unknown == 1
    assert any("strict mode: unresolved unknown/manual_review constraints require manual review" in warning for warning in result.warnings)


def test_validation_accepts_constraints_packet_dict():
    packet = PatchConstraintPacket(task="Update permissions", constraints=[_constraint("generated", "generated_file", "Generated files *.g.dart must not be edited.", files=["*.g.dart"])])

    result = _service().validate_patch_against_constraints(asdict(packet), changed_files=["lib/user/user.g.dart"])

    assert result.task == "Update permissions"
    assert result.violated == 1


def test_validation_accepts_constraints_list():
    result = _service().validate_patch_against_constraints([
        {"id": "lock", "type": "forbidden_edit", "instruction": "Do not change lockfile.", "source": "pubspec.lock", "severity": "must", "confidence": "high", "evidence": "Do not change lockfile.", "files": ["pubspec.lock"], "symbols": []}
    ], changed_files=["pubspec.lock"])

    assert result.violated == 1


def test_validation_handles_empty_constraints():
    result = _service().validate_patch_against_constraints([], changed_files=["lib/main.dart"])

    assert result.total_constraints == 0
    assert result.satisfied == 0
    assert result.violated == 0
    assert result.unknown == 0
    assert result.confidence == "low"


def test_validation_does_not_require_git_repo_when_changed_files_provided(tmp_path: Path):
    missing_repo = tmp_path / "does-not-exist"
    constraint = _constraint("lock", "forbidden_edit", "Do not change lockfile.", files=["pubspec.lock"])

    result = _service().validate_patch_against_constraints([constraint], project_path=str(missing_repo), changed_files=["pubspec.lock"])

    assert result.violated == 1



def test_safe_ui_wiring_close_menu_and_notifier_call_is_not_violation():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate policy; delegate to MenuNotifier.")
    diff = """
+ onPressed: () {
+   menuNotifierController.closeMenu();
+   ref.read(tabBrowserNotifierProvider.notifier).openInfo();
+ }
+ context.push(CameraScreen.route);
"""

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/modules/menu/presentation/menu_line.dart"], patch_diff=diff)

    assert result.violated == 0
    assert result.results[0].status == "satisfied"


def test_context_push_route_navigation_alone_is_not_policy_violation():
    constraint = _constraint("provider", "forbidden_edit", "Presentation/UI must not duplicate policy; delegate to services.")
    diff = "+ context.push(CameraScreen.route);\n"

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/ui/menu_view.dart"], patch_diff=diff)

    assert result.violated == 0




def test_ref_read_notifier_action_alone_is_not_policy_violation():
    constraint = _constraint("provider", "forbidden_edit", "Presentation/UI must not duplicate policy; delegate to services.")
    diff = "+ onPressed: () => ref.read(tabBrowserNotifierProvider.notifier).openInfo();\n"

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/ui/menu_view.dart"], patch_diff=diff)

    assert result.violated == 0


def test_assignment_from_is_allowed_controller_violates():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate authorization policy; delegate to service.")
    diff = "+ final canProceed = authController.isAllowed(user);\n"

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/presentation/user_view.dart"], patch_diff=diff)

    assert result.violated == 1


def test_return_permission_controller_can_proceed_violates():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate permission policy; delegate to service.")
    diff = "+ return permissionController.canProceed(state);\n"

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/ui/permission_view.dart"], patch_diff=diff)

    assert result.violated == 1


def test_ui_role_branch_remains_policy_violation():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate authorization policy; delegate to service.")
    diff = """
+ if (user.role == 'admin') {
+   canProceed = true;
+ }
"""

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/presentation/user_view.dart"], patch_diff=diff)

    assert result.violated == 1


def test_ui_status_policy_map_remains_violation():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate status policy; delegate to service.")
    diff = """
+ final statusPolicyMap = {
+   PermissionStatus.denied: false,
+   PermissionStatus.granted: true,
+ };
"""

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/ui/permission_view.dart"], patch_diff=diff)

    assert result.violated == 1


def test_provider_permission_logic_remains_violation():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate permission policy; delegate to service.")
    diff = "+ final isAllowed = permission == PermissionStatus.granted;\n"

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/permission/provider/permission_provider.dart"], patch_diff=diff)

    assert result.violated == 1


def test_mixed_safe_wiring_and_policy_branch_remains_violation():
    constraint = _constraint("provider", "forbidden_edit", "Provider/UI must not duplicate authorization policy; delegate to service.")
    diff = """
+ menuNotifierController.closeMenu();
+ if (user.role == 'admin') {
+   ref.read(adminNotifierProvider.notifier).openAdmin();
+ }
"""

    result = _service().validate_patch_against_constraints([constraint], changed_files=["lib/presentation/menu_line.dart"], patch_diff=diff)

    assert result.violated == 1
