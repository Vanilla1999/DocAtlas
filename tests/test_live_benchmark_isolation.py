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



























