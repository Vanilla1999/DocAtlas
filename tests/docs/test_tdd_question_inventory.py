"""Exercise the capture contract, not model answer quality."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from eval.tdd_question_inventory import (
    inspect_source, load_cases, request_for, validate_cases,
)

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "eval/tdd_questions30/cases.json"
DIGEST = "12835d40de697b0c719181bba59f88b86c66d4337bcfce7fc92bb673d969836f"


def case():
    return {"id": "N01", "question": "Original question?", "scope": "all",
            "lookup_queries": ["original question"]}


def inventory():
    return [dict(case(), id=f"N{i:02d}") for i in range(1, 31)]


def test_frozen_inventory_is_loaded_without_editing_bytes():
    before = CASES.read_bytes()
    rows = load_cases(CASES, DIGEST)
    assert len(rows) == 30
    assert [r["id"] for r in rows] == [f"N{i:02d}" for i in range(1, 31)]
    assert rows == json.loads(before)
    assert CASES.read_bytes() == before


def test_inventory_digest_is_checked_before_use(tmp_path):
    path = tmp_path / "cases.json"
    path.write_bytes(CASES.read_bytes() + b" ")
    with pytest.raises(ValueError, match="digest"):
        load_cases(path, DIGEST)


@pytest.mark.parametrize("mutation", ["short", "duplicate", "reordered", "gold", "blank", "scope", "six", "duplicates", "number"])
def test_invalid_inventory_is_rejected(mutation):
    rows = inventory()
    if mutation == "short": rows.pop()
    elif mutation == "duplicate": rows[1]["id"] = "N01"
    elif mutation == "reordered": rows.reverse()
    elif mutation == "gold": rows[0]["gold"] = {"expected": "not runtime data"}
    elif mutation == "blank": rows[0]["question"] = " "
    elif mutation == "scope": rows[0]["scope"] = "global"
    elif mutation == "six": rows[0]["lookup_queries"] = [str(i) for i in range(6)]
    elif mutation == "duplicates": rows[0]["lookup_queries"] = ["same", "same"]
    elif mutation == "number": rows[0]["lookup_queries"] = [23]
    with pytest.raises(ValueError):
        validate_cases(rows)


@pytest.mark.parametrize("lane", ["direct", "assisted"])
def test_request_uses_only_original_question_and_fixed_lookups(lane):
    row = case(); before = deepcopy(row)
    payload = request_for(row, "/project", lane)
    expected = {"question": row["question"], "project_path": "/project", "scope": "all"}
    if lane == "assisted": expected["lookup_queries"] = row["lookup_queries"]
    assert payload == expected
    assert row == before
    if lane == "assisted":
        payload["lookup_queries"].append("caller mutation")
        assert row == before


def test_gold_cannot_be_injected_into_requests():
    row = dict(case(), gold={"source_path": "secret-answer.md"})
    with pytest.raises(ValueError):
        request_for(row, "/project", "direct")


def test_unknown_lane_is_not_silently_assisted():
    with pytest.raises(ValueError):
        request_for(case(), "/project", "adaptive")


def source(path="docs/guide.md", **kwargs):
    return {"path_or_url": path, "snippet": "Exact witness.", "line_start": 3, "line_end": 3, **kwargs}


def test_source_span_is_checked_against_actual_file(tmp_path):
    (tmp_path / "docs").mkdir()
    data = b"# Guide\r\n\r\nExact witness.\r\n"
    (tmp_path / "docs/guide.md").write_bytes(data)
    result = inspect_source(source(), tmp_path)
    assert result["span_verified"] is True
    assert result["file_sha256"] == hashlib.sha256(data).hexdigest()
    assert result["runtime_content_hash_verified"] is None


@pytest.mark.parametrize("change", [{"line_start": 1, "line_end": 1}, {"snippet": "Invented"}, {"line_start": True}])
def test_wrong_span_is_not_verified(tmp_path, change):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/guide.md").write_text("# Guide\n\nExact witness.\n")
    assert inspect_source(source(**change), tmp_path)["span_verified"] is False


@pytest.mark.parametrize("path", ["../outside.md", "/etc/passwd", "eval/answers.md", "experiments/report.md", "tests/gold.md", "https://example.com/guide"])
def test_outside_or_evaluation_sources_are_not_read(tmp_path, path):
    result = inspect_source(source(path), tmp_path)
    assert result["span_verified"] is False
    assert "file_sha256" not in result


def test_symlink_outside_project_is_not_read(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    outside = tmp_path / "outside.md"; outside.write_text("Private data")
    (project / "guide.md").symlink_to(outside)
    assert inspect_source(source("guide.md"), project)["span_verified"] is False


def test_absent_source_ranges_remain_unmeasured(tmp_path):
    (tmp_path / "guide.md").write_text("Exact witness.")
    row = {"path_or_url": "guide.md", "snippet": "Exact witness."}
    assert inspect_source(row, tmp_path)["span_verified"] is None
