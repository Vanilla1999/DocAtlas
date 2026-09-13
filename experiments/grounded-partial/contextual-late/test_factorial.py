"""Counterexamples for confounding and fabricated source evidence in fusion."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'research_factorial', Path(__file__).parents[1] / 'research-suite/evaluate.py'
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_descriptions_change_sparse_ranking_without_becoming_evidence():
    pool = [{'key': 'a', 'text': 'alpha'}, {'key': 'b', 'text': 'beta'}]
    orders = {'plain': ['a', 'b'], 'late': ['a', 'b']}
    lanes = m.hybrid_factorial('needle', pool, orders, {'a': '', 'b': 'needle'})
    assert lanes['hybrid_plain'][0]['key'] == 'a'
    assert lanes['hybrid_context_bm25_plain'][0]['key'] == 'b'
    assert all(c is pool[0] or c is pool[1] for lane in lanes.values() for c in lane)
    assert all('needle' not in c['text'] for lane in lanes.values() for c in lane)


def test_equal_factors_produce_identical_lanes():
    pool = [{'key': 'a', 'text': 'alpha'}, {'key': 'b', 'text': 'beta'}]
    lanes = m.hybrid_factorial('beta', pool, {'plain': ['b', 'a'], 'late': ['b', 'a']}, {'a': '', 'b': ''})
    assert len(lanes) == 4
    assert all(lane == lanes['hybrid_plain'] for lane in lanes.values())


@pytest.mark.parametrize('late', [['a'], ['a', 'a'], ['a', 'foreign']])
def test_missing_duplicate_or_cross_project_dense_candidates_rejected(late):
    pool = [{'key': 'a', 'text': 'alpha'}, {'key': 'b', 'text': 'beta'}]
    with pytest.raises(ValueError, match='same complete source pool'):
        m.hybrid_factorial('alpha', pool, {'plain': ['a', 'b'], 'late': late}, {'a': '', 'b': ''})
