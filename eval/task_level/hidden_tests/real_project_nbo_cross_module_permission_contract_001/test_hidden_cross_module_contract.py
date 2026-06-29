from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"
BROWSER = ROOT / "lib/modules/browser/application/browser_permission_gate.dart"
SCAN = ROOT / "lib/modules/scan/application/scan_permission_gate.dart"
LOCKFILE = ROOT / "pubspec.lock"
PUBSPEC = ROOT / "pubspec.yaml"


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_hidden_requirement_sources_are_visible():
    assert "canonical permission result interpretation" in (ROOT / "docs/permission-architecture.md").read_text(encoding="utf-8")
    assert "Browser and scan flows must use the shared permission contract" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "must not duplicate permission policy" in (ROOT / "docs/permission-architecture.md").read_text(encoding="utf-8")
    assert "must not be edited by hand" in (ROOT / "docs/generated-files.md").read_text(encoding="utf-8")


def test_permission_module_keeps_canonical_interpretation():
    service = SERVICE.read_text(encoding="utf-8")

    assert "PermissionDecision evaluatePreflight" in service
    assert "result.hasAnyMissingPermission" in service
    assert "PermissionDecision.block" in service
    assert "PermissionDecision.allow" in service


def test_both_flow_gates_delegate_to_shared_contract():
    browser = BROWSER.read_text(encoding="utf-8")
    scan = SCAN.read_text(encoding="utf-8")

    assert "_permissionService.evaluatePreflight(result) == PermissionDecision.allow" in browser
    assert "_permissionService.evaluatePreflight(result) == PermissionDecision.allow" in scan


def test_no_duplicate_permission_interpretation_remains_in_flow_gates():
    browser = BROWSER.read_text(encoding="utf-8")
    scan = SCAN.read_text(encoding="utf-8")
    flow_text = browser + "\n" + scan

    assert "cameraGranted ||" not in flow_text
    assert "locationGranted ||" not in flow_text
    assert "notificationGranted ||" not in flow_text
    assert "hasAnyMissingPermission" not in flow_text


def test_generated_and_dependency_files_unchanged():
    changed = _changed_files()

    assert all(not path.endswith((".freezed.dart", ".g.dart")) for path in changed)
    assert "pubspec.yaml" not in changed
    assert "pubspec.lock" not in changed
    assert "permission_handler: 11.4.0" in PUBSPEC.read_text(encoding="utf-8")
    assert 'version: "11.4.0"' in LOCKFILE.read_text(encoding="utf-8")


def test_shared_contract_change_does_not_patch_generated_source():
    changed = _changed_files()

    assert "lib/modules/permission/domain/permission_result.freezed.dart" not in changed
    assert "lib/modules/scan/application/scan_permission_gate.dart" in changed
