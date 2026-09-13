"""Replay frozen retrieval; alter source-bound qualification only, not search."""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import sys
from unittest.mock import patch
from section_scope import ScopeBinder, STAMP_KEYS, PREFIX, installed, label
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for, audit_payload
from eval.evidence_quality_v2.semantic import assess_context

HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def spans(payload):
    return [(s['path_or_url'], s['snippet']) for s in payload.get('sources', [])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    _, cases, manifest = load_protocol()
    cases = {c['id']: c for c in cases}
    # Load only the existing 80-case corpus, checked against its frozen manifest.
    documents = {g: documents_for(g, manifest) for g in {c['project_group'] for c in cases.values()}}
    captured = []
    original_project = projection.project_docs_context

    def capture(*, retrieval, **kwargs):
        if not retrieval.get('context_pack'):
            return original_project(retrieval=retrieval, **kwargs)
        saved = deepcopy(retrieval)
        with patch.object(projection, 'project_docs_context', original_project):
            payload, snapshot = original_project(retrieval=retrieval, **kwargs)
        captured.append({'input': saved, 'payload': deepcopy(payload)})
        return payload, snapshot

    spec = importlib.util.spec_from_file_location('scope_control_eval', HERE.parent / 'research-suite/evaluate.py')
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    argv = ['evaluate.py', '--input', '/tmp/docatlas-research-input', '--output', str(args.output / 'controls'),
            '--embeddings', '/tmp/docatlas-embedding-output-v2/rankings.json',
            '--contexts', '/tmp/docatlas-contextual-final/contexts.json', '--hybrid-factorial-only']
    with patch.object(sys, 'argv', argv), patch.object(projection, 'project_docs_context', capture):
        evaluator.main()
    rows = json.loads((args.output / 'controls/rows.json').read_text())
    history = json.loads(lzma.decompress((HERE.parent / 'contextual-late/results/raw-results.json.xz').read_bytes()))
    historical = {(r['id'], r['variant']): r for r in history}
    assert len(captured) == len(rows) == 320
    inputs = {}
    for row, observed in zip(rows, captured):
        prior = historical[row['id'], row['variant']]
        assert row['replay'] == observed['payload']
        assert spans(row['replay']) == spans(prior['replay']) and row['replay_assessment'] == prior['replay_assessment']
        assert row['selected_keys'] == prior['selected_keys'] and not row['replay_errors']
        if row['variant'] == 'hybrid_plain':
            inputs[row['id']] = observed['input']
    assert len(inputs) == 80
    outcomes, all_events = [], []
    for cid, frozen in inputs.items():
        case = cases[cid]
        identity = {c['project_identity'] for c in frozen['context_pack']}
        assert len(identity) == 1
        stamps = {}
        for c in frozen['context_pack']:
            stamp = tuple(c.get(k) for k in STAMP_KEYS)
            assert stamps.setdefault(c['path'], stamp) == stamp
        binder = ScopeBinder(documents[case['project_group']], next(iter(identity)), stamps)
        for mode in ('current', 'initial_only', 'scope_requalify'):
            retrieval, events = deepcopy(frozen), []
            with installed(binder, mode, events) if mode != 'current' else nullcontext():
                payload, snapshot = original_project(retrieval=retrieval)
            root = Path('/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus') / case['project_group']
            errors = audit_payload(payload, snapshot, root)
            heading_records = []
            for source in payload.get('sources', []):
                assert any(source['path_or_url'] == c['path'] and source['snippet'] in c['content'] for c in frozen['context_pack'])
                if str(source['section']).startswith(PREFIX):
                    proof = binder.bind({**source, '_qualification_candidate': snapshot[source['evidence_id']]['source']})
                    if not proof or source['section'] != label(proof):
                        errors.append('source section is not bound to the visible window')
                    heading_records.append({'evidence_id': source['evidence_id'], 'proof': proof})
            record = {'id': cid, 'question': case['question'], 'project_group': case['project_group'],
                      'answerability': case['answerability'], 'mode': mode, 'input_sha256': digest(frozen),
                      'payload': payload, 'snapshot': snapshot, 'tokens': docs_context_budget_tokens(payload),
                      'assessment': assess_context(case, payload, registry_for(case['project_group'], manifest)),
                      'audit_errors': errors, 'heading_records': heading_records,
                      'rescues': dict(Counter(e['stage'] for e in events if e['scope_proof'])),
                      'diagnostics': retrieval.get('retrieval_diagnostics', {}).get('docs_context_projection', {})}
            if mode == 'current':
                assert spans(payload) == spans(historical[cid, 'hybrid_plain']['replay'])
                assert record['assessment'] == historical[cid, 'hybrid_plain']['replay_assessment']
            outcomes.append(record)
            all_events.append({'id': cid, 'mode': mode, 'events': events})
        print('scope-replayed', cid, flush=True)
    success = lambda r: r['answerability'] == 'within_budget' and r['assessment']['context_sufficiency'] == 'sufficient'
    baseline = {r['id']: r for r in outcomes if r['mode'] == 'current'}
    old_ok = {cid for cid, r in baseline.items() if success(r)}
    assert len(old_ok) == 34
    summary = {}
    for mode in ('current', 'initial_only', 'scope_requalify'):
        lane = [r for r in outcomes if r['mode'] == mode]
        ok = {r['id'] for r in lane if success(r)}
        wins, losses = sorted(ok - old_ok), sorted(old_ok - ok)
        controls = [r['id'] for r in lane if r['answerability'] != 'within_budget' and r['assessment']['context_sufficiency'] == 'sufficient']
        groups = sorted({cases[c]['project_group'] for c in wins})
        summary[mode] = {'sufficient': len(ok), 'wins': wins, 'losses': losses,
            'winning_project_groups': groups, 'sufficient_controls': controls,
            'changed_output': [r['id'] for r in lane if r['payload'] != baseline[r['id']]['payload']],
            'changed_spans': [r['id'] for r in lane if spans(r['payload']) != spans(baseline[r['id']]['payload'])],
            'max_tokens': max(r['tokens'] for r in lane), 'mean_tokens': sum(r['tokens'] for r in lane) / 80,
            'heading_sources': sum(len(r['heading_records']) for r in lane),
            'audit_errors': sum(len(r['audit_errors']) for r in lane),
            'screening_passed': len(ok) >= 36 and len(groups) >= 2 and not losses and not controls and not any(r['audit_errors'] for r in lane)}
    validation = {'historical_controls_reproduced': 320, 'rows': len(outcomes), 'questions': 80,
                  'audit_errors': sum(len(r['audit_errors']) for r in outcomes),
                  'production_changed': False, 'holdout_opened': False, 'semantic_admission_changed': False,
                  'documents_sha256': {g: {p: hashlib.sha256(t.encode()).hexdigest() for p, t in ds.items()} for g, ds in documents.items()},
                  'policy_sha256': hashlib.sha256((HERE / 'section_scope.py').read_bytes()).hexdigest()}
    save(args.output / 'summary.json', summary)
    save(args.output / 'validation.json', validation)
    save(args.output / 'questions.json', outcomes)
    for name, data in [('inputs', inputs), ('events', all_events)]:
        (args.output / (name + '.json.xz')).write_bytes(lzma.compress(json.dumps(data, ensure_ascii=False, default=str).encode()))
    print('SECTION_SCOPE_SUMMARY', json.dumps(summary, ensure_ascii=False), flush=True)
    assert validation['audit_errors'] == 0
    assert all(r['tokens'] <= 800 and len(r['payload'].get('sources', [])) <= 3 for r in outcomes)


if __name__ == '__main__':
    main()
