import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_artifact(relative_path: str) -> dict:
    path = ROOT / relative_path
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _assert_metric(actual, expected, name: str) -> None:
    assert actual == expected, f"{name} expected {expected!r}, got {actual!r}"


def _assert_public_docs_artifact(report: dict, suite: str) -> None:
    metrics = report["metrics"]
    quality = metrics["quality"]
    hit_at = metrics["hit_at"]

    _assert_metric(hit_at["1"], 1.0, f"{suite} Hit@1")
    _assert_metric(hit_at["5"], 1.0, f"{suite} Hit@5")
    _assert_metric(metrics["mrr"], 1.0, f"{suite} MRR")
    _assert_metric(quality["locale_contamination_rate"], 0.0, f"{suite} locale_contamination_rate")

    assert "snippet_present_at_5_rate" in quality, f"{suite} missing snippet_present_at_5_rate"
    assert quality["snippet_present_at_5_rate"] > 0.0, f"{suite} snippet_present_at_5_rate must be positive"
    assert "snippet_sections_at_5_avg" in quality, f"{suite} missing snippet_sections_at_5_avg"
    assert quality["snippet_sections_at_5_avg"] > 0.0, f"{suite} snippet_sections_at_5_avg must be positive"


def test_public_docs_riverpod_artifact_regression_gate():
    report = _load_artifact("eval/results/docmancer_riverpod_results.json")

    _assert_metric(report["dataset"], "eval/riverpod_golden.yaml", "Riverpod dataset")
    _assert_metric(report["metrics"]["queries"], 5, "Riverpod query count")
    _assert_public_docs_artifact(report, "Riverpod")


def test_public_docs_fastapi_artifact_regression_gate():
    report = _load_artifact("eval/results/docmancer_fastapi_results.json")

    _assert_metric(report["dataset"], "eval/fastapi_golden.yaml", "FastAPI dataset")
    _assert_metric(report["metrics"]["queries"], 3, "FastAPI query count")
    _assert_public_docs_artifact(report, "FastAPI")
