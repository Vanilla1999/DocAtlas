"""Development controls, not held-out validation."""
import importlib.util
import json
from pathlib import Path


def test_native_focused_lookup_delivers_missing_part(tmp_path):
    path = Path(__file__).resolve().parents[2] / 'v2plan' / 'lookup_gap_probe.py'
    spec = importlib.util.spec_from_file_location('lookup_gap_probe', path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    output = tmp_path / 'probe'
    probe.run(output)
    rows = json.loads((output / 'summary.json').read_text())
    assert len(rows) == 8
    for row in rows:
        snippets = [s['snippet'] for s in row['sources']]
        assert '# Guide\n\n' + probe.KNOWN in snippets
        expected_second = row['arm'] == 'focused' and row['case'] in ('both', 'partial')
        assert ('# Guide\n\n' + probe.CASES[row['case']] in snippets) == expected_second
        assert row['flags']['answer_supported'] is False
        assert row['flags']['edit_ready'] is False
        assert row['flags']['support_status'] == 'retrieval_only'
        if row['case'] in ('both', 'partial'):
            raw = json.loads((output / row['case'] / (row['arm'] + '.json')).read_text())
            candidates = [s for batch in raw['trace']['stages']['retrieved_candidates']
                          for s in batch['sources']]
            assert any(probe.CASES[row['case']] in s['snippet'] for s in candidates)
            decisions = raw['trace']['executed_decisions']
            assert any(probe.CASES[row['case']] in (event['snippet'] or '')
                       and event['reason'] == ('no_new_direction' if row['arm'] == 'original' else 'accepted')
                       for event in decisions)
