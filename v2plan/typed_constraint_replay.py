"""Single owner/1500 research replay with scoped compiler substitution."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import admission_layer_probe
import corrected_admission_probe
from docmancer.docs.application import read_context_admission
from docmancer.docs.application.need_context_disposition import _applicable_context
from docmancer.docs.domain.query_reference_binding import resolve_references, ScopeKey
from temporal_condition_probe import MATRIX
from typed_constraint_compiler import compile_typed_constraints, native_compile


def matrix_controls():
    rows = []
    for name, label, question, body in MATRIX:
        references = resolve_references(question, catalog=(), scope=ScopeKey('diagnostic', '', 'generation'),
                                        catalog_complete=True, document_suffixes=frozenset())
        original = native_compile(question, references)
        research = compile_typed_constraints(question, references)
        rows.append({'id': name, 'label': label, 'question': question, 'body': body,
            'native': [{'contract': asdict(c), 'applicable': _applicable_context(c, question, body)} for c in original],
            'research': [{'contract': asdict(c), 'applicable': _applicable_context(c, question, body)} for c in research]})
    return rows


def run(args):
    previous_compiler = read_context_admission.compile_need_contracts
    with patch.object(read_context_admission, 'compile_need_contracts', compile_typed_constraints), \
         patch.object(admission_layer_probe, 'compile_need_contracts', compile_typed_constraints):
        corrected_admission_probe.run(args.input, args.output)
    if read_context_admission.compile_need_contracts is not previous_compiler:
        raise RuntimeError('compiler_substitution_not_restored')
    results = json.loads((args.output / 'results.json').read_text())
    prior = {r['case_id']: r for r in json.loads(args.previous.read_text())}
    transitions = []
    for row in results:
        old = prior[row['case_id']]
        if {l['proposal_id'] for l in old['layers']} != {l['proposal_id'] for l in row['layers']}:
            raise ValueError('paired_inventory_mismatch')
        old_reasons = {l['proposal_id']: l['corrected_reason'] for l in old['layers']}
        for layer in row['layers']:
            old_reason = old_reasons[layer['proposal_id']]
            if old_reason != layer['corrected_reason']:
                transitions.append({'case_id': row['case_id'], 'proposal_id': layer['proposal_id'],
                                    'before': old_reason, 'after': layer['corrected_reason']})
    comparison = {'cases': len(results), 'budget': 1500, 'policy': 'owner',
        'previous_packets': sum(bool(r['payload']) for r in prior.values()),
        'research_packets': sum(bool(r['payload']) for r in results),
        'recovered_vs_corrected': [], 'lost_vs_corrected': [], 'admission_transitions': transitions,
        'scope': 'Only two research-process compiler references replaced; production files unchanged.'}
    for row in results:
        old_claims = {c['claim_id']: c for c in prior[row['case_id']]['claims']}
        for claim in row['claims']:
            previous = old_claims[claim['claim_id']]['corrected']
            current = claim['corrected']
            key = row['case_id'] + ':' + claim['claim_id']
            if previous != 'supported' and current == 'supported':
                comparison['recovered_vs_corrected'].append(key)
            if previous == 'supported' and current != 'supported':
                comparison['lost_vs_corrected'].append(key)
    for name, data in [('matrix_controls.json', matrix_controls()), ('paired_comparison.json', comparison),
                       ('compiler_provenance.json', {'code_hashes': {
                           name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in ('typed_constraint_compiler.py', 'typed_constraint_replay.py', 'temporal_condition_probe.py')},
                        'previous_results_sha256': hashlib.sha256(args.previous.read_bytes()).hexdigest(),
                        'substitution': ['read_context_admission.compile_need_contracts', 'admission_layer_probe.compile_need_contracts'],
                        'restored': True, 'diagnostic_only': True})]:
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--previous', type=Path, default=Path('v2plan/artifacts/corrected-owner-1500/results.json'))
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
