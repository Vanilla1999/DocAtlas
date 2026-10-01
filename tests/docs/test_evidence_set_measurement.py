"""Physical partition of real bytes cannot change occurrence coverage."""
import pytest
from eval.evidence_sets_v1.span_coverage import witness_bytes_covered


def test_two_adjacent_fragments_cover_the_same_fact():
    raw = 'Cells cannot contain blocks.\n\nBlank lines are required.'
    gap = raw.index('\n\n')
    assert witness_bytes_covered(raw, (0, len(raw)), ((0, len(raw)),))
    assert witness_bytes_covered(raw, (0, len(raw)), ((0, gap), (gap + 2, len(raw))),
                                 ignored_gaps=((gap, gap + 2),))


def test_code_space_is_not_an_ignorable_gap():
    raw = '" /--disabled"'
    space = raw.index(' ')
    assert not witness_bytes_covered(raw, (0, len(raw)), ((0, space), (space + 1, len(raw))))


def test_overlapping_intervals_are_counted_once_and_order_is_irrelevant():
    raw = 'abcdef'
    assert witness_bytes_covered(raw, (0, 6), ((3, 6), (0, 4), (1, 3)))


def test_another_occurrence_does_not_cover_the_requested_occurrence():
    raw = 'same fact\n\nsame fact'
    assert not witness_bytes_covered(raw, (0, 9), ((11, len(raw)),))


@pytest.mark.parametrize('raw,gap', [('must not run', (5, 8)), ('value 42', (6, 8)),
                                    ('only in mode X', (0, 4))])
def test_nonwhitespace_cannot_be_annotated_as_ignored(raw, gap):
    with pytest.raises(ValueError):
        witness_bytes_covered(raw, (0, len(raw)), (), ignored_gaps=(gap,))


@pytest.mark.parametrize('interval', [(-1, 2), (3, 2), (0, 99), (True, 2)])
def test_invalid_interval_is_explicitly_rejected(interval):
    with pytest.raises(ValueError):
        witness_bytes_covered('text', (0, 4), (interval,))


def test_uncovered_predicate_and_condition_stay_missing():
    raw = 'When disabled, the client must not retry.'
    assert not witness_bytes_covered(raw, (0, len(raw)), ((15, len(raw)),))


def test_unicode_and_crlf_offsets_are_original_characters():
    raw = 'Жук не ждёт.\r\n\r\nЗатем идёт.'
    gap = raw.index('\r\n\r\n')
    assert witness_bytes_covered(raw, (0, len(raw)), ((0, gap), (gap + 4, len(raw))),
                                 ignored_gaps=((gap, gap + 4),))
