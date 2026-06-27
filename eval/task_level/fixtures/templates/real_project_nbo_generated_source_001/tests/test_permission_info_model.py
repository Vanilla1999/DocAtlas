from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "lib/modules/permission/data/models/permission_info.dart"
GENERATED = ROOT / "lib/modules/permission/data/models/permission_info.freezed.dart"


def test_is_critical_getter_added_to_source_model():
    text = MODEL.read_text(encoding="utf-8")

    assert "bool get isCritical" in text
    assert "Permission.camera" in text
    assert "Permission.phone" in text
    assert "Permission.location" in text
    assert "Permission.locationAlways" in text


def test_generated_file_remains_unmodified_source_stub():
    text = GENERATED.read_text(encoding="utf-8")

    assert "GENERATED CODE - DO NOT MODIFY BY HAND" in text
    assert "isCritical" not in text
