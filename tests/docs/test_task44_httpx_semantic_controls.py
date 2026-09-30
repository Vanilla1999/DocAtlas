"""Viewed-corpus semantic diagnostics. NOT calibration or independent holdout.

No threshold is selected here. Missing model configuration is a visible skip;
execution degradation is a failure, never a semantic PASS. Real BGE inference
is required; no oracle scorer or canned model responses are used.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "eval/evidence_quality_v2/sources/httpx/docs/advanced/timeouts.md"
needs_reranker = pytest.mark.skipif(
    not all(os.environ.get(k) for k in (
        "DOCATLAS_RERANKER_MODEL_DIR", "DOCATLAS_RERANKER_MODEL_MANIFEST")),
    reason="real local BGE model+manifest required; diagnostic NOT executed",
)


def _span(start, end):
    lines = DOC.read_text(encoding="utf-8").splitlines(keepends=True)
    assert 1 <= start <= end <= len(lines)
    return "".join(lines[start-1:end])


@needs_reranker
@pytest.mark.parametrize(("question", "positive", "negative", "required"), [
    ("Какие четыре вида тайм-аутов различает HTTPX?",
     (45, 61), (1, 4), ("connect", "read", "write", "pool")),
    ("Какое поведение timeout по умолчанию в HTTPX: сколько секунд и какое исключение?",
     (1, 4), (45, 61), ("TimeoutException", "5 seconds", "network inactivity")),
    ("Как отключить тайм-аут только для отдельного запроса, не меняя default client?",
     (19, 28), (30, 39), ("individual request", "timeout=None")),
    ("Как отключить timeouts по умолчанию для всех запросов Client, а не только одного?",
     (30, 39), (19, 28), ("client instance", "Disable all timeouts by default")),
])
def test_httpx_fact_and_condition_direction(question, positive, negative, required, record_property):
    from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    positive_text, negative_text = _span(*positive), _span(*negative)
    assert all(phrase in positive_text for phrase in required)
    assert positive_text != negative_text
    bounded = BoundedScorer(reranker_scorer, score_range=(0, 1),
                            max_evaluations=60, timeout=10.0, capture_text=True)
    identity = bounded.identity()
    assert identity.get("verified") is True
    scores = [bounded.score(question, text) for text in (positive_text, negative_text)]
    record_property("scorer_identity", identity)
    record_property("scores", scores)
    record_property("scorer_events", bounded.events)
    assert not bounded.degraded, bounded.summary
    assert all(score is not None for score in scores)
    assert scores[0] > scores[1], "wrong fact/direction ranks above the requested witness"


def test_canonical_httpx_control_spans_contain_the_declared_facts():
    assert all(t in _span(1, 4) for t in ("TimeoutException", "5 seconds", "network inactivity"))
    assert all(t in _span(45, 61) for t in ("connect", "read", "write", "pool"))
    assert all(t in _span(19, 28) for t in ("individual request", "timeout=None"))
    assert all(t in _span(30, 39) for t in ("client instance", "Disable all timeouts by default"))
