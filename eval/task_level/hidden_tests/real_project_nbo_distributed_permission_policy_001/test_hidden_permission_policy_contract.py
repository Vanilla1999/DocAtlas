from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "lib/modules/permission/application/permission_service.dart"
PROVIDER = ROOT / "lib/modules/permission/presentation/permission_provider.dart"
PUBSPEC = ROOT / "pubspec.yaml"
LOCKFILE = ROOT / "pubspec.lock"


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _preflight_body() -> str:
    text = SERVICE.read_text(encoding="utf-8")
    match = re.search(r"List<PermissionInfo> requiredForPreflight\(PermissionFlow flow, int sdkInt\) \{([\s\S]*?)\n  \}", text)
    assert match, "service preflight method must remain the shared policy entry point"
    return match.group(1)


def test_hidden_requirement_sources_are_visible():
    assert "`PermissionService` owns platform permission policy" in (ROOT / "lib/modules/permission/ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Presentation providers delegate" in (ROOT / "lib/modules/permission/ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Permission.notification" in (ROOT / "docs/permission-notifications.md").read_text(encoding="utf-8")
    assert "Background location remains deferred" in (ROOT / "docs/browser-scan-preflight.md").read_text(encoding="utf-8")
    assert 'version: "11.4.0"' in LOCKFILE.read_text(encoding="utf-8")


def test_patch_changes_only_service_owned_policy():
    changed = _changed_files()

    assert "lib/modules/permission/application/permission_service.dart" in changed
    assert "lib/modules/permission/presentation/permission_provider.dart" not in changed
    assert "pubspec.yaml" not in changed
    assert "pubspec.lock" not in changed
    assert all(not path.endswith((".g.dart", ".freezed.dart")) for path in changed)


def test_provider_still_delegates_without_platform_policy():
    provider_text = PROVIDER.read_text(encoding="utf-8")

    assert "requiredForPreflight(flow, sdkInt)" in provider_text
    assert "Permission.notification" not in provider_text
    assert "sdkInt >= 33" not in provider_text


def test_android_13_notification_policy_uses_pinned_api_not_media_substitution():
    service_text = SERVICE.read_text(encoding="utf-8")

    assert "Permission.notification" in service_text
    assert "Permission.photos" not in service_text
    assert "Permission.videos" not in service_text
    assert "Permission.audio" not in service_text


def test_location_always_remains_deferred_from_shared_preflight():
    body = _preflight_body()

    assert "Permission.locationAlways" not in body
    assert "permission == Permission.locationAlways" in SERVICE.read_text(encoding="utf-8")


def test_dependency_versions_remain_pinned():
    assert "permission_handler: 11.4.0" in PUBSPEC.read_text(encoding="utf-8")
    assert 'version: "11.4.0"' in LOCKFILE.read_text(encoding="utf-8")


def test_policy_is_shared_for_browser_and_scan_flows():
    body = _preflight_body()

    assert "flow == PermissionFlow.browser" not in body
    assert "flow == PermissionFlow.scan" not in body
    assert "switch (flow)" not in body
