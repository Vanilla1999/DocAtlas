from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROWSER = ROOT / "lib/modules/browser/application/browser_permission_gate.dart"
SCAN = ROOT / "lib/modules/scan/application/scan_permission_gate.dart"
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_body(path: Path, method: str) -> str:
    match = re.search(rf"{method}\(PermissionResult result\) \{{([\s\S]*?)\n  \}}", _text(path))
    assert match, f"{path.name} must expose {method}(PermissionResult result)"
    return match.group(1)


def test_browser_and_scan_block_partial_permission_result():
    browser = _method_body(BROWSER, "canEnter")
    scan = _method_body(SCAN, "canEnter")

    assert "evaluatePreflight(result) == PermissionDecision.allow" in browser
    assert "evaluatePreflight(result) == PermissionDecision.allow" in scan


def test_allowed_result_still_proceeds_through_shared_contract():
    service = _method_body(SERVICE, "evaluatePreflight")

    assert "PermissionDecision.allow" in service
    assert "PermissionDecision.block" in service


def test_browser_and_scan_use_consistent_permission_gate_shape():
    assert "PermissionService _permissionService" in _text(BROWSER)
    assert "PermissionService _permissionService" in _text(SCAN)
