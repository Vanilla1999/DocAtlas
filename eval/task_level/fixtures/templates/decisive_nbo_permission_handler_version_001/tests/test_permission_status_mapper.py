from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPER = ROOT / "lib/modules/permission/domain/services/permission_status_mapper.dart"
LOCKFILE = ROOT / "pubspec.lock"
PUBSPEC = ROOT / "pubspec.yaml"
DOC = ROOT / "docs/dependencies.md"


def _mapping_for(status: str) -> str:
    text = MAPPER.read_text(encoding="utf-8")
    pattern = rf"PermissionStatus\.{re.escape(status)}\s*=>\s*PermissionReviewAction\.([A-Za-z0-9_]+)"
    match = re.search(pattern, text)
    assert match, f"missing explicit mapping for PermissionStatus.{status}"
    return match.group(1)


def test_permanently_denied_permissions_send_users_to_settings():
    assert _mapping_for("permanentlyDenied") == "openAppSettings"


def test_provisional_notification_access_is_not_app_settings_failure():
    assert _mapping_for("provisional") == "allowedWithFollowUp"


def test_permission_handler_dependency_remains_lockfile_pinned():
    lockfile = LOCKFILE.read_text(encoding="utf-8")
    pubspec = PUBSPEC.read_text(encoding="utf-8")
    docs = DOC.read_text(encoding="utf-8")

    assert 'version: "11.4.0"' in lockfile
    assert "permission_handler: 11.4.0" in pubspec
    assert "PermissionStatus.provisional" in docs
