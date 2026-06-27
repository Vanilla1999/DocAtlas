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
    assert "Permission.notification" in (ROOT / "docs/permission-notifications.md").read_text(encoding="utf-8")
    assert 'version: "11.4.0"' in (ROOT / "pubspec.lock").read_text(encoding="utf-8")


def test_notification_uses_pinned_permission_handler_api_not_media_permissions():
    text = SERVICE.read_text(encoding="utf-8")

    assert "Permission.notification" in text
    assert "Permission.photos" not in text
    assert "Permission.videos" not in text
    assert "Permission.audio" not in text


def test_permission_change_stays_in_service_layer():
    changed = _changed_files()

    assert "lib/modules/permission/domain/services/permission_service.dart" in changed
    assert "lib/modules/permission/presentation/provider/permission_notifier.dart" not in changed
    assert all(not path.endswith((".g.dart", ".freezed.dart")) for path in changed)
    assert "Permission.notification" not in NOTIFIER.read_text(encoding="utf-8")


def test_notification_permission_is_idempotent_and_named():
    text = SERVICE.read_text(encoding="utf-8")

    assert "PermissionInfo permissionNotification" in text
    assert "permissionNotification.permission" in text
    assert re.search(
        r"permissionsToRequest\.any\(\s*\(p\)\s*=>\s*p\.permission\s*==\s*permissionNotification\.permission\s*,?\s*\)",
        text,
    )
