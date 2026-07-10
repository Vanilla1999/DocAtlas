from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("context7_parity_eval", ROOT / "eval" / "context7_parity" / "parity_eval.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _dataset(module):
    return module.load_jsonl(ROOT / "eval" / "context7_parity" / "dataset.jsonl")


def _trace(item: dict, provider: str, *, phase: str = "warm", source: str | None = None) -> dict:
    evidence = item["expected_evidence"]
    symbol = evidence["symbols"][0]
    snippet = "x = 1" if item["ecosystem"] == "python" else "const x = 1;"
    return {
        "provider": provider,
        "case_id": item["id"],
        "first_tool": item["expected_first_tool"][provider],
        "results": [{"source": source or evidence["source"], "section": evidence["section"], "content": symbol, "snippet": snippet}],
        "latency_ms": 10,
        "phase": phase,
        "resolved_version": item["requested_version"],
        "network_fetch_count": 0,
        "lifecycle_call_count": 0,
    }


def test_committed_parity_dataset_has_150_version_sensitive_items() -> None:
    module = _module()
    items = _dataset(module)

    module.validate_dataset(items)
    assert len(items) == 150
    assert {item["ecosystem"] for item in items} >= {"python", "javascript", "typescript", "dart", "flutter"}
    assert {item["question_type"] for item in items} == {"api_usage", "migration", "configuration", "code_example", "reference"}
    assert all(item["requested_version"] for item in items)
    assert all(item["allowed_corpus"]["policy"] == "official-docs-only" for item in items)


def test_generator_reproduces_committed_dataset() -> None:
    module = _module()
    generator_spec = importlib.util.spec_from_file_location("context7_parity_generator", ROOT / "eval" / "context7_parity" / "generate_dataset.py")
    generator = importlib.util.module_from_spec(generator_spec)
    assert generator_spec.loader is not None
    generator_spec.loader.exec_module(generator)
    catalog = json.loads((ROOT / "eval" / "context7_parity" / "catalog.json").read_text(encoding="utf-8"))

    assert generator.build_items(catalog) == _dataset(module)


def test_report_has_per_item_metrics_confidence_intervals_and_no_claim_for_partial_coverage(tmp_path: Path) -> None:
    module = _module()
    items = _dataset(module)
    trace_path = tmp_path / "docatlas.jsonl"
    trace_path.write_text(json.dumps(_trace(items[0], "docatlas")) + "\n", encoding="utf-8")

    report = module.build_report(ROOT / "eval" / "context7_parity" / "dataset.jsonl", [trace_path])

    assert report["dataset"]["items"] == 150
    assert report["providers"]["docatlas"]["confidence_intervals_95"]["hit_at_1"]
    assert report["per_item"]["docatlas"][0]["id"] == items[0]["id"]
    assert report["comparison"]["comparable"] is False
    assert "No comparative claim" in report["comparison"]["unsupported_cases"][-1]["reason"]


def test_complete_equal_captures_are_comparable(tmp_path: Path) -> None:
    module = _module()
    items = _dataset(module)
    docatlas = tmp_path / "docatlas.jsonl"
    context7 = tmp_path / "context7.jsonl"
    docatlas.write_text("".join(json.dumps(_trace(item, "docatlas", phase="cold" if index == 0 else "warm")) + "\n" for index, item in enumerate(items)), encoding="utf-8")
    context7.write_text("".join(json.dumps(_trace(item, "context7")) + "\n" for item in items), encoding="utf-8")

    report = module.build_report(ROOT / "eval" / "context7_parity" / "dataset.jsonl", [docatlas, context7])

    assert report["comparison"]["comparable"] is True
    assert report["providers"]["docatlas"]["hit_at_3"] == 1.0
    assert report["providers"]["docatlas"]["cold_latency_ms"] == 10.0
    assert report["providers"]["docatlas"]["warm_latency_ms"] == 10.0


def test_source_contamination_prevents_a_comparative_claim(tmp_path: Path) -> None:
    module = _module()
    items = _dataset(module)
    docatlas = tmp_path / "docatlas.jsonl"
    context7 = tmp_path / "context7.jsonl"
    docatlas.write_text("".join(json.dumps(_trace(item, "docatlas")) + "\n" for item in items), encoding="utf-8")
    context7.write_text("".join(json.dumps(_trace(item, "context7", source="https://untrusted.example/test") if index == 0 else _trace(item, "context7")) + "\n" for index, item in enumerate(items)), encoding="utf-8")

    report = module.build_report(ROOT / "eval" / "context7_parity" / "dataset.jsonl", [docatlas, context7])

    assert report["providers"]["context7"]["source_contamination_rate"] > 0.0
    assert report["comparison"]["comparable"] is False
