"""One corrected 1500-unit owner replay; all native admission vetoes retained."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from admission_layer_probe import inspect_layers
from grounded_loss_audit import ReadOnlyStore, load_probe, witness_groups, classify
from eval.evidence_quality_v2.run import load_protocol, registry_for, documents_for
from eval.evidence_quality_v2.semantic import assess_context


def corrected_reason(proposal, *, question, identity, probe):
    item = proposal['item']
    if item['char_span'] != proposal['expected_span']:
        return 'proposal_span_changed'
    source = probe.source_window_eligibility(item, question=question, expected_project_identity=identity)
    if not source.eligible:
        return source.reason
    raw = item['_reference_evidence']['raw_document']
    start, end = item['char_span']
    atoms = probe._atom_spans(raw, *proposal['owner_span'])
    touched = [a for a in atoms if a.start < end and start < a.end and a.atom_type in ('code', 'list', 'table')]
    if touched and item['char_span'] != proposal['owner_span']:
        return 'incomplete_owner'
    if proposal['structural_reason']:
        return proposal['structural_reason']
    layers = inspect_layers(item, question=question, identity=identity, probe=probe)
    if layers['reference_reason']:
        return layers['reference_reason']
    if layers['literal_missing']:
        return 'missing_exact_terms'
    if any(s['location'] == 'unresolved' for s in layers['subjects']):
        return 'missing_bound_subject'
    # No condition/topic removal or new interpretation: original native decision.
    return None if layers['native_read_allowed'] else layers['native_read_reason']


def run(input_dir, output_dir):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    probe = load_probe()
    protocol, cases, manifest = load_protocol()
    archived_bytes = (input_dir / 'results.json').read_bytes()
    archived = json.loads(archived_bytes)
    cells = {r['case_id']: r for r in archived if r['policy'] == 'owner'
             and r['budget'] == 1500 and not r['topic_relaxed']}
    results = []
    for case in cases:
        old = cells[case['id']]
        retrieval = old['retrieval']
        store = ReadOnlyStore(input_dir / case['project_group'] / 'passages.db', retrieval['generation_id'])
        documents = documents_for(case['project_group'], manifest)
        with store._connect() as connection:
            snapshots = connection.execute('SELECT source, content, metadata_json FROM generation_sources WHERE generation_id=?',
                                           (store.generation,)).fetchall()
        source_metadata = {s['source']: json.loads(s['metadata_json']) for s in snapshots}
        for s in snapshots:
            if s['content'] != documents[source_metadata[s['source']]['project_doc_path']]:
                raise ValueError('archived_source_changed')
        metadata = next(iter(source_metadata.values()))
        filters = {k: metadata[k] for k in ('project_identity', 'project_path', 'source_class')}
        context = probe.SourceReferenceContext(store, question=case['question'], filters=filters)
        proposals, omissions, _ = probe.inventory(store, question=case['question'], filters=filters,
                                                 policy='owner', retrieval=retrieval, context=context)
        if {p['proposal_id'] for p in proposals} != {t['proposal_id'] for t in old['trace']}:
            raise ValueError('inventory_changed')
        plan = probe.build_documentation_query_plan(case['question']).as_payload()
        check = lambda p: corrected_reason(p, question=case['question'], identity=filters['project_identity'], probe=probe)
        result = probe.ordered_packet(proposals, budget=1500, check=check,
                    build=lambda pp: probe.render_packet([p['item'] for p in pp], query_plan=plan))
        result.pop('snapshot', None)
        registry = registry_for(case['project_group'], manifest)
        assessment = assess_context(case, result['payload'] or {'sources': []}, registry)
        baseline_raw = json.loads((input_dir / case['project_group'] / (case['id'] + '-baseline.json')).read_text())
        if not isinstance(baseline_raw, list):
            raise ValueError('baseline_unavailable')
        baseline = assess_context(case, baseline_raw[0], registry)
        layers = [dict(inspect_layers(p['item'], question=case['question'], identity=filters['project_identity'], probe=probe),
                       proposal_id=p['proposal_id'], corrected_reason=check(p)) for p in proposals]
        proposal_rows = [{'path_or_url': p['item']['project_doc_path'], 'snippet': p['item']['snippet']} for p in proposals]
        retrieved_rows = [{'path_or_url': source_metadata[h['source']]['project_doc_path'], 'snippet': h['text']}
                          for h in retrieval['candidates']]
        admitted = [r for r, p in zip(proposal_rows, proposals) if check(p) is None]
        claims = []
        for claim in case['required_claims']:
            cid = claim['id']
            stages = {name: witness_groups(claim, rows) for name, rows in (
                ('source', [{'path_or_url': path, 'snippet': text} for path, text in documents.items()]),
                ('retrieval', retrieved_rows), ('proposals', proposal_rows), ('admitted', admitted),
                ('final', (result['payload'] or {}).get('sources', [])))}
            claims.append({'claim_id': cid, 'baseline': baseline['claims'][cid]['status'],
                           'historical': old['assessment']['claims'][cid]['status'],
                           'corrected': assessment['claims'][cid]['status'],
                           'attribution': classify(stages), 'literal_groups': stages})
        results.append(dict(result, case_id=case['id'], answerability=case['answerability'], budget=1500,
                            policy='owner', assessment=assessment, claims=claims, layers=layers, omissions=omissions,
                            historical_trace=old['trace'], historical_assessment=old['assessment'],
                            diagnostic_only=True, eligible_for_rollout=False))
    losses = [(r, c) for r in results for c in r['claims'] if c['baseline'] == 'supported' and c['corrected'] != 'supported']
    summary = {'cases': len(results), 'packets': sum(bool(r['payload']) for r in results),
               'historical_supported': sum(c['historical'] == 'supported' for r in results for c in r['claims']),
               'corrected_supported': sum(c['corrected'] == 'supported' for r in results for c in r['claims']),
               'baseline_supported': sum(c['baseline'] == 'supported' for r in results for c in r['claims']),
               'baseline_loss_count': len(losses), 'baseline_loss_attribution': dict(Counter(c['attribution'] for _, c in losses)),
               'baseline_loss_ids': [r['case_id'] + ':' + c['claim_id'] for r, c in losses],
               'recovered_vs_historical': [r['case_id'] + ':' + c['claim_id'] for r in results for c in r['claims']
                                          if c['historical'] != 'supported' and c['corrected'] == 'supported'],
               'lost_vs_historical': [r['case_id'] + ':' + c['claim_id'] for r in results for c in r['claims']
                                      if c['historical'] == 'supported' and c['corrected'] != 'supported'],
               'unanswerable_packets': [r['case_id'] for r in results if r['answerability'] == 'unanswerable' and r['payload']],
               'review_cases': [r['case_id'] for r in results if r['assessment']['review_queue']],
               'proposal_refusals': dict(Counter(l['corrected_reason'] for r in results for l in r['layers'] if l['corrected_reason']))}
    output_dir.mkdir(parents=True)
    for name, data in [('results.json', results), ('summary.json', summary), ('provenance.json', {
            'input': str(input_dir), 'input_results_sha256': hashlib.sha256(archived_bytes).hexdigest(),
            'protocol': protocol, 'budget': 1500, 'policy': 'owner',
            'code_hashes': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in ('corrected_admission_probe.py', 'admission_layer_probe.py', 'grounded_budget_probe.py', 'grounded_loss_audit.py')}})]:
        (output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
