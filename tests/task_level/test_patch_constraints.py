from __future__ import annotations

from pathlib import Path

from eval.task_level.context.patch_constraints import build_patch_constraint_packet
from eval.task_level.evaluators.patch_constraints import evaluate_patch_constraint_usage
from eval.task_level.schemas import DependencySpec, TaskSpec


def _task(task_id: str = "decisive_nbo_cross_module_gate_large_001") -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        task_type="real",
        suite="differentiation",
        repo="fixture://x",
        base_commit="base",
        issue_text="Browser and scan flows disagree about shared permission policy. Hidden test says do not leak this.",
        language="dart",
        ecosystem="dart",
        dependencies=(DependencySpec("permission_handler", "11.4.0"),),
        setup_command="",
        test_command="pytest tests",
    )


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "docs").mkdir(parents=True)
    (workspace / "lib/modules/permission/application").mkdir(parents=True)
    (workspace / "lib/modules/permission/presentation").mkdir(parents=True)
    (workspace / "docs/generated-files.md").write_text("Generated *.g.dart and *.freezed.dart files must not be edited by hand.", encoding="utf-8")
    (workspace / "docs/permission-architecture.md").write_text("PermissionService is the source of truth. Providers delegate to the service and must not duplicate policy.", encoding="utf-8")
    (workspace / "docs/browser-flow.md").write_text("Browser and scan use the same shared permission contract.", encoding="utf-8")
    (workspace / "pubspec.lock").write_text('packages:\n  permission_handler:\n    version: "11.4.0"\n', encoding="utf-8")
    (workspace / "lib/modules/permission/application/permission_service.dart").write_text("class PermissionService { List requiredForPreflight() => []; }", encoding="utf-8")
    return workspace


def test_patch_constraints_exclude_hidden_only_requirements(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))

    assert "Hidden test says" not in "\n".join(c.instruction for c in packet.constraints)


def test_patch_constraints_include_visible_generated_file_rule(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))

    assert any(c.type == "generated_file" for c in packet.constraints)


def test_patch_constraints_include_dependency_version_contract(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))

    assert any(c.type == "dependency_version" and "11.4.0" in c.instruction for c in packet.constraints)


def test_patch_constraints_include_architecture_owner(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))

    assert any(c.type == "architecture" and "PermissionService" in c.instruction for c in packet.constraints)


def test_patch_constraints_have_source_attribution(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))

    assert packet.constraints
    assert all(c.source for c in packet.constraints)
    assert packet.source_summary


def test_patch_constraints_token_estimate_exists(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))

    assert isinstance(packet.token_estimate, int)
    assert packet.token_estimate > 0


def test_patch_constraints_usage_detects_symbol_or_file_match(tmp_path: Path):
    packet = build_patch_constraint_packet(task=_task(), workspace=_workspace(tmp_path))
    patch_path = tmp_path / "patch.diff"
    patch_path.write_text("diff -- lib/modules/permission/application/permission_service.dart\n+ PermissionService().requiredForPreflight();\n", encoding="utf-8")

    usage = evaluate_patch_constraint_usage(packet, patch_path)

    assert usage["constraint_used"] is True
