"""Offline receipt audit, not a selector, inference, or new product test.

Run with the frozen installed interpreter. Gold never enters a product call.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tarfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    base = repo / 'reports/docatlas-grounded-20261014/budget-diagnostic'
    load = lambda name: json.loads((base / name).read_text())
    freeze, measurements, boundary = map(load, ['FREEZE.json', 'MEASUREMENTS.json', 'BOUNDARY_ASSESSMENT.json'])
    manifest = load('RECEIPTS_ARCHIVE.json')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    assert head == freeze['code_sha']
    assert all(sha((repo / path).read_bytes()) == digest for path, digest in freeze['inputs_sha256'].items())
    import docmancer
    from docmancer.docs.application.experimental_context_finalization import experimental_context_cost
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    installed = Path(docmancer.__file__).resolve().parent
    assert all(sha((installed / path).read_bytes()) == digest for path, digest in freeze['installed_files_sha256'].items())
    archive = base / 'receipts.tar.xz'
    assert sha(archive.read_bytes()) == manifest['archive_sha256']
    with tarfile.open(archive) as tar:
        data = {name: tar.extractfile(name).read() for name in manifest['files']}
    assert all(sha(data[name]) == entry['sha256'] and len(data[name]) == entry['bytes']
               for name, entry in manifest['files'].items())
    rows = []
    for observed, assessed in zip(measurements['cases'], boundary['cases']):
        case = observed['case_id']
        trace = json.loads(data[f'run/{case}-trace.json'])['events']
        pool = next(event['rows'] for event in trace if event['stage'] == 'source_recheck.output')
        by_id = {row['public']['evidence_id']: row for row in pool}
        packet = json.loads(data[f'run/{case}-feasible-packet.json'])
        public = json.loads(data[f'run/{case}-off-public.json'])
        assert public == json.loads(data[f'run/{case}-on-public.json'])
        assert [row['evidence_id'] for row in packet['sources']] == observed['diagnostic']['selected_whole_ids']
        spans = []
        for row in packet['sources']:
            candidate = by_id[row['evidence_id']]
            assert row == candidate['public']
            binding = candidate['binding']
            target = next(item for item in assessed['targets'] if item['evidence_id'] == row['evidence_id'])
            assert all(admission['accepted'] for admission in target['admission'])
            family = 'poetry' if case == 'V40-P03' else 'eslint'
            paths = list((repo / 'eval/prepared_model_comparison40/sources').rglob(row['path_or_url']))
            paths = [path for path in paths if family in path.parts]
            assert len(paths) == 1, paths
            raw = paths[0].read_bytes()
            text = raw.decode()
            start, end = binding['reference_char_start'], binding['reference_char_end']
            assert sha(raw) == binding['source_sha256']
            assert text[start:end] == row['snippet']
            assert sha(row['snippet'].encode()) == binding['snippet_sha256']
            spans.append(dict(id=row['evidence_id'], span=[start, end], scope=row['scope'], version=row['version_binding']))
        wire = json.dumps(packet, ensure_ascii=False).encode()
        assert sha(wire) == observed['diagnostic']['feasible']['wire_sha256']
        cost = experimental_context_cost(packet)
        assert cost == observed['diagnostic']['feasible']['cost'] <= 12000
        compact = json.dumps(public, ensure_ascii=False, separators=(',', ':')).encode()
        assert json.loads(compact) == public
        compact_cost = max(projection_token_count(compact), math.ceil(len(compact) / 4))
        assert compact_cost == assessed['format_counterfactuals']['whitespace_only']['cost']
        assert all(stage['gold']['all_documented_claims_covered'] for stage in assessed['stages'][:-1])
        assert not assessed['stages'][-1]['gold']['all_documented_claims_covered']
        ledger = assessed['ledger']['ledger']
        assert len(pool) - len(public['sources']) == ledger['omitted_source_count']
        rows.append(dict(case=case, pool=len(pool), selected=len(public['sources']), omitted=ledger['omitted_source_count'],
                         actual_cost=experimental_context_cost(public), compact_cost=compact_cost,
                         feasibility_cost=cost, whole_verified_windows=spans,
                         mandatory_range_coverage=assessed['stages'][-1]['gold']['claims'][0]['witness_sets'][0]['parts'][0],
                         read_only_recorded=observed['read_only']))
    result = dict(head=head, archive_files_verified=len(data), frozen_inputs_match=True, installed_files_match=True,
                  cases=rows, product_calls=0, inference_calls=0,
                  boundary='offline audit of saved installed in-process MCP receipts; no new live validation',
                  oracle='diagnostic only: feasibility packets are gold-informed, not arm B')
    with args.output.open('x') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
