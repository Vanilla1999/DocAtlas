"""Independent diagnostic layers, not an alternative admission rule."""
import argparse
from collections import Counter
import json
from pathlib import Path

from grounded_loss_audit import ReadOnlyStore, load_probe, witness_groups
from eval.evidence_quality_v2.run import load_protocol
from docmancer.docs.domain.source_window_eligibility import prepare_source_probe
from docmancer.docs.domain.query_terms import documentation_query_terms
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.application.need_context_projection import _current_plan
from docmancer.docs.application.need_context_disposition import _applicable_context
from docmancer.docs.application.read_context_admission import local_topic_witness


def inspect_layers(item, *, question, identity, probe):
    """Measure every layer independently; never infer PASS from earlier veto."""
    body = item['snippet']
    roles = probe.query_constraint_roles(question)
    prepared, reference_reason = prepare_source_probe(
        {'query_text': question, 'exact_terms': list(roles.hard_exact),
         'bound_subjects': list(roles.bound_subjects)},
        visible_text=body, evidence_text=body, candidate=item,
        expected_project_identity=identity)
    owner = str(prepared.get('bound_subject_context') or '')
    # Source-only locators may already have been removed by verified reference binding.
    exact_terms = prepared.get('exact_terms', roles.hard_exact)
    subjects = prepared.get('bound_subjects', roles.bound_subjects)
    literal_missing = [t for t in exact_terms if not probe._visible_term_present(t.casefold(), body.casefold(), exact=True)]
    subject_rows = []
    for term in subjects:
        location = 'body' if probe._visible_term_present(term.casefold(), body.casefold(), exact=True) else (
            'verified_owner' if reference_reason is None and probe._visible_term_present(term.casefold(), owner.casefold(), exact=True)
            else 'unresolved')
        subject_rows.append({'term': term, 'location': location})
    plan = _current_plan(item.get('_reference_root_plan') or {}, question)
    conditions = []
    if plan is not None:
        for contract in compile_need_contracts(question, plan):
            if contract.constraint_spans:
                conditions.append({'need_id': contract.need.need_id,
                    'query_span': contract.need.query_span_text,
                    'constraints': [question[s.start:s.end] for s in contract.constraint_spans],
                    'state': 'recognized_applicable' if _applicable_context(contract, question, body)
                             else 'unresolved_or_inapplicable'})
    terms = {t.casefold() for t in prepared.get('query_terms', documentation_query_terms(question))
             if probe._visible_term_present(t.casefold(), body.casefold(), exact=False)}
    native = probe.read_context_admission(item, question=question, expected_project_identity=identity)
    return {'source_eligible': probe.source_window_eligibility(item, question=question,
                expected_project_identity=identity).eligible,
            'reference_reason': reference_reason,
            'subjects': subject_rows, 'literal_terms': list(exact_terms), 'literal_missing': literal_missing,
            'conditions': conditions, 'condition_plan_available': plan is not None,
            'topic_locality': local_topic_witness(body, question=question, terms=terms),
            'native_read_allowed': native.allowed, 'native_read_reason': native.reason,
            'research_read_reason': probe.read_reason(item, question=question, identity=identity),
            'diagnostic_only': True}


def run(input_dir, output_dir):
    probe = load_probe()
    _, cases, _ = load_protocol()
    archived = json.loads((input_dir / 'results.json').read_text())
    cells = {r['case_id']: r for r in archived
             if r['policy'] == 'owner' and r['budget'] == 1500 and not r['topic_relaxed']}
    rows = []
    for case in cases:
        cell = cells[case['id']]
        retrieval = cell['retrieval']
        store = ReadOnlyStore(input_dir / case['project_group'] / 'passages.db', retrieval['generation_id'])
        with store._connect() as connection:
            metadata = json.loads(connection.execute(
                'SELECT metadata_json FROM generation_sources WHERE generation_id=? LIMIT 1',
                (store.generation,)).fetchone()[0])
        filters = {k: metadata[k] for k in ('project_identity', 'project_path', 'source_class')}
        context = probe.SourceReferenceContext(store, question=case['question'], filters=filters)
        proposals, _, _ = probe.inventory(store, question=case['question'], filters=filters,
                                          policy='owner', retrieval=retrieval, context=context)
        for proposal in proposals:
            item = proposal['item']
            layers = inspect_layers(item, question=case['question'], identity=filters['project_identity'], probe=probe)
            source = {'path_or_url': item['project_doc_path'], 'snippet': item['snippet']}
            # Annotation is only an observation label, never used by inspect_layers.
            claims = [c['id'] for c in case['required_claims'] if witness_groups(c, [source])]
            rows.append(dict(layers, case_id=case['id'], question=case['question'],
                proposal_id=proposal['proposal_id'], path=source['path_or_url'], span=item['char_span'],
                native_rank=proposal['native_rank'], literal_complete_claims=claims,
                structural_reason=proposal['structural_reason']))
    summary = {}
    for label, selected in [('all_proposals', rows), ('complete_witness_proposals', [r for r in rows if r['literal_complete_claims']])]:
        summary[label] = {'count': len(selected),
            'subject_unresolved': sum(any(s['location'] == 'unresolved' for s in r['subjects']) for r in selected),
            'subject_from_owner': sum(any(s['location'] == 'verified_owner' for s in r['subjects']) for r in selected),
            'literal_missing': sum(bool(r['literal_missing']) for r in selected),
            'condition_unresolved': sum(any(c['state'] != 'recognized_applicable' for c in r['conditions']) for r in selected),
            'topic_false': sum(not r['topic_locality'] for r in selected),
            'native_allowed': sum(r['native_read_allowed'] for r in selected),
            'research_refusals': dict(Counter(r['research_read_reason'] for r in selected if r['research_read_reason']))}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / 'layers.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (output_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
