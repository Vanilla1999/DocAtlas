from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "lib/modules/permission/data/models/permission_info.dart"
GENERATED = ROOT / "lib/modules/permission/data/models/permission_info.freezed.dart"
DOC = ROOT / "docs/generated-source.md"


def test_permission_info_source_exposes_preflight_blocking_policy():
    text = MODEL.read_text(encoding="utf-8")

    assert "bool get blocksPreflight" in text
    assert "Permission.camera" in text
    assert "Permission.phone" in text
    assert "Permission.location" in text
    assert "Permission.notification" in text


def test_background_location_remains_deferred_by_source_policy():
    text = MODEL.read_text(encoding="utf-8")
    helper_body = text.split("bool get blocksPreflight", 1)[1]

    assert "Permission.locationAlways" in DOC.read_text(encoding="utf-8")
    assert "Permission.locationAlways" not in helper_body.split("_ => false", 1)[0]


def test_generated_file_remains_unmodified_source_stub():
    text = GENERATED.read_text(encoding="utf-8")

    assert "GENERATED CODE - DO NOT MODIFY BY HAND" in text
    assert "blocksPreflight" not in text
