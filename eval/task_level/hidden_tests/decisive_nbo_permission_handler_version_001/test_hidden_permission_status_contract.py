from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPPER = ROOT / "lib/modules/permission/domain/services/permission_status_mapper.dart"
REVIEW_NOTIFIER = ROOT / "lib/modules/permission/presentation/provider/permission_review_notifier.dart"
LOCKFILE = ROOT / "pubspec.lock"
PUBSPEC = ROOT / "pubspec.yaml"
DOCS = ROOT / "docs/dependencies.md"
ARCH = ROOT / "lib/modules/permission/ARCHITECTURE.md"


def _mapping_for(status: str) -> str:
    text = MAPPER.read_text(encoding="utf-8")
    pattern = rf"PermissionStatus\.{re.escape(status)}\s*=>\s*PermissionReviewAction\.([A-Za-z0-9_]+)"
    match = re.search(pattern, text)
    assert match, f"missing explicit mapping for PermissionStatus.{status}"
    return match.group(1)


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_hidden_requirements_are_discoverable_from_visible_dependency_sources():
    docs = DOCS.read_text(encoding="utf-8")
    arch = ARCH.read_text(encoding="utf-8")
    lockfile = LOCKFILE.read_text(encoding="utf-8")

    assert "PermissionStatus.restricted" in docs
    assert "PermissionStatus.limited" in docs
    assert "PermissionStatus.provisional" in docs
    assert "presentation" in arch.lower() and "must not duplicate" in arch
    assert 'version: "11.4.0"' in lockfile


def test_full_pinned_permission_status_mapping_contract():
    assert _mapping_for("granted") == "allowed"
    assert _mapping_for("denied") == "retryRequest"
    assert _mapping_for("permanentlyDenied") == "openAppSettings"
    assert _mapping_for("restricted") == "blockedBySystem"
    assert _mapping_for("limited") == "allowedWithLimits"
    assert _mapping_for("provisional") == "allowedWithFollowUp"


def test_fix_stays_in_domain_mapper_and_does_not_duplicate_status_policy_in_presentation():
    changed = _changed_files()
    mapper_path = "lib/modules/permission/domain/services/permission_status_mapper.dart"
    assert mapper_path in changed
    assert "pubspec.yaml" not in changed
    assert "pubspec.lock" not in changed

    presentation_text = REVIEW_NOTIFIER.read_text(encoding="utf-8")
    assert "PermissionStatus.permanentlyDenied" not in presentation_text
    assert "PermissionStatus.provisional" not in presentation_text


def test_no_latest_or_wrong_version_permission_status_symbols_are_introduced():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*.dart")
        if ".git" not in path.parts
    )

    forbidden = [
        "PermissionStatus.deniedPermanently",
        "PermissionStatus.permanentDenied",
        "PermissionStatus.appSettingsOnly",
        "PermissionStatus.notificationProvisional",
        ".isPermanentlyDenied",
    ]
    for symbol in forbidden:
        assert symbol not in combined

    assert "permission_handler: 11.4.0" in PUBSPEC.read_text(encoding="utf-8")
