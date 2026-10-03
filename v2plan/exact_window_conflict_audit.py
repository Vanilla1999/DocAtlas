"""Read-only policy comparison; proposal membership is not delivery or permission."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from unified_read_replay import native_inventory
from grounded_loss_audit import ReadOnlyStore, load_probe, witness_groups
from eval.evidence_quality_v2.run import load_protocol, documents_for
from docmancer.docs.application.need_context_projection import (
    _current_plan, _current_bundles, iter_need_context_variants, preferred_context_variants)
from docmancer.docs.application.need_context_disposition import classify_need_context, _probe
from docmancer.docs.application.read_context_admission import iter_read_context_variants
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.evidence_set_types import SourceKey
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from unified_read_admission import unified_read_admission


def run(input_dir, output_dir):
    if output_dir.exists():
        raise FileExistsError(output_dir)
    probe = load_probe()
    protocol, cases, manifest = load_protocol()
    cells = {r['case_id']: r for r in json.loads((input_dir / 'results.json').read_text())
             if r['policy'] == 'owner' and r['budget'] == 1500 and not r['topic_relaxed']}
    rows, captures = [], {}
    for case in cases:
        raw_capture = (input_dir / case['project_group'] / (case['id'] + '-baseline.json')).read_bytes()
        captures[case['id']] = hashlib.sha256(raw_capture).hexdigest()
        store = ReadOnlyStore(input_dir / case['project_group'] / 'passages.db',
                              cells[case['id']]['retrieval']['generation_id'])
        documents = documents_for(case['project_group'], manifest)
        with store._connect() as connection:
            snapshots = connection.execute('SELECT source, content, metadata_json FROM generation_sources WHERE generation_id=?',
                                           (store.generation,)).fetchall()
        metadata = {s['source']: json.loads(s['metadata_json']) for s in snapshots}
        assert all(s['content'] == documents[metadata[s['source']]['project_doc_path']] for s in snapshots)
        filters = {k: next(iter(metadata.values()))[k] for k in ('project_identity', 'project_path', 'source_class')}
        question, identity = case['question'], filters['project_identity']
        context = probe.SourceReferenceContext(store, question=question, filters=filters)
        proposals = native_inventory(json.loads(raw_capture)[1], store=store, context=context,
                                     metadata=metadata, documents=documents, probe=probe)
        for proposal in proposals:
            original = proposal['item']
            diagnostics = {}
            kwargs = dict(query_plan=probe.build_documentation_query_plan(question).as_payload(),
                          expected_project_identity=identity, max_tokens=1500, diagnostics=diagnostics)
            typed = list(iter_need_context_variants([original], **kwargs))
            preferred = list(preferred_context_variants([original], **dict(kwargs, diagnostics={})))
            reads = list(iter_read_context_variants([original], **dict(kwargs, diagnostics={})))
            spans = {tuple(original['char_span'])}
            spans.update(tuple(r['span']) for r in diagnostics.get('need_context_fallback', []))
            raw = original['_reference_evidence']['raw_document']
            plan = _current_plan(original['_reference_root_plan'], question)
            source = original['_reference_evidence']['source']
            key = SourceKey(plan.scope, source['document_id'], source['canonical_path'], source['content_sha256'])
            bundles = _current_bundles(original.get('_evidence_sets'), key)
            if bundles is None:
                raise ValueError('unavailable_current_bundles')
            records = {key: {'source': source, 'raw_document': raw}}
            contracts = compile_need_contracts(question, plan)[:12]
            for start, end in sorted(spans):
                body = raw[start:end]
                item = dict(original, snippet=body, char_span=[start, end], char_start=start, char_end=end)
                native = probe.read_context_admission(item, question=question, expected_project_identity=identity)
                unified = unified_read_admission(item, question=question, expected_project_identity=identity)
                need_rows = []
                for contract in contracts:
                    disposition = classify_need_context(contract, reference_plan=plan, candidate=item,
                                                         bundles=bundles, prepared_sources=records)
                    qualification = qualify_evidence(_probe(contract), query_id=contract.need.need_id,
                        visible_text=body, evidence_text=body, candidate=item, expected_project_identity=identity,
                        catalog_role=str(item.get('catalog_role') or ''))
                    need_rows.append({'need_id': contract.need.need_id, 'query_span': contract.need.query_span_text,
                                      'disposition': asdict(disposition), 'qualified': qualification.qualified,
                                      'qualification_reason': qualification.reason})
                # Projectors return display text without reliable absolute span fields.
                # Ambiguous repeated bytes are UNKNOWN, never attributed to a span.
                def membership(variants):
                    if not any(v[1]['snippet'] == body for v in variants):
                        return False
                    if raw.count(body, original['char_span'][0], original['char_span'][1]) != 1:
                        return None
                    return True
                claims = [c['id'] for c in case['required_claims']
                          if witness_groups(c, [{'path_or_url': item['path'], 'snippet': body}])]
                rows.append({'case_id': case['id'], 'proposal_id': proposal['proposal_id'],
                    'path': item['path'], 'span': [start, end], 'snippet': body,
                    'source_eligible': probe.source_window_eligibility(item, question=question,
                        expected_project_identity=identity).eligible,
                    'native_read': asdict(native), 'unified_read': asdict(unified), 'needs': need_rows,
                    'typed_proposal': membership(typed), 'preferred_proposal': membership(preferred),
                    'read_proposal': membership(reads), 'literal_complete_claims': claims})
    summary = {'cases': len(cases), 'windows_per_proposal': len(rows),
        'unique_request_windows': len({(r['case_id'], r['path'], tuple(r['span'])) for r in rows}),
        'read_vs_typed': dict(Counter(str((r['native_read']['allowed'],
            any(n['disposition']['state'] != 'blocked' for n in r['needs']))) for r in rows)),
        'read_vs_unified': dict(Counter(str((r['native_read']['allowed'], r['unified_read']['allowed'])) for r in rows)),
        'typed_proposals_not_prefit': sum(r['typed_proposal'] is True and r['preferred_proposal'] is False
                                        and r['read_proposal'] is False for r in rows),
        'ambiguous_membership_rows': sum(any(r[k] is None for k in ('typed_proposal', 'preferred_proposal', 'read_proposal')) for r in rows),
        'witness_typed_only': sum(bool(r['literal_complete_claims']) and not r['native_read']['allowed']
            and any(n['disposition']['state'] != 'blocked' for n in r['needs']) for r in rows),
        'scope': 'per-candidate proposals, not full orchestrator selection or delivered packets'}
    output_dir.mkdir(parents=True)
    for name, data in [('rows.json', rows), ('summary.json', summary), ('provenance.json',
        {'protocol': protocol, 'capture_hashes': captures, 'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'budget': 1500, 'production_changed': False, 'retrieval_changed': False})]:
        (output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
