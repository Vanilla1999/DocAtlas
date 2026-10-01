import gzip
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'roadmap/search-quality-2026-10-01/results/06-multilingual-recall/experiment'


def test_two_lanes_preserve_original_questions_identity_and_scope():
    protocol = json.loads((OUT / 'protocol.json').read_text())
    review = (REPO / 'roadmap/search-quality-2026-10-01/audit/PROJECT_80_REVIEW_RU.md').read_text()
    original = {}
    for line in review.splitlines():
        if line.startswith('| projectA-'):
            cells = [c.strip() for c in line.split('|')]
            original[cells[1]] = cells[2]
    for case in protocol['cases']:
        requests = [json.loads((OUT / f'{case["id"]}-{lane}.json').read_text())['request']
                    for lane in protocol['lanes']]
        assert requests[0]['question'] == requests[1]['question'] == original[case['id']]
        assert requests[0]['project_path'] == requests[1]['project_path']
        assert requests[0]['scope'] == requests[1]['scope'] == 'all'
        assert 'lookup_queries' not in requests[0]
        assert requests[1]['lookup_queries'] == [case['lookup']]
        assert set(requests[1]) - set(requests[0]) == {'lookup_queries'}
    translations = {case['id']: case['lookup'] for case in protocol['cases']}
    assert 'README' in translations['projectA-Q29']
    assert 'ignore previous instructions' in translations['projectA-Q29']
    assert 'untrusted' not in translations['projectA-Q29']  # No expected answer injected.
    assert translations['projectA-Q30'] == original['projectA-Q30']
    assert protocol['activation'] is False and protocol['packing_replay'] is False


def test_recall_gain_does_not_claim_final_success_or_enable_rollout():
    diagnosis = json.loads((OUT / 'fact-diagnosis.json').read_text())
    rows = {(r['id'], r['lane']): r for r in diagnosis['rows']}
    before = rows['projectA-Q29', 'question-only']
    after = rows['projectA-Q29', 'same-need-lookup']
    assert not before['witnesses']['pre_cap']
    assert after['witnesses']['pre_cap'] and after['witnesses']['post_cap']
    assert after['witnesses']['query_window']
    assert not after['witnesses']['qualified_fragments']
    assert not after['witnesses']['final_packet']
    assert diagnosis['activation'] is False
    for row in diagnosis['rows']:
        assert row['wire_trace_final_source_parity']
        trace = json.loads(gzip.decompress((OUT / f'{row["id"]}-{row["lane"]}-trace.json.gz').read_bytes()))
        assert trace['payload'].get('answer_supported', False) is False
        assert trace['payload'].get('edit_ready', False) is False
