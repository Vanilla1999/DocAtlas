"""Tests for live benchmark: provider_id, storage isolation, raw output collisions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from eval.live_mcp_context7_benchmark import (
    BenchmarkCase,
    DocAtlasDirectProvider,
    NormalizedBenchmarkResult,
    PreindexDiagnostics,
)


def _make_docatlas_result(
    case: BenchmarkCase,
    status: str = "success",
    provider_id: str = "docatlas_zero_setup",
    sources: list | None = None,
) -> NormalizedBenchmarkResult:
    return NormalizedBenchmarkResult(
        provider="docatlas",
        provider_id=provider_id,
        provider_mode="live_direct_api",
        mode="zero-setup" if "zero" in provider_id else "preindexed",
        case_id=case.id,
        query=case.query,
        suite=case.suite,
        status=status,
        latency_ms=10.0,
        setup_calls=1,
        sources=sources or [],
        snippets=[],
        answer_text="test answer",
        warnings=[],
        reason_codes=[],
        exact_version_used=None,
        contamination_hits=[],
        forbidden_source_hits=[],
        expected_source_hits=[],
        manual_review_required=False,
        preindex=PreindexDiagnostics(attempted=False) if "zero" in provider_id else None,
    )


def test_provider_id_attributes():
    """DocAtlasDirectProvider sets provider_id matching its benchmark_mode."""
    zs = DocAtlasDirectProvider()
    zs.benchmark_mode = "zero-setup"
    zs.provider_id = "docatlas_zero_setup"
    assert zs.name == "docatlas"
    assert zs.provider_id == "docatlas_zero_setup"
    assert zs.benchmark_mode == "zero-setup"

    pi = DocAtlasDirectProvider()
    pi.benchmark_mode = "preindexed"
    pi.provider_id = "docatlas_preindexed"
    assert pi.name == "docatlas"
    assert pi.provider_id == "docatlas_preindexed"
    assert pi.benchmark_mode == "preindexed"


def test_provider_id_uniqueness_in_both_mode():
    """Both zero-setup and preindexed providers must have distinct provider_ids."""
    zs = DocAtlasDirectProvider()
    zs.benchmark_mode = "zero-setup"
    zs.provider_id = "docatlas_zero_setup"

    pi = DocAtlasDirectProvider()
    pi.benchmark_mode = "preindexed"
    pi.provider_id = "docatlas_preindexed"

    ids = {zs.provider_id, pi.provider_id}
    assert len(ids) == 2
    assert zs.provider_id != pi.provider_id


def test_raw_output_dir_uses_provider_id():
    """Raw output dir must be based on provider_id, not provider name."""
    zs = DocAtlasDirectProvider()
    zs.benchmark_mode = "zero-setup"
    zs.provider_id = "docatlas_zero_setup"

    pi = DocAtlasDirectProvider()
    pi.benchmark_mode = "preindexed"
    pi.provider_id = "docatlas_preindexed"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        dir_zs = out / zs.provider_id
        dir_pi = out / pi.provider_id
        dir_zs.mkdir(parents=True)
        dir_pi.mkdir(parents=True)

        case = BenchmarkCase(id="test_case", query="test", suite="public-docs")
        (dir_zs / f"{case.id}.json").write_text("{}")
        (dir_pi / f"{case.id}.json").write_text("{}")

        assert (dir_zs / f"{case.id}.json").exists()
        assert (dir_pi / f"{case.id}.json").exists()
        assert dir_zs.name == "docatlas_zero_setup"
        assert dir_pi.name == "docatlas_preindexed"


def test_provider_id_in_raw_json():
    """Raw JSON must include provider and provider_id fields."""
    raw = {
        "case_id": "fastapi_depends",
        "provider": "docatlas",
        "provider_id": "docatlas_preindexed",
        "mode": "preindexed",
    }
    assert raw["provider"] == "docatlas"
    assert raw["provider_id"] == "docatlas_preindexed"
    assert raw["provider"] != raw["provider_id"]


def test_normalized_result_has_provider_id():
    """NormalizedBenchmarkResult must carry provider_id field."""
    case = BenchmarkCase(id="test", query="test", suite="public-docs")
    r = _make_docatlas_result(case, provider_id="docatlas_zero_setup")
    assert r.provider == "docatlas"
    assert r.provider_id == "docatlas_zero_setup"
    assert r.provider != r.provider_id


def test_compute_suite_metrics_groups_by_provider_id():
    """compute_suite_metrics should group by provider_id, not by provider name."""
    from eval.live_mcp_context7_benchmark import compute_suite_metrics

    case = BenchmarkCase(id="test", query="test", suite="public-docs")
    zs = _make_docatlas_result(case, provider_id="docatlas_zero_setup", status="success")
    pi = _make_docatlas_result(case, provider_id="docatlas_preindexed", status="success")
    c7 = NormalizedBenchmarkResult(
        provider="context7", provider_id="context7_zero_setup",
        provider_mode="live_mcp_stdio", mode="zero-setup",
        case_id=case.id, query=case.query, suite="public-docs",
        status="success", latency_ms=5.0, setup_calls=1,
        sources=[], snippets=[], answer_text="c7",
        warnings=[], reason_codes=[], exact_version_used=None,
        contamination_hits=[], forbidden_source_hits=[],
        expected_source_hits=[], manual_review_required=False,
    )

    results = [zs, pi, c7]
    sm = compute_suite_metrics(results, "public-docs")

    assert "docatlas_zero_setup" in sm
    assert "docatlas_preindexed" in sm
    assert "context7_zero_setup" in sm
    assert sm["docatlas_zero_setup"]["provider"] == "docatlas"
    assert sm["docatlas_preindexed"]["provider"] == "docatlas"
    assert sm["context7_zero_setup"]["provider"] == "context7"


def test_provider_id_isolation_in_results_grouping():
    """Results grouped by case_id and provider_id should not collide."""
    case = BenchmarkCase(id="same_case", query="test", suite="public-docs")
    zs = _make_docatlas_result(case, provider_id="docatlas_zero_setup")
    pi = _make_docatlas_result(case, provider_id="docatlas_preindexed")

    by_id: dict[str, dict[str, NormalizedBenchmarkResult]] = {}
    for r in [zs, pi]:
        by_id.setdefault(r.case_id, {})[r.provider_id] = r

    assert len(by_id["same_case"]) == 2
    assert "docatlas_zero_setup" in by_id["same_case"]
    assert "docatlas_preindexed" in by_id["same_case"]
    assert by_id["same_case"]["docatlas_zero_setup"] is zs
    assert by_id["same_case"]["docatlas_preindexed"] is pi


@pytest.mark.parametrize("provider_id", [
    "docatlas_zero_setup",
    "docatlas_preindexed",
    "context7_zero_setup",
])
def test_exact_version_metrics_no_false_correctness(provider_id: str):
    """When all exact-version results are empty, correctness must be None, not 1.0."""
    from eval.live_mcp_context7_benchmark import compute_metrics

    case = BenchmarkCase(id="exact_fastapi_version", query="test", suite="exact-version")
    r = _make_docatlas_result(case, status="empty_index", provider_id=provider_id)
    m = compute_metrics([r])

    assert m["exact_version_success_count"] == 0
    assert m["exact_version_empty_count"] == 1
    assert m["exact_version_coverage_rate"] == 0.0
    assert m["exact_version_correctness_on_success"] is None


def test_exact_version_metrics_with_mixed_results():
    """exact-version metrics must distinguish success vs empty vs not_supported."""
    from eval.live_mcp_context7_benchmark import compute_metrics

    ev_case = BenchmarkCase(id="exact_fastapi_version", query="test", suite="exact-version")
    pd_case = BenchmarkCase(id="fastapi_depends", query="test", suite="public-docs")

    results = [
        _make_docatlas_result(ev_case, status="success", provider_id="docatlas_preindexed"),
        _make_docatlas_result(ev_case, status="empty_index", provider_id="docatlas_preindexed"),
        _make_docatlas_result(ev_case, status="not_supported", provider_id="docatlas_preindexed"),
        _make_docatlas_result(pd_case, status="success", provider_id="docatlas_preindexed"),
    ]

    m = compute_metrics(results)
    assert m["exact_version_success_count"] == 1
    assert m["exact_version_empty_count"] == 1
    assert m["exact_version_not_supported_count"] == 1
    assert m["exact_version_coverage_rate"] == pytest.approx(1 / 3, abs=0.01)
