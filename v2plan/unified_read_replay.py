"""Read-only paired admission trial on captured native candidates, not passages."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from grounded_loss_audit import ReadOnlyStore, load_probe
from unified_read_admission import unified_read_admission
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context


def native_inventory(capture, *, store, context, metadata, documents, probe):
    events = capture['stages']['retrieved_candidates']
    if len(events) != 1 or events[0]['complete'] is not True:
        raise ValueError('native_inventory_not_complete')
    by_path = {m['project_doc_path']: (source, m) for source, m in metadata.items()}
    proposals, seen = [], set()
    for rank, row in enumerate(events[0]['sources']):
        path = row['path_or_url']
        start, end = row['char_start'], row['char_end']
        if documents[path][start:end] != row['snippet']:
            raise ValueError('native_source_span_changed')
        source, source_metadata = by_path[path]
        if row['project_identity'] != source_metadata['project_identity']:
            raise ValueError('native_project_identity_changed')
        key = (path, start, end)
        if key in seen:
            continue
        seen.add(key)
        chunk = probe.Chunk(source=source, text=row['snippet'], chunk_index=rank,
            metadata=dict(source_metadata, char_span=[start, end], generation_id=store.generation))
        ready = context.prepare([chunk])[0]
        item = dict(ready.metadata, source=source, path=path, snippet=ready.text)
        proposals.append({'proposal_id': row['evidence_id'], 'native_rank': rank,
                          'source_identity': source, 'item': item})
    return proposals


def run(input_dir, output_dir):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    probe = load_probe()
    protocol, cases, manifest = load_protocol()
    archived = json.loads((input_dir / 'results.json').read_text())
    cells = {r['case_id']: r for r in archived
             if r['policy'] == 'owner' and r['budget'] == 1500 and not r['topic_relaxed']}
    results, input_hashes = [], {}
    for case in cases:
        capture_path = input_dir / case['project_group'] / (case['id'] + '-baseline.json')
        raw_capture = capture_path.read_bytes()
        input_hashes[case['id']] = hashlib.sha256(raw_capture).hexdigest()
        historical, capture = json.loads(raw_capture)
        store = ReadOnlyStore(input_dir / case['project_group'] / 'passages.db',
                              cells[case['id']]['retrieval']['generation_id'])
        documents = documents_for(case['project_group'], manifest)
        with store._connect() as connection:
            snapshots = connection.execute(
                'SELECT source, content, metadata_json FROM generation_sources WHERE generation_id=?',
                (store.generation,)).fetchall()
        metadata = {s['source']: json.loads(s['metadata_json']) for s in snapshots}
        if any(s['content'] != documents[metadata[s['source']]['project_doc_path']] for s in snapshots):
            raise ValueError('archived_snapshot_changed')
        filters = {k: next(iter(metadata.values()))[k]
                   for k in ('project_identity', 'project_path', 'source_class')}
        context = probe.SourceReferenceContext(store, question=case['question'], filters=filters)
        proposals = native_inventory(capture, store=store, context=context, metadata=metadata,
                                     documents=documents, probe=probe)
        plan = probe.build_documentation_query_plan(case['question']).as_payload()
        row = {'case_id': case['id'], 'answerability': case['answerability'],
               'inventory': [{'proposal_id': p['proposal_id'], 'native_rank': p['native_rank'],
                              'path': p['item']['path'], 'span': p['item']['char_span']}
                             for p in proposals], 'arms': {}}
        registry = registry_for(case['project_group'], manifest)
        for name, admission in [('native_read', probe.read_context_admission),
                                ('unified_read', unified_read_admission)]:
            def check(proposal):
                decision = admission(proposal['item'], question=case['question'],
                                     expected_project_identity=filters['project_identity'])
                return None if decision.allowed else decision.reason
            result = probe.ordered_packet(proposals, budget=1500, check=check,
                build=lambda selected: probe.render_packet([p['item'] for p in selected], query_plan=plan))
            result.pop('snapshot', None)
            result['assessment'] = assess_context(case, result['payload'] or {'sources': []}, registry)
            result['decisions'] = [{'proposal_id': p['proposal_id'], 'reason': check(p)} for p in proposals]
            row['arms'][name] = result
        row['historical_native_assessment'] = assess_context(case, historical, registry)
        results.append(row)
    summary = {'cases': len(results), 'budget': 1500, 'inventory': 'captured_native_retrieved_candidates',
               'arms': {}, 'recovered': [], 'lost': [], 'transitions': [],
               'production_changed': False, 'eligible_for_rollout': False}
    for arm in ('native_read', 'unified_read'):
        summary['arms'][arm] = {
            'packets': sum(bool(r['arms'][arm]['payload']) for r in results),
            'supported': sum(r['arms'][arm]['assessment']['required_supported'] for r in results),
            'review_cases': [r['case_id'] for r in results if r['arms'][arm]['assessment']['review_queue']],
            'unanswerable_packets': [r['case_id'] for r in results
                                    if r['answerability'] == 'unanswerable' and r['arms'][arm]['payload']],
            'refusals': dict(Counter(d['reason'] for r in results for d in r['arms'][arm]['decisions'] if d['reason']))}
    for row in results:
        before, after = row['arms']['native_read'], row['arms']['unified_read']
        for claim_id, claim in before['assessment']['claims'].items():
            current = after['assessment']['claims'][claim_id]['status']
            if claim['status'] != 'supported' and current == 'supported':
                summary['recovered'].append(row['case_id'] + ':' + claim_id)
            if claim['status'] == 'supported' and current != 'supported':
                summary['lost'].append(row['case_id'] + ':' + claim_id)
        for old, new in zip(before['decisions'], after['decisions'], strict=True):
            if old['proposal_id'] != new['proposal_id']:
                raise ValueError('paired_decision_identity_changed')
            if old['reason'] != new['reason']:
                summary['transitions'].append({'case_id': row['case_id'], 'proposal_id': old['proposal_id'],
                                              'before': old['reason'], 'after': new['reason']})
    output_dir.mkdir(parents=True)
    provenance = {'protocol': protocol, 'native_capture_hashes': input_hashes,
        'code_hashes': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                        for name in ('unified_read_admission.py', 'unified_read_replay.py', 'grounded_budget_probe.py')},
        'input': str(input_dir), 'retrieval_replayed': False, 'compiler_changed': False,
        'source_reads': 'archived read-only snapshots', 'scope': 'isolated read arms, not full native pipeline'}
    for filename, data in [('results.json', results), ('summary.json', summary), ('provenance.json', provenance)]:
        (output_dir / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
