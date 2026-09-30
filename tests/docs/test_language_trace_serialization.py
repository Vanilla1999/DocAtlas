"""The real observer contains immutable requirement-ID sets in its trace."""
import json
import pytest
from experiments.language_aware_context.baseline_probe import write_report


@pytest.mark.parametrize('value', [frozenset(), frozenset({'b', 'a'}), {'b', 'a'}])
def test_trace_id_sets_are_saved_as_sorted_arrays(tmp_path, value):
    path = tmp_path / 'run.json'
    write_report(path, {'trace': {'covered_requirement_ids': value}})
    assert json.loads(path.read_text()) == {'trace': {'covered_requirement_ids': sorted(value)}}


def test_unknown_objects_are_not_silently_stringified(tmp_path):
    class Unknown:
        def __str__(self):
            return 'pretend success'
    with pytest.raises(TypeError):
        write_report(tmp_path / 'bad.json', {'trace': Unknown()})
    assert not (tmp_path / 'bad.json').exists()


def test_non_string_sets_are_rejected(tmp_path):
    with pytest.raises(TypeError):
        write_report(tmp_path / 'bad.json', {'trace': {1, 2}})


def test_literal_and_source_bytes_survive_trace_encoding(tmp_path):
    raw = 'Use ` /-S`, not `/-S`.\r\n'
    path = tmp_path / 'run.json'
    write_report(path, {'payload': {'snippet': raw}, 'trace': {'ids': frozenset()}})
    assert json.loads(path.read_text())['payload']['snippet'] == raw
