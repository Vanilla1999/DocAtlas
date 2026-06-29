from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"
BROWSER = ROOT / "lib/modules/browser/application/browser_permission_gate.dart"
SCAN = ROOT / "lib/modules/scan/application/scan_permission_gate.dart"
REVIEW = ROOT / "lib/modules/review/application/permission_review_policy.dart"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_body(path: Path, method: str) -> str:
    match = re.search(rf"{method}\(PermissionResult result\) \{{([\s\S]*?)\n  \}}", _text(path))
    assert match, f"{path.name} must expose {method}(PermissionResult result)"
    return match.group(1)


def test_browser_blocks_partial_permission_result_even_with_offline_fallback():
    browser = _method_body(BROWSER, "canEnter")
    service = _text(SERVICE)

    assert "allowOfflineFallback: true" in browser
    assert "== PermissionDecision.allow" in browser
    assert "? PermissionDecision.deferFollowUp" not in service


def test_allowed_result_still_has_allow_and_block_decisions():
    service = _text(SERVICE)

    assert "PermissionDecision allow" not in service
    assert "PermissionDecision.allow" in service
    assert "PermissionDecision.block" in service
    assert "hasMissingImmediatePermission" in service


def test_scan_source_still_exposes_gate_for_cross_module_contract():
    scan = _text(SCAN)

    assert "class ScanPermissionGate" in scan
    assert "PermissionService _permissionService" in scan


def test_review_policy_remains_descriptive_not_entry_gate():
    review = _text(REVIEW)

    assert "evaluateReview" in review
    assert "labelFor" in review
    assert "canEnter" not in review
