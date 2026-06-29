from __future__ import annotations

import subprocess
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "lib/modules/permission/domain/services/permission_service.dart"
NOTIFIER = ROOT / "lib/modules/permission/presentation/provider/permission_notifier.dart"


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_hidden_requirement_sources_are_visible():
    assert "PermissionService" in (ROOT / "lib/modules/permission/ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "locationAlways" in (ROOT / "docs/permission-location.md").read_text(encoding="utf-8")
    assert 'version: "11.4.0"' in (ROOT / "pubspec.lock").read_text(encoding="utf-8")


def test_location_always_uses_pinned_permission_handler_api_not_media_permissions():
    text = SERVICE.read_text(encoding="utf-8")

    assert "Permission.locationAlways" in text
    assert "Permission.photos" not in text
    assert "Permission.videos" not in text
    assert "Permission.audio" not in text


def test_deferred_location_change_stays_in_service_layer():
    changed = _changed_files()

    assert "lib/modules/permission/domain/services/permission_service.dart" in changed
    assert "lib/modules/permission/presentation/provider/permission_notifier.dart" not in changed
    assert all(not path.endswith((".g.dart", ".freezed.dart")) for path in changed)
    assert "Permission.locationAlways.request" not in NOTIFIER.read_text(encoding="utf-8")


def test_location_always_is_deferred_not_requested_inline():
    text = SERVICE.read_text(encoding="utf-8")

    assert "Permission.locationAlways.request()" not in text
    assert re.search(r"permissionsToRequestAgain\.add\(\s*permissionLocationAlways\s*\)", text)
    assert re.search(r"await\s+Permission\.location\.status", text)
