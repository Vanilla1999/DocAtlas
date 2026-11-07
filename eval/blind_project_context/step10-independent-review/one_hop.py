"""Read-only Step10 development analysis of saved packets and source graph.

No model, MCP, ingestion, production selector or annotation generator is run.
Only the pure vendored token codec is imported by file, avoiding app imports.
All 24 tasks in this analysis are already seen development material.
"""
from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

DEFAULT_REPO = Path('/workspace/scratch/66f7674793b8/DocAtlas-step10-review')
DEFAULT_OUT = Path('/workspace/scratch/66f7674793b8/step10-offline-analysis')
EXPECTED_COMMIT = '9e2c331c45e8f9a86f809a1f4d66c43125250702'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def with_ancestors(selected, units):
    return set(selected) | {a for key in selected for a in units[key]['ancestors']}


def one_hop(selected, units, *, frontier=None):
    targets = {target for key in (selected if frontier is None else frontier)
               for target in units[key]['reference_targets']}
    assert targets <= set(units), 'reference escaped allowed scope'
    return with_ancestors(set(selected) | targets, units)


def reachability(selected, units):
    seen = with_ancestors(selected, units)
    distances = {key: 0 for key in seen}
    depth = 0
    while True:
        nxt = one_hop(seen, units)
        if nxt == seen:
            return distances
        depth += 1
        distances.update({key: depth for key in nxt - seen})
        seen = nxt


def ranges(selected, units, sources):
    result = {}
    for path in sources:
        intervals = sorted((units[key]['char_start'], units[key]['char_end'])
                           for key in selected if units[key]['path'] == path)
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        if merged:
            result[path] = merged
    return result


def metrics(selected, task, units, sources, count):
    pieces = [sources[path][start:end] for path, spans in ranges(selected, units, sources).items()
              for start, end in spans]
    required = set(task['direct']) | set(task['structural'])
    present = [i for i, (key, quote) in enumerate(task['facts'])
               if key in selected and quote in sources[units[key]['path']][units[key]['char_start']:units[key]['char_end']]]
    outgoing = {target for key in selected for target in units[key]['reference_targets']}
    return {'units': len(selected), 'source_tokens': sum(count(p.encode()) for p in pieces),
            'source_bytes': sum(len(p.encode()) for p in pieces),
            'facts_found': len(present), 'facts_total': len(task['facts']), 'fact_indices': present,
            'required_units_found': len(required & selected), 'required_units_total': len(required),
            'missing_required_units': sorted(required - selected),
            'hard_negative_units': sorted(set(task.get('hard_negatives', [])) & selected),
            'unexpanded_internal_targets': sorted(outgoing - selected),
            'dependency_gaps': [{'source_unit': key, **gap} for key in sorted(selected)
                                for gap in units[key]['reference_gaps']],
            'selected_units': sorted(selected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=DEFAULT_REPO,
                        help='Clean DocAtlas checkout at the fixed reviewed commit')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT,
                        help='Directory for offline analysis artifacts, outside the checkout')
    args = parser.parse_args()
    ROOT, OUT = args.repo.resolve(), args.out.resolve()
    BASE = ROOT / 'eval/blind_project_context'
    DATA = BASE / 'step10-reference-closure-v3'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == EXPECTED_COMMIT
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    OUT.mkdir(parents=True, exist_ok=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT))
    codec_path = ROOT / 'docmancer/docs/application/projection_tokenizer.py'
    spec = importlib.util.spec_from_file_location('offline_step10_codec', codec_path)
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    count = codec.projection_token_count
    tasks = read(DATA / 'tasks.json')
    graph = read(DATA / 'source-extent-graph.json')
    projects = {p['id']: p for p in read(DATA / 'projects.json')}
    units_by_project, sources_by_project, inputs = {}, {}, {}
    for path in [DATA / 'tasks.json', DATA / 'source-extent-graph.json', DATA / 'projects.json', codec_path,
                 ROOT / 'docmancer/docs/data/o200k_base.tiktoken.gz',
                 BASE / 'step10-qwen-validation/provenance/original-policy.json']:
        inputs[str(path.relative_to(ROOT))] = sha(path)
    for name, project in projects.items():
        root = (DATA / project['root']).resolve()
        all_paths = project['project_documents'] + [p['path'] for p in project['module_documents']]
        all_sources = {path: (root / path).read_bytes().decode() for path in all_paths}
        for path in all_paths:
            inputs[str((root / path).relative_to(ROOT))] = sha(root / path)
        for unit in graph[name]:
            raw = all_sources[unit['path']]
            assert hashlib.sha256(raw.encode()).hexdigest() == unit['source_sha256']
            assert raw[unit['body_char_start']:unit['char_end']] == unit['own_text']
            assert hashlib.sha256(raw[unit['char_start']:unit['char_end']].encode()).hexdigest() == unit['whole_text_sha256']
        units_by_project[name] = {u['key']: u for u in graph[name] if u['scope'] == 'project'}
        sources_by_project[name] = {path: all_sources[path] for path in project['project_documents']}
    policy = read(BASE / 'step10-qwen-validation/provenance/original-policy.json')
    paths = {}
    for task in tasks:
        if task['id'].startswith('C-'):
            paths[task['id']] = BASE / 'step10-qwen-recovery/run-01/recovery' / task['project'] / (task['id'] + '.json')
        elif task['id'].startswith('V-'):
            paths[task['id']] = BASE / 'step10-qwen-validation/run-01/validation' / task['project'] / (task['id'] + '.json')
    for path in paths.values():
        inputs[str(path.relative_to(ROOT))] = sha(path)
    plan = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'source_commit': EXPECTED_COMMIT,
            'script_sha256': sha(Path(__file__)), 'input_sha256': inputs,
            'status': 'SEEN_DEVELOPMENT_OFFLINE_COUNTERFACTUAL',
            'primary_recipe': 'From every body in the saved final packet, follow each explicit resolved reference once; include full author-addressed target extent and ancestors. Do not expand newly added bodies.',
            'seed_only_diagnostic': 'Same target extent, but links originate only from saved model seeds >= frozen tau. Existing delivered bodies remain. This weaker frontier is not a proposed completeness guarantee.',
            'real_source_recipe': 'No Qwen outputs exist. Measure graph amplification from the oracle-complete minimum whole-body set (required direct+structural), and per-entry reachability separately. This is not model quality or retrieval prediction.',
            'real_source_frontier_diagnostic': 'Compare links from all required bodies with links from direct-labelled bodies only, retaining all required ancestors in both outputs. This isolates additional ancestor-link expansion; it is not permission to ignore ancestor dependencies.',
            'metric': 'Unique original half-open character intervals; overlap/adjacency merged per source. Vendored o200k codec for tokens; UTF-8 bytes. No wire/provider costs estimated.',
            'new_model_calls': 0, 'new_mcp_calls': 0, 'threshold_refit': False}
    save(OUT / 'one-hop-plan.json', plan)
    results, real_results, entry_results = [], [], []
    for task in tasks:
        name, ident = task['project'], task['id']
        units, sources = units_by_project[name], sources_by_project[name]
        for key, quote in task['facts']:
            assert quote in sources[units[key]['path']][units[key]['char_start']:units[key]['char_end']]
        denominator = {'allowed_source_tokens': sum(count(raw.encode()) for raw in sources.values()),
                       'allowed_source_bytes': sum(len(raw.encode()) for raw in sources.values())}
        if ident in paths:
            result = read(paths[ident])
            assert result['error'] is None and result['receipt_status'] == 'available'
            packet = result['packet']
            selected = set()
            for source in packet['sources']:
                match = [u for u in units.values() if u['path'] == source['path_or_url']
                         and u['heading_line'] == source['line_start'] and u['line_end'] == source['line_end']]
                assert len(match) == 1, 'packet row must identify one whole independent source unit'
                unit = match[0]
                assert source['snippet'] == sources[unit['path']][unit['char_start']:unit['char_end']]
                selected.add(unit['key'])
            assert with_ancestors(selected, units) == selected
            observation = result['observations'][0]
            assert observation['policy_sha256'] == sha(BASE / 'step10-qwen-validation/provenance/original-policy.json')
            seeds = set()
            for score in observation['scores']:
                match = [u for u in units.values() if u['path'] == score['path']
                         and u['char_start'] == score['char_start'] and u['char_end'] == score['char_end']]
                assert len(match) == 1
                if score['score'] >= policy['threshold']:
                    seeds.add(match[0]['key'])
            assert with_ancestors(seeds, units) == selected
            first = one_hop(selected, units)
            seed_first = one_hop(selected, units, frontier=seeds)
            distances = reachability(selected, units)
            after = metrics(first, task, units, sources, count)
            before = metrics(selected, task, units, sources, count)
            row = {'task_id': ident, 'project': name, 'split': 'recovery' if ident.startswith('C-') else 'validation',
                   'no_answer': not task['facts'], **denominator,
                   'model_seed_units': sorted(seeds), 'before': before, 'one_hop': after,
                   'seed_only_one_hop': metrics(seed_first, task, units, sources, count),
                   'added_by_ancestor_links': sorted(first - seed_first),
                   'new_fact_indices': sorted(set(after['fact_indices']) - set(before['fact_indices'])),
                   'full_reachable': metrics(set(distances), task, units, sources, count),
                   'minimum_reference_hops_from_actual_packet': distances}
            results.append(row)
        else:
            base = with_ancestors(set(task['direct']) | set(task['structural']), units)
            first = one_hop(base, units)
            direct_first = one_hop(base, units, frontier=set(task['direct']))
            distances = reachability(base, units)
            real_results.append({'task_id': ident, 'project': name, 'no_answer': not task['facts'], **denominator,
                                 'starting_set_interpretation': 'minimum label-complete bodies, NOT predicted Qwen selection',
                                 'minimum_required': metrics(base, task, units, sources, count),
                                 'one_hop': metrics(first, task, units, sources, count),
                                 'direct_only_frontier': metrics(direct_first, task, units, sources, count),
                                 'added_by_ancestor_links': sorted(first - direct_first),
                                 'full_reachable': metrics(set(distances), task, units, sources, count),
                                 'minimum_reference_hops': distances})
        # Exhaust all authored direct entry units instead of choosing a favourable
        # seed. Reachability is a source-graph diagnostic, not a retrieval result.
        required = set(task['direct']) | set(task['structural'])
        for entry in task['direct']:
            distances = reachability({entry}, units)
            fact_hops = [{'fact_index': i, 'unit': key, 'hops': distances.get(key)}
                         for i, (key, _) in enumerate(task['facts'])]
            entry_results.append({'task_id': ident, 'entry_unit': entry,
                                  'required_hops': {key: distances.get(key) for key in sorted(required)},
                                  'fact_hops': fact_hops})
    def totals(rows, before_key):
        answerable = [row for row in rows if not row['no_answer']]
        answer = {'cases': len(rows), 'answerable_cases': len(answerable),
                  'no_answer_cases': sum(row['no_answer'] for row in rows),
                  'allowed_source_tokens': sum(row['allowed_source_tokens'] for row in answerable),
                  'allowed_source_bytes': sum(row['allowed_source_bytes'] for row in answerable)}
        for variant in (before_key, 'one_hop', 'full_reachable'):
            answer[variant] = {key: sum(row[variant][key] for row in rows) for key in
                               ('facts_found', 'facts_total', 'required_units_found', 'required_units_total', 'source_tokens', 'source_bytes', 'units')}
            answer[variant]['complete_fact_cases'] = sum(row[variant]['facts_found'] == row[variant]['facts_total'] for row in rows)
            answer[variant]['empty_no_answer_cases'] = sum(row['no_answer'] and row[variant]['units'] == 0 for row in rows)
            answer[variant]['hard_negative_unit_exposures'] = sum(len(row[variant]['hard_negative_units']) for row in rows)
            answer[variant]['cases_with_dependency_gaps'] = sum(bool(row[variant]['dependency_gaps']) for row in rows)
            answer[variant]['cases_with_unexpanded_internal_targets'] = sum(bool(row[variant]['unexpanded_internal_targets']) for row in rows)
        return answer
    summary = {'analysis_status': 'SEEN_DEVELOPMENT_OFFLINE_COUNTERFACTUAL',
               'plan_sha256': sha(OUT / 'one-hop-plan.json'),
               'synthetic_totals': totals(results, 'before'),
               'synthetic_by_split': {split: totals([row for row in results if row['split'] == split], 'before')
                                      for split in ('recovery', 'validation')},
               'real_source_graph_totals': totals(real_results, 'minimum_required'),
               'real_source_by_project': {name: totals([row for row in real_results if row['project'] == name], 'minimum_required')
                                         for name in ('otel', 'embedded')},
               'synthetic_cases': results, 'real_source_graph_cases': real_results,
               'all_direct_entry_reachability': entry_results,
               'limits': ['These 16 synthetic and 8 upstream cases are already seen; no new validation PASS.',
                          'Counterfactual source assembly only; no public MCP/capability/50k wire/delivery check or new model inference.',
                          'One hop leaves new-body outgoing references unexpanded; this does not classify them as nonbinding.',
                          'The saved independent graph has documented parser/scope gaps; they remain explicit.',
                          'Real-source oracle seeds are a lower-bound source-completeness diagnostic, not predicted model seeds.',
                          'No new provider-token savings estimate.']}
    for relative, expected in inputs.items():
        assert sha(ROOT / relative) == expected, relative
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    save(OUT / 'one-hop-results.json', summary)
    forbidden = ['torch', 'transformers', 'onnxruntime', 'fastembed', 'mcp',
                 'docmancer.docs.application.minimal_context_selection',
                 'docmancer.docs.application.context_evidence_scoring']
    loaded = [name for name in sys.modules if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden)]
    assert not loaded, loaded
    save(OUT / 'one-hop-receipt.json', {
        'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_commit': EXPECTED_COMMIT, 'source_tree_clean_before_and_after': True,
        'script_sha256': sha(Path(__file__)), 'plan_sha256': sha(OUT / 'one-hop-plan.json'),
        'results_sha256': sha(OUT / 'one-hop-results.json'),
        'input_hash_assertions_before_and_after': len(inputs),
        'pure_codec_source_sha256': sha(codec_path),
        'vocabulary_uncompressed_sha256_checked_by_codec': '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d',
        'tokenizer': 'vendored o200k_base vocabulary and regex from tiktoken 0.11.0; pure offline implementation',
        'python': platform.python_version(), 'forbidden_model_or_mcp_modules_loaded': loaded,
        'new_model_calls': 0, 'new_mcp_calls': 0,
        'no_inference_or_threshold_change': True,
        'scope': 'Only saved Step10 seen development packets, labels and sources; original blind260 gold not read.'})
    print(json.dumps({key: summary[key] for key in ('analysis_status', 'synthetic_totals', 'synthetic_by_split', 'real_source_graph_totals', 'real_source_by_project')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
