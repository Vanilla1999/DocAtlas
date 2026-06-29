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


def test_browser_preflight_includes_notification_for_android_13_plus():
    text = _service_text()
    body = _preflight_body(text)

    assert "sdkInt >= 33" in body
    assert "Permission.notification" in text
    assert "notificationPermission" in body


def test_background_location_is_not_in_preflight_batch():
    body = _preflight_body(_service_text())

    assert "Permission.locationAlways" not in body
    assert "permission == Permission.locationAlways" in _service_text()
