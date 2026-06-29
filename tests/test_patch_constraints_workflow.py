from __future__ import annotations

from pathlib import Path

from docmancer.docs.application.patch_constraint_validation_service import PatchConstraintValidationService
from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.service import LibraryDocsService


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(
        root / "docs/architecture.md",
        """
PermissionService owns permission policy and is the source of truth for permission decisions.
Provider delegates to PermissionService and must not duplicate policy maps.
Generated files *.g.dart and *.freezed.dart must not be edited by hand; regenerate from source model.
Do not change lockfile without explicit dependency upgrade approval.
""",
    )
    _write(root / "pubspec.lock", 'packages:\n  permission_handler:\n    version: "11.4.0"\n')
    _write(root / "lib/permission/application/permission_service.dart", "class PermissionService {}\n")
    _write(root / "lib/permission/presentation/permission_provider.dart", "// provider\n")
    return root


def _constraints(root: Path, *, changed_files: list[str] | None = None):
    return PatchConstraintsService(LibraryDocsService()).get_patch_constraints(
        "Update permission policy without touching generated files or providers.",
        project_path=str(root),
        changed_files=changed_files,
    )


def test_get_then_validate_generated_file_violation(tmp_path: Path):
    root = _project(tmp_path)
    packet = _constraints(root, changed_files=["lib/user/user.g.dart"])

    result = PatchConstraintValidationService().validate_patch_against_constraints(packet, changed_files=["lib/user/user.g.dart"])

    assert result.violated >= 1
    assert any("generated" in item.reason.lower() for item in result.results if item.status == "violated")


def test_get_then_validate_lockfile_violation(tmp_path: Path):
    root = _project(tmp_path)
    packet = _constraints(root, changed_files=["pubspec.lock"])

    result = PatchConstraintValidationService().validate_patch_against_constraints(packet, changed_files=["pubspec.lock"])

    assert result.violated >= 1
    assert any("lockfile" in item.reason.lower() for item in result.results if item.status == "violated")


def test_get_then_validate_source_of_truth_satisfied(tmp_path: Path):
    root = _project(tmp_path)
    packet = _constraints(root, changed_files=["lib/permission/application/permission_service.dart"])

    result = PatchConstraintValidationService().validate_patch_against_constraints(
        packet,
        changed_files=["lib/permission/application/permission_service.dart"],
    )

    assert result.satisfied >= 1
    assert any(item.status == "satisfied" for item in result.results)


def test_get_then_validate_provider_policy_violation(tmp_path: Path):
    root = _project(tmp_path)
    packet = _constraints(root, changed_files=["lib/permission/presentation/permission_provider.dart"])
    diff = """
+ if (permission.status == PermissionStatus.denied) {
+   canProceed = role == 'admin';
+ }
"""

    result = PatchConstraintValidationService().validate_patch_against_constraints(
        packet,
        changed_files=["lib/permission/presentation/permission_provider.dart"],
        patch_diff=diff,
    )

    assert result.violated >= 1
    assert any("provider/ui" in item.reason.lower() for item in result.results if item.status == "violated")


def test_get_then_validate_unknown_without_diff(tmp_path: Path):
    root = _project(tmp_path)
    packet = _constraints(root, changed_files=["lib/permission/presentation/permission_provider.dart"])

    result = PatchConstraintValidationService().validate_patch_against_constraints(
        packet,
        changed_files=["lib/permission/presentation/permission_provider.dart"],
    )

    assert result.unknown >= 1
    assert any("diff unavailable" in item.reason.lower() for item in result.results if item.status == "unknown")
