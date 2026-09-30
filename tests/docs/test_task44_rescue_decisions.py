"""Unit controls for rescue telemetry, not retrieval/model-quality evidence.

The qualification inputs in this module are synthetic boundary fixtures.
Source-policy checks must additionally run through real qualify_evidence.
"""
from __future__ import annotations

import hashlib

import pytest

from docmancer.docs.domain.evidence_qualification import EvidenceQualification
from experiments.crosslingual_relevance.context_rescue import apply_rescue, M2B_THRESHOLD
from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

QUESTION = "Нужен ли пробел перед косой чертой?"
SHORT_COMPLETE_RULE = "A space before / is required."


def _rejected():
    return EvidenceQualification(
        qualified=False, covered_query_ids=(), coverage_kind=None,
        reason="insufficient_visible_match",
        trace={"qualified": False, "qualification_reason": "insufficient_visible_match"},
    )


def _apply(scorer, *, question=QUESTION, text=SHORT_COMPLETE_RULE):
    return apply_rescue(
        _rejected(), query_id="query-original", question=question,
        evidence_text=text, source_identity="local:test", scorer=scorer,
        source_binding={"path": "docs/rule.md", "line_start": 1, "line_end": 1},
    )


def _admissions(scorer):
    return [e for e in scorer.events if e.get("decision") == "context_only_relevance"]


def test_identity_failure_is_not_a_successful_rescue_event():
    def score(_question, _text):
        return 0.99

    def identity():
        raise ValueError("model hash mismatch")

    score.identity = identity
    bounded = BoundedScorer(score)
    result = _apply(bounded)
    assert not result.qualified
    assert result.trace["context_relevance_degraded_reason"] == "scorer_identity_error"
    assert not _admissions(bounded), "an identity-vetoed attempt was recorded as admission"


def test_malformed_verified_identity_is_not_a_successful_rescue_event():
    def score(_question, _text):
        return 0.99

    score.identity = lambda: {"verified": True, "fingerprint": "not-a-content-hash"}
    bounded = BoundedScorer(score)
    result = _apply(bounded)
    assert not result.qualified
    assert result.trace["context_relevance_degraded_reason"] == "scorer_identity_error"
    assert not _admissions(bounded)


def test_prove_rescue_before_asserting_no_authority():
    bounded = BoundedScorer(lambda _q, _t: 0.99)
    result = _apply(bounded)
    # Positive control FIRST; an empty or rejected result cannot pass this test.
    assert result.qualified
    assert result.reason == "context_only_relevance"
    assert result.trace["admission_only"] is True
    admissions = _admissions(bounded)
    assert len(admissions) == 1
    assert admissions[0]["text_sha256"] == hashlib.sha256(SHORT_COMPLETE_RULE.encode()).hexdigest()
    assert admissions[0]["threshold"] == M2B_THRESHOLD == 0.7453
    assert result.covered_query_ids == ()
    assert result.coverage_kind is None
    assert result.trace["covered_query_ids"] == ()
    assert result.trace.get("answer_supported", False) is False
    assert result.trace.get("edit_ready", False) is False


def test_short_complete_evidence_is_scored_not_filtered_by_length():
    observed = []
    bounded = BoundedScorer(lambda q, t: observed.append((q, t)) or 0.99)
    assert 0 < len(SHORT_COMPLETE_RULE) < 80
    result = _apply(bounded)
    assert result.qualified
    assert observed == [(QUESTION, SHORT_COMPLETE_RULE)]


def test_raw_space_slash_literals_are_distinct_scorer_inputs_and_bindings():
    observed = []
    bounded = BoundedScorer(lambda q, t: observed.append((q, t)) or 0.99)
    question = 'Чем отличаются ` /-S` и `/-S`?'
    texts = ('The exact literal is ` /-S`.', 'The exact literal is `/-S`.')
    results = [_apply(bounded, question=question, text=t) for t in texts]
    assert observed == [(question, texts[0]), (question, texts[1])]
    assert all(r.qualified for r in results)
    assert results[0].trace["context_relevance_binding"]["text_hash"] != results[1].trace["context_relevance_binding"]["text_hash"]
    assert bounded.summary["evaluations"] == 2
    # Byte preservation only: this is NOT a semantic reranker PASS.


def test_below_threshold_has_no_admission_event():
    bounded = BoundedScorer(lambda _q, _t: 0.1)
    result = _apply(bounded)
    assert not result.qualified
    assert not _admissions(bounded)
    assert any(e.get("decision") == "below_threshold" for e in bounded.events)


def test_invalid_threshold_still_rejected():
    with pytest.raises(ValueError, match="threshold must be finite"):
        apply_rescue(
            _rejected(), query_id="q", question=QUESTION,
            evidence_text=SHORT_COMPLETE_RULE, source_identity="local:test",
            scorer=BoundedScorer(lambda _q, _t: 0.99), threshold=float("nan"),
        )
