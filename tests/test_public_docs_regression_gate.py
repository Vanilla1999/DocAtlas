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



