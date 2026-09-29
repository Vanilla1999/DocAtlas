"""Regression tests for review findings; no embedding weights or oracle answers."""
from dataclasses import dataclass
from unittest.mock import patch
import math
import threading

import pytest
from docmancer.docs.domain.evidence_qualification import EvidenceQualification
from experiments.crosslingual_relevance.context_rescue import BoundedScorer, apply_rescue, installed

TEXT = 'A complete document sentence that must be assessed against its own original question. ' * 2


def rejected():
    return EvidenceQualification(False, (), None, 'insufficient_visible_match', {})


def rescue(scorer, threshold=0.7453):
    return apply_rescue(rejected(), query_id='query-original', question='question',
                        evidence_text=TEXT, source_identity='local:test',
                        scorer=scorer, threshold=threshold)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_scores_fail_closed(value):
    scorer = BoundedScorer(lambda q, t: value)
    result = rescue(scorer)
    assert not result.qualified
    assert scorer.degraded


@pytest.mark.parametrize('threshold', [float('nan'), float('inf'), -float('inf')])
def test_invalid_threshold_is_rejected_before_inference(threshold):
    calls = []
    with pytest.raises(ValueError):
        rescue(BoundedScorer(lambda q,t: calls.append(t) or 0.9), threshold)
    assert calls == []


@pytest.mark.parametrize('value', [1.01, -1.01])
def test_out_of_range_cosine_is_an_error(value):
    scorer = BoundedScorer(lambda q,t: value)
    assert not rescue(scorer).qualified
    assert scorer.degraded


def test_negative_cosine_is_valid_not_an_execution_error():
    scorer = BoundedScorer(lambda q,t: -0.4)
    assert scorer.score('q', TEXT) == -0.4
    assert not scorer.degraded


@pytest.mark.parametrize('kwargs', [{'max_evaluations': 0}, {'max_evaluations': -2},
    {'max_evaluations': True}, {'max_evaluations': 2.5}, {'timeout': 0},
    {'timeout': -1}, {'timeout': float('nan')}, {'timeout': float('inf')}])
def test_invalid_execution_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        BoundedScorer(lambda q,t: 0.9, **kwargs)


def test_one_deadline_applies_to_the_stage_not_each_call():
    now = [0.0]
    calls = []
    def slow(q, text):
        calls.append(text)
        now[0] += 6.0
        return 0.9
    with patch('experiments.crosslingual_relevance.context_rescue.time.monotonic', side_effect=lambda: now[0]):
        scorer = BoundedScorer(slow, timeout=10)
        assert scorer.score('q', TEXT + '1') == 0.9
        assert scorer.score('q', TEXT + '2') is None
        assert scorer.score('q', TEXT + '3') is None
        # Proven earlier result remains usable; no extra inference or deadline reset.
        assert scorer.score('q', TEXT + '1') == 0.9
    assert len(calls) == 2
    assert scorer.degraded


def test_deadline_includes_idle_time_between_stage_calls():
    now = [10.0]
    calls = []
    with patch('experiments.crosslingual_relevance.context_rescue.time.monotonic', side_effect=lambda: now[0]):
        scorer = BoundedScorer(lambda q,t: calls.append(t) or 0.9, timeout=10)
        assert scorer.score('q', TEXT) == 0.9
        now[0] = 21.0
        assert scorer.score('q', TEXT + 'changed') is None
    assert len(calls) == 1


def test_cache_hit_is_observable_and_does_not_consume_evaluation_budget():
    scorer = BoundedScorer(lambda q,t: 0.9, max_evaluations=1)
    assert scorer.score('q', TEXT) == 0.9
    assert scorer.score('q', TEXT) == 0.9
    assert scorer.score('q', TEXT + 'new') is None
    assert scorer.score('q', TEXT) == 0.9
    assert scorer.degraded_reason == 'evaluation_limit_reached'


def test_short_rule_is_not_silently_discarded_by_arbitrary_80_character_cutoff():
    calls = []
    result = apply_rescue(rejected(), query_id='q', question='question',
        evidence_text='The cursor expires after 60 seconds.', source_identity='local:test',
        scorer=BoundedScorer(lambda q,t: calls.append(t) or 0.9))
    assert calls
    assert result.qualified
    assert result.trace['admission_only'] is True
    assert result.covered_query_ids == ()


def test_nested_installation_fails_without_replacing_outer_question():
    outer_calls = []
    with installed(lambda q,t: outer_calls.append(q) or 0.9, question='outer'):
        with pytest.raises(RuntimeError):
            with installed(lambda q,t: 0.9, question='inner'):
                pass


def test_scoring_exception_fails_closed():
    def bad(q,t):
        raise RuntimeError('test')
    scorer = BoundedScorer(bad)
    assert not rescue(scorer).qualified
    assert scorer.degraded_reason == 'scorer_error'


def test_only_lexical_rejection_can_be_rescued():
    for reason in ['wrong_project_identity','stale_evidence','missing_local_demand',
                   'metadata_only_evidence','missing_exact_terms']:
        calls = []
        original = EvidenceQualification(False, (), None, reason, {})
        got = apply_rescue(original, query_id='q', question='q', evidence_text=TEXT,
            source_identity='local:test', scorer=BoundedScorer(lambda q,t: calls.append(t) or .99))
        assert got is original
        assert not calls
