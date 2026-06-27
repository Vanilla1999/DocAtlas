from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "lib/modules/permission/domain/services/permission_service.dart"


def _service_text() -> str:
    return SERVICE.read_text(encoding="utf-8")


def test_location_always_is_not_requested_during_preflight():
    text = _service_text()

    assert ".where((p) => p.permission != Permission.locationAlways)" in text
    assert "Permission.locationAlways.request()" not in text


def test_location_always_is_still_reported_as_deferred_when_needed():
    text = _service_text()

    assert "permissionLocationAlways" in text
    assert re.search(r"permissionsToRequestAgain\.add\(\s*permissionLocationAlways\s*\)", text)
    assert "Permission.location.status" in text
