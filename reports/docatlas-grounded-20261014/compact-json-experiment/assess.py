"""Offline audit of delivered DTOs and complete native window bindings."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('repo', 'run', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    data = args.repo / 'eval/prepared_model_comparison40'
    spec = importlib.util.spec_from_file_location('unchanged_oracle', data / 'evaluate.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    questions = {c['id']: c for c in json.loads((data / 'questions.json').read_text())['cases']}
    golds = {c['id']: c for c in json.loads((data / 'gold_spans.json').read_text())['cases']}
    frozen = json.loads((args.run / 'FREEZE.json').read_text())
    assert all(sha((args.repo / path).read_bytes()) == digest for path, digest in frozen['inputs_sha256'].items())
    output = []
    for cid in ('V40-P03', 'V40-E01'):
        preparation = json.loads((args.run / (cid + '-preparation.json')).read_text())
        root = Path(preparation['root'])
        prepared = dict(root=str(root), sources={})
        raw_files = {}
        for p in (data / 'sources' / questions[cid]['project_group']).rglob('*'):
            if not p.is_file():
                continue
            name = p.relative_to(data / 'sources' / questions[cid]['project_group']).as_posix()
            raw = p.read_bytes()
            assert (root / name).read_bytes() == raw
            raw_files[name] = sha(raw)
            text, offsets = raw.decode(), [0]
            for line in text.splitlines(keepends=True):
                offsets.append(offsets[-1] + len(line))
            prepared['sources'][name] = dict(raw=raw, content=text, sha256=sha(raw), line_offsets=offsets, errors=[])
        pair = {arm: json.loads((args.run / (cid + '-' + arm + '-server.json')).read_text()) for arm in ('A', 'C')}
        stage_comparisons = {}
        for stage in ('_search_rows.output', 'acquire_candidates.output', 'select_experimental_candidates.output',
                      'project_native_rank_context.output', 'project_docs_context.output'):
            values = [[e['rows'] for e in pair[arm]['events'] if e['stage'] == stage] for arm in ('A', 'C')]
            assert values[0] and values[0] == values[1]
            stage_comparisons[stage] = dict(equal=True, counts=[len(v) for v in values[0]])
        pools = {arm: [e for e in pair[arm]['events'] if e['stage'] == 'project_docs_context.output'][-1]['rows'] for arm in ('A', 'C')}
        pool = pools['A']
        verified, intervals, errors = oracle._source_rows({'sources': [r['public'] for r in pool]}, prepared)
        assert not errors
        before_gold = oracle._gold(questions[cid], golds[cid], prepared, intervals)
        assert before_gold['all_documented_claims_covered']
        gold_parts = [p for c in before_gold['claims'] for w in c['witness_sets'] for p in w['parts']]
        targets = []
        for position, (item, check) in enumerate(zip(pool, verified), 1):
            row, binding = item['public'], item['binding']
            text = prepared['sources'][check['relative_path']]['content']
            raw_hash = prepared['sources'][check['relative_path']]['sha256']
            left, right = binding['visible_char_start'], binding['visible_char_end']
            assert binding['source_sha256'] == raw_hash
            assert text[left:right] == row['snippet']
            assert sha(row['snippet'].encode()) == binding['snippet_sha256']
            assert (left, right) == (binding['reference_char_start'], binding['reference_char_end'])
            if not any(p['path'] == check['relative_path'] and left < p['char_end'] and right > p['char_start'] for p in gold_parts):
                continue
            key = row['evidence_id']
            target = dict(position=position, evidence_id=key, path=check['relative_path'],
                          lines=[row['line_start'], row['line_end']], chars=[left, right],
                          raw_sha256=raw_hash, snippet_sha256=binding['snippet_sha256'], arms={})
            for arm in ('A', 'C'):
                server = pair[arm]
                ledger = [e for e in server['events'] if e['stage'] == 'budget.ledger'][-1]
                trials = [e for e in server['events'] if e['stage'] == 'budget.cost' and (e.get('option') or {}).get('evidence_id') == key]
                omitted = key in ledger['all_omitted_evidence_ids']
                selected = key in {r['evidence_id'] for r in server['payload']['sources']}
                assert selected != omitted and trials
                assert not omitted or all(e['over_cap'] for e in trials)
                target['arms'][arm] = dict(selected=selected, omitted=omitted,
                    reason='full_DTO_cost_exceeds_12000' if omitted else 'retained',
                    trials=[dict(cost=e['cost'], cap=e['cap'], selected_before=len(e['selected_ids'])) for e in trials])
            targets.append(target)
        selected_binding_counts = {}
        for arm in ('A', 'C'):
            delivered = json.loads((args.run / (cid + '-' + arm + '-dto.txt')).read_bytes())
            assert delivered == pair[arm]['payload']
            assert set(delivered) == set(pair['A']['payload']) == set(pair['C']['payload'])
            lookup = {r['public']['evidence_id']: r for r in pool}
            for row in delivered['sources']:
                assert row == lookup[row['evidence_id']]['public']
            selected_binding_counts[arm] = len(delivered['sources'])
        output.append(dict(case_id=cid, pool_count=len(pool), full_pool_native_bytes_hashes_ranges=True,
            upstream_stages=stage_comparisons, prebudget_gold=before_gold, targets=targets,
            raw_source_sha256=raw_files, selected_binding_counts=selected_binding_counts,
            full_DTO_roundtrip=True, top_level_schema_equal=True))
    args.output.write_text(json.dumps(dict(cases=output, frozen_inputs_unchanged=True,
        evaluator_sha256=sha((data / 'evaluate.py').read_bytes()),
        gold_sha256=sha((data / 'gold_spans.json').read_bytes()), product_calls=0), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
