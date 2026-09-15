"""Audit the fixed factorial and save paired outcomes plus exact delivered text."""
import argparse
from collections import Counter
import hashlib
import json
import lzma
from pathlib import Path

from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from eval.evidence_quality_v2.run import load_protocol


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    rows = json.loads((args.evaluation / 'rows.json').read_text())
    old_path = root.parent / 'research-suite/results/raw-results.json.xz'
    old = json.loads(lzma.decompress(old_path.read_bytes()))['files']
    historical = {r['id']: r for r in old['docatlas-research-final-eval/rows.json'] if r['variant'] == 'hybrid_plain'}
    _, cases, _ = load_protocol()
    case_map = {c['id']: c for c in cases}
    names = ('hybrid_plain', 'hybrid_context_bm25_plain', 'hybrid_late', 'hybrid_context_bm25_late')
    by_lane = {name: {r['id']: r for r in rows if r['variant'] == name} for name in names}
    assert len(rows) == 320 and all(set(lane) == set(case_map) for lane in by_lane.values())
    assert all(not r['replay_errors'] and not r['packet_errors'] for r in rows)
    assert all(docs_context_budget_tokens(r['replay']) <= 800 for r in rows)
    assert all(docs_context_budget_tokens(r['source_only_packet']) <= 800 for r in rows)
    assert all(r['replay'].get('answer_supported') is False for r in rows)
    spans = lambda r: [(s['path_or_url'], s['snippet']) for s in r['replay'].get('sources', [])]
    for cid, r in by_lane['hybrid_plain'].items():
        prior = historical[cid]
        assert r['selected_keys'] == prior['selected_keys'], cid
        assert spans(r) == spans(prior), cid
        assert r['replay_assessment'] == prior['replay_assessment'], cid
    sufficient = lambda r: r['replay_assessment']['context_sufficiency'] == 'sufficient'
    positive = lambda r: r['answerability'] == 'within_budget'
    success = {name: {cid for cid, r in lane.items() if positive(r) and sufficient(r)} for name, lane in by_lane.items()}
    summary = {}
    for name, lane in by_lane.items():
        pos = [r for r in lane.values() if positive(r)]
        summary[name] = {
            'top5': sum(r['coverage']['5']['complete'] for r in pos),
            'top20': sum(r['coverage']['20']['complete'] for r in pos),
            'sufficient': len(success[name]),
            'assessment_counts': dict(Counter(r['replay_assessment']['context_sufficiency'] for r in pos)),
            'found_top20_not_confirmed_final': [r['id'] for r in pos if r['coverage']['20']['complete'] and not sufficient(r)],
            'controls': {kind: dict(Counter(r['replay_assessment']['context_sufficiency'] for r in lane.values() if r['answerability'] == kind)) for kind in sorted({r['answerability'] for r in lane.values()} - {'within_budget'})},
        }
    pairs = {}
    for before, after in [(names[0], names[1]), (names[0], names[2]), (names[1], names[3]), (names[2], names[3]), (names[0], names[3])]:
        pairs[before + ' -> ' + after] = {
            'wins': sorted(success[after] - success[before]),
            'losses': sorted(success[before] - success[after]),
            'changed_output_cases': [cid for cid in case_map if spans(by_lane[before][cid]) != spans(by_lane[after][cid])],
            'top5_wins': [cid for cid in case_map if positive(by_lane[before][cid]) and not by_lane[before][cid]['coverage']['5']['complete'] and by_lane[after][cid]['coverage']['5']['complete']],
            'top5_losses': [cid for cid in case_map if positive(by_lane[before][cid]) and by_lane[before][cid]['coverage']['5']['complete'] and not by_lane[after][cid]['coverage']['5']['complete']],
        }
    native_path = root.parent / 'semantic-selection/results/raw-results.json.xz'
    native = json.loads(lzma.decompress(native_path.read_bytes()))['baseline']
    native_success = {r['id'] for r in native if r['assessment']['context_sufficiency'] == 'sufficient'}
    combined = names[-1]
    controls_sufficient = [cid for cid, r in by_lane[combined].items() if not positive(r) and sufficient(r)]
    promote = (len(success[combined]) > max(34, *(len(success[n]) for n in names[:-1]))
               and native_success <= success[combined] and not controls_sufficient)
    validation = {
        'rows': len(rows), 'unchanged_hybrid_plain_cases': 80, 'audit_errors': 0,
        'max_replay_tokens': max(docs_context_budget_tokens(r['replay']) for r in rows),
        'max_packet_tokens': max(docs_context_budget_tokens(r['source_only_packet']) for r in rows),
        'native_sufficient_cases_lost': sorted(native_success - success[combined]),
        'combined_passes_screening': promote, 'holdout_opened': False,
        'answer_model_run': False, 'inference_reused': True,
        'input_archive_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
        'native_archive_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
    }
    questions = [{'id': cid, 'question': case['question'], 'answerability': case['answerability'],
                  'lanes': {name: {'top5_complete': lane[cid]['coverage']['5']['complete'],
                                   'top20_complete': lane[cid]['coverage']['20']['complete'],
                                   'assessment': lane[cid]['replay_assessment'],
                                   'payload': lane[cid]['replay']} for name, lane in by_lane.items()}}
                 for cid, case in case_map.items()]
    args.output.mkdir(parents=True, exist_ok=True)
    raw = lzma.compress(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode())
    validation['raw_results_sha256'] = hashlib.sha256(raw).hexdigest()
    (args.output / 'raw-results.json.xz').write_bytes(raw)
    for name, value in [('summary', summary), ('paired', pairs), ('validation', validation), ('questions', questions)]:
        (args.output / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'summary': summary, 'paired': pairs, 'validation': validation}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
