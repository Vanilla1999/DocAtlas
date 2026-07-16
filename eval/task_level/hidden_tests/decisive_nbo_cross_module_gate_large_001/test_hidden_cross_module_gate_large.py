from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"
BROWSER = ROOT / "lib/modules/browser/application/browser_permission_gate.dart"
SCAN = ROOT / "lib/modules/scan/application/scan_permission_gate.dart"
SYNC = ROOT / "lib/modules/sync/application/offline_sync_gate.dart"
REVIEW = ROOT / "lib/modules/review/application/permission_review_policy.dart"
PUBSPEC = ROOT / "pubspec.yaml"
LOCKFILE = ROOT / "pubspec.lock"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _delegates_and_requires_allow(source: str) -> bool:
    direct = re.search(
        r"\breturn\s+(?:\w+\.)?evaluateFlowEntry\s*"
        r"\(\s*result\s*\)\s*==\s*PermissionDecision\.allow\s*;",
        source,
        re.DOTALL,
    )
    assigned = re.search(
        r"final\s+(\w+)\s*=\s*(?:\w+\.)?evaluateFlowEntry\s*"
        r"\(\s*result\s*\)\s*;.*?return\s+\1\s*==\s*"
        r"PermissionDecision\.allow\s*;",
        source,
        re.DOTALL,
    )
    return direct is not None or assigned is not None


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _method_body(path: Path, method: str) -> str:
    match = re.search(rf"{method}\(PermissionResult result\) \{{([\s\S]*?)\n  \}}", _text(path))
    assert match, f"{path.name} must expose {method}(PermissionResult result)"
    return match.group(1)


def test_hidden_requirement_sources_are_visible():
    assert "canonical owner of permission result interpretation" in _text(ROOT / "docs/permission-architecture.md")
    assert "Browser and scan flows both share the same immediate-entry contract" in _text(ROOT / "docs/permission-architecture.md")
    assert "offline fallback still cannot bypass missing immediate-entry permissions" in _text(ROOT / "docs/permission-architecture.md")
    assert "Use `PermissionService.evaluateFlowEntry(result, allowOfflineFallback: false)`" in _text(ROOT / "docs/offline-sync.md")
    assert "must not be hand-edited" in _text(ROOT / "docs/generated-files.md")


def test_permission_service_blocks_partial_results_for_entry_even_when_offline_fallback_exists():
    service = _text(SERVICE)
    entry = service.split("PermissionDecision evaluateReview", 1)[0]

    assert "PermissionDecision evaluateFlowEntry" in service
    assert "allowOfflineFallback" in service
    assert "result.hasMissingImmediatePermission" in entry
    assert "return PermissionDecision.block;" in entry
    assert "PermissionDecision.deferFollowUp" not in entry


def test_browser_scan_and_sync_delegate_to_shared_entry_contract():
    browser = _method_body(BROWSER, "canEnter")
    scan = _method_body(SCAN, "canEnter")
    sync = _method_body(SYNC, "canAcceptQueuedWork")

    assert "evaluateFlowEntry" in browser and "== PermissionDecision.allow" in browser
    assert _delegates_and_requires_allow(scan)
    assert "evaluateFlowEntry" in sync and "allowOfflineFallback: false" in sync and "== PermissionDecision.allow" in sync


def test_no_duplicate_immediate_permission_interpretation_in_flow_gates():
    flow_text = "\n".join(_text(path) for path in [BROWSER, SCAN, SYNC])

    forbidden = [
        "cameraGranted ||",
        "locationGranted ||",
        "nearbyGranted ||",
        "notificationGranted ||",
        "hasMissingImmediatePermission",
        "hasPartialImmediateGrant",
        "decision != PermissionDecision.block",
    ]
    for token in forbidden:
        assert token not in flow_text


def test_review_policy_stays_descriptive_and_background_location_remains_deferred_followup():
    service = _text(SERVICE)
    review = _text(REVIEW)

    assert "hasDeferredBackgroundLocation" in service
    assert "PermissionDecision.deferFollowUp" in service
    assert "evaluateReview" in review
    assert "canEnter" not in review


def test_generated_and_dependency_files_are_not_changed():
    changed = _changed_files()

    assert all(not path.endswith((".freezed.dart", ".g.dart")) for path in changed)
    assert "pubspec.yaml" not in changed
    assert "pubspec.lock" not in changed
    assert "permission_handler: 11.4.0" in _text(PUBSPEC)
    assert 'version: "11.4.0"' in _text(LOCKFILE)
