from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"


def _service_text() -> str:
    return SERVICE.read_text(encoding="utf-8")


def _preflight_body(text: str) -> str:
    match = re.search(r"List<PermissionInfo> requiredForPreflight\(PermissionFlow flow, int sdkInt\) \{([\s\S]*?)\n  \}", text)
    assert match, "PermissionService must expose requiredForPreflight(flow, sdkInt)"
    return match.group(1)


def test_browser_scan_preflight_includes_notification_for_android_13_plus():
    text = _service_text()
    body = _preflight_body(_service_text())

    assert "sdkInt >= 33" in body
    assert "Permission.notification" in text
    assert "notificationPermission" in body


def test_android_below_13_does_not_require_notification_by_default():
    body = _preflight_body(_service_text())
    initial_list = body.split("if (sdkInt >= 33)", 1)[0]

    assert "Permission.notification" not in initial_list


def test_location_always_remains_deferred_from_preflight():
    body = _preflight_body(_service_text())

    assert "Permission.locationAlways" not in body
    assert "permission == Permission.locationAlways" in _service_text()
