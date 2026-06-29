from __future__ import annotations

import subprocess
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "lib/modules/permission/data/models/permission_info.dart"
GENERATED = ROOT / "lib/modules/permission/data/models/permission_info.freezed.dart"


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_hidden_requirement_sources_are_visible():
    assert "*.g.dart" in (ROOT / "lib/modules/permission/ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "isCritical" in (ROOT / "docs/generated-source.md").read_text(encoding="utf-8")
    assert 'version: "11.4.0"' in (ROOT / "pubspec.lock").read_text(encoding="utf-8")


def test_is_critical_uses_pinned_permission_handler_api_not_media_permissions():
    text = MODEL.read_text(encoding="utf-8")

    assert "Permission.locationAlways" in text
    assert "Permission.photos" not in text
    assert "Permission.videos" not in text
    assert "Permission.audio" not in text


def test_generated_file_is_not_edited():
    changed = _changed_files()

    assert "lib/modules/permission/data/models/permission_info.dart" in changed
    assert all(not path.endswith((".g.dart", ".freezed.dart")) for path in changed)
    assert "isCritical" not in GENERATED.read_text(encoding="utf-8")


def test_critical_set_is_exact_for_permission_module():
    text = MODEL.read_text(encoding="utf-8")

    assert "bool get isCritical" in text
    assert "Permission.camera" in text
    assert "Permission.phone" in text
    assert "Permission.location" in text
    assert "Permission.locationAlways" in text
    assert "Permission.storage" not in text.split("bool get isCritical", 1)[1]
