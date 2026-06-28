from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "lib/modules/permission/data/models/permission_info.dart"
GENERATED = ROOT / "lib/modules/permission/data/models/permission_info.freezed.dart"


def _changed_files() -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _helper_body() -> str:
    text = MODEL.read_text(encoding="utf-8")
    assert "bool get blocksPreflight" in text
    return text.split("bool get blocksPreflight", 1)[1]


def test_hidden_requirement_sources_are_visible():
    generated_doc = (ROOT / "docs/generated-source.md").read_text(encoding="utf-8")
    architecture = (ROOT / "lib/modules/permission/ARCHITECTURE.md").read_text(encoding="utf-8")
    lockfile = (ROOT / "pubspec.lock").read_text(encoding="utf-8")

    assert "blocksPreflight" in generated_doc
    assert "locationAlways" in generated_doc
    assert "*.freezed.dart" in generated_doc
    assert "*.g.dart" in architecture
    assert 'version: "11.4.0"' in lockfile


def test_preflight_policy_uses_pinned_permission_handler_names():
    body = _helper_body()

    assert "Permission.notification" in body
    assert "Permission.location" in body
    assert "Permission.photos" not in body
    assert "Permission.videos" not in body
    assert "Permission.audio" not in body


def test_generated_file_is_not_edited():
    changed = _changed_files()

    assert "lib/modules/permission/data/models/permission_info.dart" in changed
    assert all(not path.endswith((".g.dart", ".freezed.dart")) for path in changed)
    assert "blocksPreflight" not in GENERATED.read_text(encoding="utf-8")


def test_background_location_is_deferred_not_preflight_blocking():
    body = _helper_body()
    positive_branch = body.split("_ => false", 1)[0]

    assert "Permission.locationAlways" not in positive_branch
    assert "Permission.storage" not in positive_branch
