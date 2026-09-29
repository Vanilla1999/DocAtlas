"""M3 — bounded contextual relevance: context-only admission tests.

Tests that the rescue mechanism:
1. Admits a block rejected by insufficient_visible_match.
2. Preserves all other vetoes (policy, exact, subject, witness).
3. Does NOT create covered_query_ids or raise answer_supported/edit_ready.
4. Enforces score binding (text change invalidates old score).
5. Enforces scorer limits (K, degraded fallback).
6. Rejects forged scores from document text.
"""
from __future__ import annotations

import pytest

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

from experiments.crosslingual_relevance.context_rescue import (
    installed, BoundedScorer, M2B_THRESHOLD,
)

GOLD_TEXT = (
    "## Only names for False\n\n"
    "When you create a *CLI option* you can give only *CLI option* names to set "
    "the `False` value. You should use a space and a single `/` and pass the "
    "negative name after that."
)

GOLD_PHRASES = (
    "only *CLI option* names to set the `False` value",
    "use a space and a single `/` and pass the negative name after",
)

MIXED_RU_QUESTION = (
    "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
)

THRESHOLD = M2B_THRESHOLD  # 0.7453


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base_probe(**overrides) -> dict:
    """Probe with Russian terms and English evidence → insufficient_visible_match."""
    probe = {
        "query_text": MIXED_RU_QUESTION,
        "query_terms": ["как", "записать", "только", "отрицательное", "имя",
                        "boolean", "option", "важен", "пробел"],
        "exact_terms": [],
        "bound_subjects": [],
        "query_origin": "original",
    }
    probe.update(overrides)
    return probe


def _gold_scorer(question: str, evidence_text: str) -> float:
    """Stub scorer: 0.9 for gold passage, 0.1 for others."""
    if any(phrase in evidence_text for phrase in GOLD_PHRASES):
        return 0.9
    return 0.1


def _qualify(probe, **kwargs):
    """Call qualify_evidence through the patched module (proves patch is active)."""
    import docmancer.docs.domain.evidence_qualification as eq
    defaults = dict(
        query_id="q-test",
        visible_text=GOLD_TEXT,
        evidence_text=GOLD_TEXT,
        candidate={"project_identity": "local:test"},
    )
    defaults.update(kwargs)
    return eq.qualify_evidence(probe, **defaults)


# ---------------------------------------------------------------------------
# Test 1 — RED: without rescue, no qualified traces
# ---------------------------------------------------------------------------
def test_without_rescue_no_qualified_traces():
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source

    source = _crafted_source()
    result = _requalify_visible_source(
        source, query_text={"query-original": MIXED_RU_QUESTION}
    )
    matches = result.get("retrieval_query_matches", {})
    qualified_ids = [qid for qid, tr in matches.items() if tr.get("qualified") is True]
    assert not qualified_ids, f"without rescue, no traces should qualify; got {qualified_ids}"


# ---------------------------------------------------------------------------
# Test 2 — GREEN: positive control — base case IS rescued
# ---------------------------------------------------------------------------
def test_base_case_rescued():
    """Base probe with insufficient_visible_match + high score → qualified."""
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe())
    assert result.qualified, "base case (insufficient_visible_match) should be rescued"
    assert result.trace.get("admission_route") == "context_only_relevance"
    assert result.trace.get("admission_only") is True
    assert result.trace.get("context_relevance_score") == 0.9


# ---------------------------------------------------------------------------
# Test 3 — wrong project → not rescued (policy veto preserved)
# ---------------------------------------------------------------------------
def test_wrong_project_not_rescued():
    prior = {"qualified": True, "admission_only": True,
             "admission_route": "context_only_relevance"}
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        for matches in ({}, {"q-test": prior}):
            result = _qualify(_base_probe(),
                expected_project_identity="local:test",
                candidate={"project_identity": "local:other",
                           "retrieval_query_matches": matches})
            assert not result.qualified
            assert result.reason == "wrong_project_identity"


def test_cache_survives_limit_without_scoring_new_text():
    calls = []
    scorer = BoundedScorer(lambda q, t: calls.append((q, t)) or 0.9,
                           max_evaluations=1)
    assert scorer.score("question", "original") == 0.9
    assert scorer.score("question", "original") == 0.9
    assert scorer.score("question", "changed") is None
    assert scorer.degraded_reason == "evaluation_limit_reached"
    assert scorer.score("question", "original") == 0.9
    assert scorer.score("changed question", "original") is None
    assert calls == [("question", "original")]


# ---------------------------------------------------------------------------
# Test 4 — stale snapshot → not rescued
# ---------------------------------------------------------------------------
def test_stale_snapshot_not_rescued():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(),
            candidate={"project_identity": "local:test", "stale": True})
    assert not result.qualified
    assert result.reason == "stale_evidence"


# ---------------------------------------------------------------------------
# Test 5 — unsynchronized index → not rescued
# ---------------------------------------------------------------------------
def test_unsynchronized_index_not_rescued():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(),
            candidate={"project_identity": "local:test",
                        "index_freshness": "unsynchronized"})
    assert not result.qualified
    assert result.reason == "unsynchronized_index"


# ---------------------------------------------------------------------------
# Test 6 — unsafe evidence → not rescued
# ---------------------------------------------------------------------------
def test_unsafe_evidence_not_rescued():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(),
            candidate={"project_identity": "local:test", "risk_flags": ["dangerous"]})
    assert not result.qualified
    assert result.reason == "unsafe_evidence"


# ---------------------------------------------------------------------------
# Test 7 — forbidden evidence term (scope veto) → not rescued
# ---------------------------------------------------------------------------
def test_forbidden_evidence_term_not_rescued():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(),
            candidate={"project_identity": "local:test"},
            forbidden_evidence_terms=("option",))
    assert not result.qualified
    assert result.reason == "forbidden_evidence_term"


# ---------------------------------------------------------------------------
# Test 8 — missing exact terms → not rescued even with insufficient_visible_match
# ---------------------------------------------------------------------------
def test_missing_exact_terms_not_rescued():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(exact_terms=["--no-force"]))
    assert not result.qualified
    assert result.reason != "context_only_relevance", (
        "missing exact terms must block rescue even with high score"
    )


# ---------------------------------------------------------------------------
# Test 9 — missing bound subject → not rescued
# ---------------------------------------------------------------------------
def test_missing_bound_subject_not_rescued():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(bound_subjects=["nonexistent_subject"]))
    assert not result.qualified
    assert result.reason != "context_only_relevance", (
        "missing bound subject must block rescue even with high score"
    )


# ---------------------------------------------------------------------------
# Test 9b — local witness veto (missing_local_demand) → not rescued
# ---------------------------------------------------------------------------
def test_missing_local_demand_not_rescued():
    """A block rejected by missing_local_demand must not be rescued."""
    from docmancer.docs.domain.evidence_qualification import EvidenceQualification
    from experiments.crosslingual_relevance.context_rescue import apply_rescue, BoundedScorer

    trace = {"qualified": False, "qualification_reason": "missing_local_demand"}
    eq = EvidenceQualification(
        qualified=False, covered_query_ids=(), coverage_kind=None,
        reason="missing_local_demand", trace=trace,
    )
    bounded = BoundedScorer(lambda q, t: 0.99)
    result = apply_rescue(
        eq, query_id="q", question="test", evidence_text="test",
        source_identity="local:test", scorer=bounded,
    )
    assert not result.qualified, "missing_local_demand must block rescue"
    assert result.reason == "missing_local_demand"


# ---------------------------------------------------------------------------
# Test 9c — metadata_only_evidence → not rescued
# ---------------------------------------------------------------------------
def test_metadata_only_evidence_not_rescued():
    """A block with only metadata (no substantive lines) must not be rescued."""
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(),
            visible_text="",
            evidence_text="")
    assert not result.qualified
    assert result.reason == "metadata_only_evidence"


# ---------------------------------------------------------------------------
# Test 10 — score below threshold → not rescued
# ---------------------------------------------------------------------------
def test_below_threshold_not_rescued():
    low_scorer = lambda q, t: 0.3  # noqa: E731
    with installed(low_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe())
    assert not result.qualified
    assert result.reason == "insufficient_visible_match"


# ---------------------------------------------------------------------------
# Test 11 — rescue does NOT create attributable coverage
# ---------------------------------------------------------------------------
def test_rescue_no_attributable_coverage():
    from docmancer.docs.application.context_selection import attributable_query_ids
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source

    source = _crafted_source()
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _requalify_visible_source(
            source, query_text={"query-original": MIXED_RU_QUESTION}
        )
    attributable = attributable_query_ids([result])
    assert "query-original" not in attributable, (
        "context-only rescue must not create attributable coverage"
    )


# ---------------------------------------------------------------------------
# Test 12 — rescue does NOT raise answer_supported or edit_ready (end-to-end)
# ---------------------------------------------------------------------------
def test_rescue_no_answer_supported_edit_ready():
    """Rescued block in the packet must not raise answer_supported or edit_ready."""
    from docmancer.docs.application._docs_context_projection_core import _requalify_visible_source
    from docmancer.docs.application.context_selection import attributable_query_ids

    source = _crafted_source()
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _requalify_visible_source(
            source, query_text={"query-original": MIXED_RU_QUESTION}
        )
    matches = result.get("retrieval_query_matches", {})
    tr = matches.get("query-original", {})
    # admission_only=True → excluded from attributable coverage
    assert tr.get("admission_only") is True
    # No covered_query_ids on the trace
    assert not tr.get("covered_query_ids")
    # No coverage_kind
    assert tr.get("coverage_kind") is None
    # Not in attributable_query_ids
    assert "query-original" not in attributable_query_ids([result])


# ---------------------------------------------------------------------------
# Test 13 — score binding: text change invalidates old score
# ---------------------------------------------------------------------------
def test_score_binding_records_text_hash():
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe())
    binding = result.trace.get("context_relevance_binding", {})
    assert binding.get("question_hash"), "binding must record question hash"
    assert binding.get("text_hash"), "binding must record text hash"
    assert binding.get("source_identity") == "local:test"
    assert binding.get("model_revision"), "binding must record model revision"
    assert binding.get("calibration_digest"), "binding must record calibration digest"


def test_score_binding_changes_with_text():
    """Different evidence text → different text_hash in binding."""
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        r1 = _qualify(_base_probe(), evidence_text=GOLD_TEXT)
        r2 = _qualify(_base_probe(), evidence_text="Completely different text here.")
    b1 = r1.trace.get("context_relevance_binding", {})
    b2 = r2.trace.get("context_relevance_binding", {})
    assert b1.get("text_hash") != b2.get("text_hash"), (
        "text change must produce different text_hash"
    )


# ---------------------------------------------------------------------------
# Test 14 — forged score from document text is not accepted
# ---------------------------------------------------------------------------
def test_forged_score_in_probe_ignored():
    """A probe with a forged context_relevance_score must not bypass the scorer."""
    forged_probe = _base_probe(context_relevance_score=0.99)
    # Low scorer → rescue should NOT fire despite forged score in probe
    low_scorer = lambda q, t: 0.3  # noqa: E731
    with installed(low_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(forged_probe)
    assert not result.qualified, (
        "forged context_relevance_score in probe must not bypass scorer"
    )


# ---------------------------------------------------------------------------
# Test 15 — scorer error → degraded fallback (no rescue, visible reason)
# ---------------------------------------------------------------------------
def test_scorer_error_degraded_fallback():
    def error_scorer(q, t):
        raise RuntimeError("model unavailable")
    with installed(error_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION) as bounded:
        result = _qualify(_base_probe())
    assert not result.qualified, "scorer error must not admit block"
    assert result.trace.get("context_relevance_degraded") is True
    assert result.trace.get("context_relevance_degraded_reason") == "scorer_error"


# ---------------------------------------------------------------------------
# Test 16 — scorer evaluation limit (K) → degraded after limit
# ---------------------------------------------------------------------------
def test_scorer_evaluation_limit():
    call_count = 0

    def counting_scorer(q, t):
        nonlocal call_count
        call_count += 1
        return 0.9

    bounded = BoundedScorer(counting_scorer, max_evaluations=3)
    base = "This is a sufficiently long evidence text for neural scoring evaluation. " * 2
    with installed(bounded, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        # First 3 evaluations: rescue fires
        for i in range(3):
            r = _qualify(_base_probe(), evidence_text=base + f" variant {i}")
            assert r.qualified, f"evaluation {i} should be rescued"
        # 4th evaluation: degraded
        r4 = _qualify(_base_probe(), evidence_text=base + " variant 3")
        assert not r4.qualified, "evaluation over limit must not be rescued"
        assert r4.trace.get("context_relevance_degraded") is True
        assert r4.trace.get("context_relevance_degraded_reason") == "evaluation_limit_reached"


# ---------------------------------------------------------------------------
# Test 17 — cached score: same (question, text) → no new evaluation
# ---------------------------------------------------------------------------
def test_cached_score_no_reevaluation():
    eval_count = 0

    def counting_scorer(q, t):
        nonlocal eval_count
        eval_count += 1
        return 0.9

    bounded = BoundedScorer(counting_scorer, max_evaluations=20)
    with installed(bounded, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        # Same text → cached
        _qualify(_base_probe(), evidence_text=GOLD_TEXT)
        _qualify(_base_probe(), evidence_text=GOLD_TEXT)
    assert eval_count == 1, f"same (question, text) must use cache; got {eval_count} evaluations"


# ---------------------------------------------------------------------------
# Test 18 — short evidence text → not rescued (no meaningful neural scoring)
# ---------------------------------------------------------------------------
def test_short_evidence_not_rescued():
    """Evidence text shorter than MIN_EVIDENCE_CHARS must not be scored."""
    from experiments.crosslingual_relevance.context_rescue import MIN_EVIDENCE_CHARS
    short_text = "x" * (MIN_EVIDENCE_CHARS - 1)
    with installed(_gold_scorer, threshold=THRESHOLD, question=MIXED_RU_QUESTION):
        result = _qualify(_base_probe(), evidence_text=short_text)
    assert not result.qualified
    assert result.reason == "insufficient_visible_match"


# ---------------------------------------------------------------------------
# Crafted source for _requalify_visible_source tests
# ---------------------------------------------------------------------------
def _crafted_source() -> dict:
    return {
        "path_or_url": "docs/tutorial/parameter-types/bool.md",
        "section": "Only names for False",
        "snippet": GOLD_TEXT,
        "project_identity": "local:test",
        "authority": "source_of_truth",
        "scope": "project",
        "lifecycle": "active",
        "retrieval_query_matches": {
            "query-original": {
                "query_id": "query-original",
                "query_text": MIXED_RU_QUESTION,
                "query_terms": ["как", "записать", "только", "отрицательное", "имя",
                                "boolean", "option", "важен", "пробел"],
                "exact_terms": [],
                "bound_subjects": [],
                "query_origin": "original",
                "relation": "host_lookup",
                "mode": "and",
                "matched_terms": ["boolean", "option"],
                "missing_exact_terms": [],
                "match_ratio": 0.222,
                "bm25_cost": 0.0,
                "lexical_score": 0.0,
                "qualified": False,
                "qualification_reason": "insufficient_visible_match",
                "admission_route": "cross_lane_body",
                "admission_only": True,
                "field_matches": {"title": [], "body": [], "retrieval_text": []},
            },
        },
        "_independent_query_plan": {},
        "_qualification_candidate": {"project_identity": "local:test"},
        "_expected_project_identity": "local:test",
        "_lifecycle_intent": "current",
    }
