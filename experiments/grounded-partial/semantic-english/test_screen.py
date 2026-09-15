"""Boundary tests use test doubles, never reported as model accuracy."""
from copy import deepcopy
import math
import pytest
from screen import load_data, model_input, calibrate, matrix, input_key


def calibration():
    return [{**r, 'score': .9 if r['expected'] else .1}
            for r in load_data()['pairs'] if r['split'] == 'calibration']


def test_english_unchanged_source_bound_split():
    assert len(load_data()['pairs']) == 56


def test_no_labels_enter_scorer():
    for r in load_data()['pairs']:
        assert set(model_input(r)) == {'query', 'document'}
        assert model_input(r)['document'] == r['body']


def test_threshold_uses_only_calibration():
    rows = calibration(); rows[0]['split'] = 'evaluation'
    with pytest.raises(ValueError): calibrate(rows)


def test_perfect_test_double_is_not_real_measurement():
    result = calibrate(calibration())
    assert result['threshold'] == .9 and result['matrix']['TP'] == 12
    assert result['matrix']['FP'] == 0 and result['passed']


def test_nonseparable_does_not_smuggle_reject_all_threshold():
    rows = calibration()
    for r in rows: r['score'] = .5
    result = calibrate(rows)
    assert result['threshold'] is None and not result['passed']


@pytest.mark.parametrize('value', [math.nan, math.inf, -1., 1.1])
def test_bad_scores_are_errors(value):
    rows = calibration(); rows[0]['score'] = value
    with pytest.raises(ValueError): calibrate(rows)


def test_threshold_ties_are_deterministic():
    rows = calibration()
    assert calibrate(rows) == calibrate(list(reversed(rows)))


def test_evaluation_not_used_to_adjust_threshold():
    result = calibrate(calibration())
    rows = [{**r, 'score': .99} for r in load_data()['pairs'] if r['split'] == 'evaluation']
    assert matrix(rows, result['threshold'])['FP'] == 16
    assert result['threshold'] == .9


def test_exact_input_identity_changes_for_new_window():
    row = model_input(load_data()['pairs'][0]); other = deepcopy(row)
    other['document'] = other['document'][:-10]
    assert input_key(row) != input_key(other)


def test_frozen_English_baseline():
    rows = load_data()['pairs']
    cal = matrix([r for r in rows if r['split'] == 'calibration'], baseline=True)
    ev = matrix([r for r in rows if r['split'] == 'evaluation'], baseline=True)
    assert [cal[k] for k in ('TP','FN','FP','TN')] == [3,9,7,9]
    assert [ev[k] for k in ('TP','FN','FP','TN')] == [7,5,6,10]
