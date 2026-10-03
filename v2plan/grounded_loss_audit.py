"""Read-only, post-selection attribution of frozen budget-probe losses.

Witness annotations are used only by this audit, never by retrieval/admission.
Literal absence means unobserved annotated witness, not semantic fact absence.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context
from docmancer.docs.domain.evidence_qualification import source_metadata_rejection_reason


def load_probe():
    path = Path(__file__).with_name('grounded_budget_probe.py')
    spec = importlib.util.spec_from_file_location('grounded_budget_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReadOnlyStore:
    def __init__(self, path, generation):
        self.path, self.generation = path, generation

    def active_generation_id(self):
        return self.generation

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def witness_groups(claim, sources):
    """Return complete exact annotated groups, including multipart witnesses."""
    return [index for index, group in enumerate(claim.get('witness_sets', []))
            if group.get('parts') and all(any(
                part['path'] == source['path_or_url'] and part['text'] in source['snippet']
                for source in sources) for part in group['parts'])]


def classify(stages):
    if stages['final']:
        return 'literal_visible'
    for stage, reason in [('source', 'source_witness_unobserved'),
                          ('retrieval', 'discovery_pool_loss'),
                          ('proposals', 'window_construction_loss'),
                          ('admitted', 'read_admission_loss')]:
        if not stages[stage]:
            return reason
    return 'packing_or_final_loss'


def audit(input_dir, output_dir):
    probe = load_probe()
    protocol, cases, manifest = load_protocol()
    raw_results = (input_dir / 'results.json').read_bytes()
    results = json.loads(raw_results)
    by_cell = {(r['case_id'], r['policy'], r['budget'], r['topic_relaxed']): r for r in results}
    records = []
    for case in cases:
        project = case['project_group']
        documents = documents_for(project, manifest)
        source_rows = [{'path_or_url': path, 'snippet': text} for path, text in documents.items()]
        baseline_raw = json.loads((input_dir / project / (case['id'] + '-baseline.json')).read_text())
        baseline = baseline_raw[0] if isinstance(baseline_raw, list) else {'sources': []}
        baseline_assessment = assess_context(case, baseline, registry_for(project, manifest))
        for policy in ('passage', 'owner'):
            reference = by_cell[case['id'], policy, 3000, False]
            retrieval = reference['retrieval']
            store = ReadOnlyStore(input_dir / project / 'passages.db', retrieval['generation_id'])
            with store._connect() as connection:
                source_metadata = {row['source']: json.loads(row['metadata_json']) for row in connection.execute(
                    'SELECT source, metadata_json FROM generation_sources WHERE generation_id=?',
                    (store.generation,))}
                # Verify the archived snapshot is still exactly the frozen source corpus.
                snapshot_rows = connection.execute('SELECT source, content FROM generation_sources WHERE generation_id=?',
                                                   (store.generation,)).fetchall()
                for row in snapshot_rows:
                    path = source_metadata[row['source']]['project_doc_path']
                    if row['content'] != documents[path]:
                        raise ValueError('archived_source_changed')
            metadata = next(iter(source_metadata.values()))
            filters = {'project_identity': metadata['project_identity'], 'project_path': metadata['project_path'],
                       'source_class': 'project_doc'}
            if any(m.get('source_class') != 'project_doc' or m.get('instruction_risk_flags')
                   or source_metadata_rejection_reason(candidate=m,
                       expected_project_identity=filters['project_identity'], lifecycle_intent='current') is not None
                   for m in source_metadata.values()):
                raise ValueError('diagnostic_fts_requires_uniform_eligible_source_pool')
            context = probe.SourceReferenceContext(store, question=case['question'], filters=filters)
            with store._connect() as connection:
                indexed = connection.execute('SELECT source, text FROM retrieval_passages WHERE generation_id=?',
                                             (store.generation,)).fetchall()
                matched = connection.execute('''SELECT p.source, p.text, p.stable_id,
                    bm25(retrieval_passages_fts) AS cost FROM retrieval_passages_fts
                    JOIN retrieval_passages p ON p.id=retrieval_passages_fts.rowid
                    WHERE retrieval_passages_fts MATCH ? AND p.generation_id=?
                    ORDER BY cost, p.stable_id''',
                    (retrieval['trace']['fts_expression'], store.generation)).fetchall()
            # Diagnostic only: inspect archived FTS beyond hydration caps; never feed selection.
            def indexed_rows(rows):
                return [{'path_or_url': source_metadata[h['source']]['project_doc_path'], 'snippet': h['text']}
                        for h in rows]
            bounded_matches = [h for h in matched if len(h['text'].encode()) <= 2048]
            discovery_stages = {'indexed_passages': indexed_rows(indexed),
                                'fts_matches': indexed_rows(matched),
                                'byte_bounded_matches': indexed_rows(bounded_matches),
                                'top12': indexed_rows(bounded_matches[:12])}
            proposals, omissions, _ = probe.inventory(store, question=case['question'], filters=filters,
                                                     policy=policy, retrieval=retrieval, context=context)
            retrieved_rows = [{'path_or_url': source_metadata[h['source']]['project_doc_path'],
                               'snippet': h['text']} for h in retrieval['candidates']]
            proposal_rows = [{'path_or_url': p['item']['project_doc_path'], 'snippet': p['item']['snippet']}
                             for p in proposals]
            for budget in (800, 1500, 3000):
                cell = by_cell[case['id'], policy, budget, False]
                if cell['retrieval'] != retrieval:
                    raise ValueError('inventory_not_paired')
                archived_reasons = {t['proposal_id']: t['reason'] for t in cell['trace']}
                if set(archived_reasons) != {p['proposal_id'] for p in proposals}:
                    raise ValueError('proposal_inventory_changed')
                decisions = {p['proposal_id']: probe.check_proposal(p, question=case['question'],
                              identity=filters['project_identity'], relaxed=False) for p in proposals}
                for pid, reason in decisions.items():
                    if reason is not None and archived_reasons[pid] != reason:
                        raise ValueError('admission_replay_changed')
                    if reason is None and archived_reasons[pid] not in (
                            'selected', 'dto_budget', 'source_row_limit', 'per_source_limit'):
                        raise ValueError('selection_replay_changed')
                admitted_rows = [row for row, p in zip(proposal_rows, proposals) if decisions[p['proposal_id']] is None]
                final_rows = (cell['payload'] or {}).get('sources', [])
                for claim in case['required_claims']:
                    stages = {name: witness_groups(claim, rows) for name, rows in (
                        ('source', source_rows), ('retrieval', retrieved_rows), ('proposals', proposal_rows),
                        ('admitted', admitted_rows), ('final', final_rows))}
                    relevant = []
                    for p, row in zip(proposals, proposal_rows):
                        parts = [part for group in claim.get('witness_sets', []) for part in group['parts']]
                        if any(part['path'] == row['path_or_url'] and part['text'] in row['snippet'] for part in parts):
                            roles = probe.query_constraint_roles(case['question'])
                            native = probe.read_context_admission(p['item'], question=case['question'],
                                expected_project_identity=filters['project_identity'])
                            relevant.append({'proposal_id': p['proposal_id'], 'path': row['path_or_url'],
                                'span': p['item']['char_span'], 'native_rank': p['native_rank'],
                                'admission_reason': decisions[p['proposal_id']],
                                'selection_reason': archived_reasons[p['proposal_id']],
                                'missing_hard_exact': [t for t in roles.hard_exact if not probe._visible_term_present(t, row['snippet'], exact=True)],
                                'missing_bound_subjects': [t for t in roles.bound_subjects if not probe._visible_term_present(t, row['snippet'], exact=True)],
                                'native_read_allowed': native.allowed, 'native_read_reason': native.reason})
                    discovery = {name: witness_groups(claim, rows) for name, rows in discovery_stages.items()}
                    annotated_parts = [part for group in claim.get('witness_sets', []) for part in group['parts']]
                    discovery_hits = [{'stable_id': h['stable_id'], 'byte_bounded_rank': rank,
                        'text_bytes': len(h['text'].encode()),
                        'skipped_resource': h['stable_id'] in retrieval['trace']['skipped_resource_ids'],
                        'source': source_metadata[h['source']]['project_doc_path']}
                        for rank, h in enumerate(bounded_matches, 1)
                        if any(part['path'] == source_metadata[h['source']]['project_doc_path']
                               and part['text'] in h['text'] for part in annotated_parts)]
                    discovery_loss = None
                    if classify(stages) == 'discovery_pool_loss':
                        for name, reason in [('indexed_passages', 'index_passage_boundary_or_deferred'),
                                             ('fts_matches', 'fts_match'), ('byte_bounded_matches', 'passage_byte_cap'),
                                             ('top12', 'rank_limit')]:
                            if not discovery[name]:
                                discovery_loss = reason
                                break
                        if discovery_loss is None:
                            discovery_loss = 'hydration_pool_or_per_source_cap'
                    records.append({'case_id': case['id'], 'claim_id': claim['id'], 'policy': policy, 'budget': budget,
                        'answerability': case['answerability'], 'stage_complete_literal_groups': stages,
                        'attribution': classify(stages), 'baseline_status': baseline_assessment['claims'][claim['id']]['status'],
                        'final_status': cell['assessment']['claims'][claim['id']]['status'],
                        'witness_proposals': relevant, 'omissions': omissions,
                        'discovery_literal_groups': discovery, 'discovery_loss': discovery_loss,
                        'discovery_witness_hits': discovery_hits,
                        'retrieval_trace': retrieval['trace'], 'diagnostic_only': True})
    summaries = []
    for policy in ('passage', 'owner'):
        for budget in (800, 1500, 3000):
            rows = [r for r in records if r['policy'] == policy and r['budget'] == budget]
            losses = [r for r in rows if r['baseline_status'] == 'supported' and r['final_status'] != 'supported']
            summaries.append({'policy': policy, 'budget': budget, 'claims': len(rows),
                'all_attribution': dict(Counter(r['attribution'] for r in rows)),
                'baseline_supported_losses': len(losses),
                'loss_attribution': dict(Counter(r['attribution'] for r in losses)),
                'loss_ids': [r['case_id'] + ':' + r['claim_id'] for r in losses],
                'admission_loss_reasons': dict(Counter(p['admission_reason'] for r in losses
                    if r['attribution'] == 'read_admission_loss' for p in r['witness_proposals']
                    if p['admission_reason'] is not None))})
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, data in [('claims.json', records), ('summary.json', summaries),
                       ('provenance.json', {'input': str(input_dir), 'results_sha256': hashlib.sha256(raw_results).hexdigest(),
                         'protocol': protocol, 'probe_sha256': hashlib.sha256(Path(probe.__file__).read_bytes()).hexdigest(),
                         'audit_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         'note': 'Read-only archived retrieval; literal-witness attribution, not semantic completeness proof.'})]:
        (output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.input, args.output)
