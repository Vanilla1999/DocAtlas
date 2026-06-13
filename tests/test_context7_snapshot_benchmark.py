import json
from pathlib import Path

from docmancer.eval.schema import load_golden_dataset


ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str) -> dict:
    path = ROOT / relative_path
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _item_ids(report: dict) -> list[str]:
    return [item["id"] for item in report["items"]]


def _golden_item_ids(dataset_path: str) -> list[str]:
    dataset = load_golden_dataset(str(ROOT / dataset_path))
    return [item.id for item in dataset.items]


def _assert_context7_snapshot(report: dict, *, dataset_path: str, source: str, expected_queries: int) -> None:
    assert report["schema_version"] == 1
    assert report["system"] == "context7"
    assert report["source"] == source
    assert report["dataset"] == dataset_path
    assert report["capture_method"] == "manual_normalized_from_tool_output"
    assert report["review_status"] == "manual_assessment_required_for_recapture"

    metrics = report["metrics"]
    assert metrics["queries"] == expected_queries
    assert metrics["hit_at"]["1"] == 1.0
    assert metrics["hit_at"]["5"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["quality"]["snippet_present_at_5_rate"] > 0.0
    assert metrics["quality"]["locale_contamination_rate"] == 0.0

    assert _item_ids(report) == _golden_item_ids(dataset_path)
    for item in report["items"]:
        assert item["first_hit_rank"] == 1
        assert item["hit_at_5"] is True
        assert item["expected_source_hit"]
        assert item["snippet_present_at_5"] is True
        assert item["manual_assessment"]


def _assert_comparable(docmancer_report: dict, context7_report: dict) -> None:
    assert docmancer_report["dataset"] == context7_report["dataset"]
    assert docmancer_report["corpus_snapshot"] == context7_report["corpus_snapshot"]
    assert _item_ids(docmancer_report) == _item_ids(context7_report)

    for metric in ["queries", "mrr"]:
        assert metric in docmancer_report["metrics"]
        assert metric in context7_report["metrics"]
    for k in ["1", "3", "5"]:
        assert k in docmancer_report["metrics"]["hit_at"]
        assert k in context7_report["metrics"]["hit_at"]
    for quality_metric in ["snippet_present_at_5_rate", "locale_contamination_rate"]:
        assert quality_metric in docmancer_report["metrics"]["quality"]
        assert quality_metric in context7_report["metrics"]["quality"]


def test_context7_riverpod_snapshot_matches_golden_dataset():
    report = _load_json("eval/results/context7_riverpod_results.json")

    _assert_context7_snapshot(
        report,
        dataset_path="eval/riverpod_golden.yaml",
        source="/websites/riverpod_dev",
        expected_queries=5,
    )


def test_context7_fastapi_snapshot_matches_golden_dataset():
    report = _load_json("eval/results/context7_fastapi_results.json")

    _assert_context7_snapshot(
        report,
        dataset_path="eval/fastapi_golden.yaml",
        source="/websites/fastapi_tiangolo",
        expected_queries=3,
    )


def test_context7_snapshots_are_comparable_with_docmancer_artifacts():
    pairs = [
        ("eval/results/docmancer_riverpod_results.json", "eval/results/context7_riverpod_results.json"),
        ("eval/results/docmancer_fastapi_results.json", "eval/results/context7_fastapi_results.json"),
    ]

    for docmancer_path, context7_path in pairs:
        _assert_comparable(_load_json(docmancer_path), _load_json(context7_path))
