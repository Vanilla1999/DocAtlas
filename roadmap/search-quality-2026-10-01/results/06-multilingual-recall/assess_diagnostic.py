"""Fact-specific trace diagnosis; headings/identifiers alone are not witnesses."""
import gzip
import json
from pathlib import Path

from eval.evidence_quality_v2.semantic import normalize_markdown

OUT = Path(__file__).resolve().parent / 'experiment'
FACTS = {
    'projectA-Q29': {'path': 'docs/security/mcp-runtime-threat-model.md',
        'text': 'Ordinary repository Markdown is cited data.'},
    'projectA-Q30': {'path': 'wiki/Architecture.md',
        'text': "Each project identity receives isolated SQLite index\nstate and extracted artifacts, so one repository's project docs cannot satisfy\nanother repository's query."},
}


def main():
    provenance = json.loads((OUT / 'provenance.json').read_text())
    root = Path(provenance['fixture'])
    rows = []
    for identity, fact in FACTS.items():
        assert fact['text'] in (root / fact['path']).read_text()
        for lane in ('question-only', 'same-need-lookup'):
            trace = json.loads(gzip.decompress((OUT / f'{identity}-{lane}-trace.json.gz').read_bytes()))
            stages = {
                'pre_cap': [s for w in trace['pre_cap_windows'] for s in w['before']],
                'post_cap': [s for w in trace['pre_cap_windows'] for s in w['after']],
                'query_window': [s for w in trace['stages']['query_window'] for s in w['sources']],
                'qualified_fragments': [s for w in trace['stages']['qualified_fragments'] for s in w['after']],
                'final_packet': trace['payload'].get('sources', []),
            }
            witnesses = {stage: [{'evidence_id': source.get('evidence_id'), 'path': source.get('path_or_url'),
                                  'snippet': source.get('snippet')} for source in sources
                if source.get('path_or_url') == fact['path'] and
                   normalize_markdown(fact['text']) in normalize_markdown(source.get('snippet', ''))]
                for stage, sources in stages.items()}
            first_loss = 'retrieval' if not witnesses['pre_cap'] else next(
                (stage for stage in stages if not witnesses[stage]), 'none')
            wire = json.loads((OUT / f'{identity}-{lane}.json').read_text())['wire']
            payload = wire.get('structuredContent') or json.loads(wire['content'][0]['text'])
            signatures = lambda p: [(s['path_or_url'], s['snippet']) for s in p.get('sources', [])]
            assert signatures(payload) == signatures(trace['payload'])
            rows.append({'id': identity, 'lane': lane, 'fact': fact,
                'witnesses': witnesses, 'first_observed_loss': first_loss,
                'boundary_caution': 'qualified_fragments missing covers application candidate eligibility/order plus qualification; not an isolated predicate attribution',
                'wire_trace_final_source_parity': True})
    with (OUT / 'fact-diagnosis.json').open('x') as handle:
        json.dump({'rows': rows, 'activation': False,
                   'decision': 'Stop: Q29 recall restored but useful policy lost downstream; Q30 unchanged pre-cap miss'}, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print([(r['id'], r['lane'], r['first_observed_loss']) for r in rows])


if __name__ == '__main__':
    main()
