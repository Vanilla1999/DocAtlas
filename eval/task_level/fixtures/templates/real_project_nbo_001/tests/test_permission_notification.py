from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "lib/modules/permission/domain/services/permission_service.dart"


def _service_text() -> str:
    return SERVICE.read_text(encoding="utf-8")


def _sdk_33_block(text: str) -> str:
    match = re.search(r"if \(androidInfo\.version\.sdkInt >= 33\) \{([\s\S]*?)\n    \} else if", text)
    assert match, "addPermissionsNotAw must keep the Android 13 branch"
    return match.group(1)


def test_android_13_notification_permission_is_requested():
    text = _service_text()
    block = _sdk_33_block(text)

    assert "Permission.notification" in text
    assert "permissionNotification" in text
    assert re.search(r"permissionsToRequest\.add\(\s*permissionNotification\s*\)", block)


def test_location_always_stays_deferred():
    text = _service_text()

    assert ".where((p) => p.permission != Permission.locationAlways)" in text
    assert "await Permission.locationAlways.request()" in text
