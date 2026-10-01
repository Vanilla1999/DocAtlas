"""Bound pure question parsing, never current source/qualification decisions."""
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from docmancer.docs.domain import question_retrieval_needs as needs


def test_repeated_identical_question_reuses_immutable_syntax_work():
    question = 'What is ParseCacheCourier default timeout?'
    with patch.object(needs, 'split_question_clause_spans', wraps=needs.split_question_clause_spans) as split:
        first = needs.retrieval_needs(question)
        calls = split.call_count
        assert first and calls > 0
        second = needs.retrieval_needs(question)
        assert second == first
        assert split.call_count == calls


def test_changed_condition_and_quoted_spelling_keep_distinct_needs():
    left = 'What is `ParseCacheOwner` default timeout when preview is disabled?'
    right = left.replace('disabled', 'enabled')
    other = left.replace('ParseCacheOwner', 'parseCacheOwner')
    values = [needs.retrieval_needs(q) for q in (left, right, other)]
    assert values[0] != values[1] and values[0] != values[2]
    for question, result in zip((left, right, other), values):
        assert result
        assert all(question[n.query_span_start:n.query_span_end] == n.query_span_text for n in result)


def test_cached_need_cannot_be_mutated_into_source_authority():
    result = needs.retrieval_needs('What is ParseCacheImmutable default timeout?')
    with pytest.raises(FrozenInstanceError):
        result[0].subject = 'OtherOwner'
    assert isinstance(result, tuple)
    assert 'qualified' not in result[0].__slots__


def test_syntax_cache_is_bounded_not_a_growing_question_registry():
    question = 'What is ParseCacheOldest default timeout?'
    first = needs.retrieval_needs(question)
    for i in range(300):
        needs.retrieval_needs(f'What is ParseCacheNew{i} default timeout?')
    with patch.object(needs, 'split_question_clause_spans', wraps=needs.split_question_clause_spans) as split:
        assert needs.retrieval_needs(question) == first
        assert split.call_count > 0


def test_existing_public_input_coercion_and_empty_input_are_preserved():
    assert needs.retrieval_needs(None) == ()
    assert needs.retrieval_needs([]) == ()
    assert needs.retrieval_needs('  ') == ()
    assert needs.retrieval_needs(['CacheCompatibility']) == needs.retrieval_needs(str(['CacheCompatibility']))
