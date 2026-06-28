from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.service import LibraryDocsService


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "lib/modules/permission/domain/services").mkdir(parents=True)
    (root / "lib/modules/permission/presentation/providers").mkdir(parents=True)
    (root / "docs/architecture.md").write_text(
        "Permission behavior is owned by PermissionService in the domain service layer. "
        "Providers delegate to the service and must not duplicate policy maps.\n",
        encoding="utf-8",
    )
    (root / "docs/generated.md").write_text(
        "Generated files such as *.g.dart and *.freezed.dart must not be edited by hand.\n",
        encoding="utf-8",
    )
    (root / "lib/modules/permission/domain/services/permission_service.dart").write_text(
        "class PermissionService { /* source-of-truth */ }\n",
        encoding="utf-8",
    )
    (root / "pubspec.yaml").write_text("dependencies:\n  permission_handler: ^11.4.0\n", encoding="utf-8")
    (root / "pubspec.lock").write_text(
        'packages:\n  permission_handler:\n    dependency: "direct main"\n    source: hosted\n    version: "11.4.0"\n',
        encoding="utf-8",
    )
    return root


def _packet(tmp_path: Path, **kwargs):
    service = PatchConstraintsService(LibraryDocsService())
    return service.get_patch_constraints(
        question="Update permission preflight without touching generated files or providers.",
        project_path=str(_workspace(tmp_path)),
        **kwargs,
    )


def test_generated_file_constraint_extraction(tmp_path: Path):
    packet = _packet(tmp_path)

    assert any(c.type == "generated_file" and "*.g.dart" in c.instruction for c in packet.constraints)
    assert any("generated" in c.evidence.lower() for c in packet.constraints)


def test_source_of_truth_extraction(tmp_path: Path):
    packet = _packet(tmp_path)

    assert any(c.type == "source_of_truth" and "PermissionService" in c.instruction for c in packet.constraints)
    assert any(c.type == "architecture" and "provider" in c.instruction.lower() for c in packet.constraints)


def test_pinned_dependency_extraction(tmp_path: Path):
    packet = _packet(tmp_path)

    assert any(c.type == "dependency_version" and "permission_handler" in c.instruction and "11.4.0" in c.instruction for c in packet.constraints)
    assert any(c.type == "forbidden_edit" and "lockfile" in c.instruction.lower() for c in packet.constraints)


def test_constraints_have_source_attribution(tmp_path: Path):
    packet = _packet(tmp_path)

    assert packet.constraints
    assert all(c.source for c in packet.constraints)
    assert all(c.confidence in {"high", "medium", "low"} for c in packet.constraints)
    assert all(c.evidence for c in packet.constraints)


def test_budget_limits_keep_must_high_confidence_first(tmp_path: Path):
    packet = _packet(tmp_path, max_constraints=2, max_tokens=80)

    assert len(packet.constraints) <= 2
    assert packet.token_estimate <= 80
    assert packet.warnings
    assert all(c.severity == "must" for c in packet.constraints)


def test_no_benchmark_oracle_hidden_test_leakage(tmp_path: Path):
    packet = _packet(tmp_path)
    payload = str(asdict(packet)).lower()

    assert "hidden test" not in payload
    assert "gold patch" not in payload
    assert "oracle" not in payload
