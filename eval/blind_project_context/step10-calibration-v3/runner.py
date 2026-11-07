"""Closure-aware calibration: real public pipeline, once-per-input scorer memo.

The evaluator instruments closure to replay score breakpoints, never replaces
retrieval, closure, validation or delivery. Memo keys contain every scorer input.
"""
from __future__ import annotations
import argparse
import copy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'step10-calibration-v2'
spec = importlib.util.spec_from_file_location('v2_evaluator', OLD / 'runner.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
save, digest = old.save, old.digest


def inputs():
    calibration = [t for t in json.loads((OLD / 'tasks.json').read_text()) if t['split'] == 'calibration']
    return calibration + json.loads((ROOT / 'tasks.json').read_text())


def document(task):
    return (OLD if task['split'] == 'calibration' else ROOT) / task['split'] / task['document']


def freeze():
    assert not (ROOT / 'manifest.json').exists(), 'Already frozen'
    old.verify()
    labels = []
    for task in inputs():
        text = document(task).read_text()
        units = old.own_units(text)
        assert set(task['useful']) <= {u['heading'] for u in units}
        assert all(f in text for f in task['facts'])
        labels.append({'task_id': task['id'], 'units': [{**u, 'useful': u['heading'] in task['useful']} for u in units]})
    save(ROOT / 'labels.json', labels)
    paths = [ROOT / 'recipe.json', ROOT / 'tasks.json', ROOT / 'labels.json', OLD / 'tasks.json', OLD / 'labels.json']
    paths += sorted({document(t) for t in inputs()})
    save(ROOT / 'manifest.json', {'frozen_before_inference': True,
         'provenance': 'V2 calibration reused as development; new authored optics/seed archive validation, not an external benchmark',
         'files': {os.path.relpath(p, ROOT): digest(p.read_bytes()) for p in paths}})
    return verify()


def verify():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    assert all(digest((ROOT / p).read_bytes()) == h for p, h in manifest['files'].items())
    families = {}
    for t in inputs():
        families.setdefault(t['family'], set()).add(t['split'])
    assert all(len(s) == 1 for s in families.values())
    return digest((ROOT / 'manifest.json').read_bytes())


def coverage(rows, task, units):
    texts = [r['snippet'] for r in rows]
    return {'missing_units': [u['heading'] for u in units if u['useful'] and not any(u['own_text'] in s for s in texts)],
            'missing_facts': [f for f in task['facts'] if not any(f in s for s in texts)],
            'delivered_negative_units': [u['heading'] for u in units if not u['useful'] and any(u['own_text'] in s for s in texts)],
            'source_rows': len(rows), 'characters': sum(map(len, texts))}


def run(args):
    frozen = verify()
    from eval.evidence_quality_v2 import runtime
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload
    from docmancer.docs.application import minimal_context_selection as selection
    from docmancer.docs.application import minimal_context_structure as structural
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    recipe = json.loads((ROOT / 'recipe.json').read_text())
    labels = {r['task_id']: r['units'] for r in json.loads((ROOT / 'labels.json').read_text())}
    tasks = inputs()
    cache, sweeps, results = {}, {}, []
    counts = {'public_prepares': 0, 'public_queries': 0, 'scorer_executions': 0, 'scorer_cache_hits': 0, 'model_pairs': 0, 'model_forwards': 0, 'closure_replays': 0}
    actual_score, actual_close = selection.score_complete_units, structural.close_selection
    current = {'sweep': False}

    def score(queries, units, model_path, **kwargs):
        units = tuple(units)
        key = digest(json.dumps([queries, [asdict(u) for u in units], model_path, kwargs], sort_keys=True).encode())
        if key not in cache:
            cache[key] = actual_score(queries, units, model_path, **kwargs)
            counts['scorer_executions'] += 1
            for name in ('model_pairs', 'model_forwards'):
                counts[name] += cache[key][1][name]
        else:
            counts['scorer_cache_hits'] += 1
        current['scores'] = cache[key][0]
        return copy.deepcopy(cache[key])

    def close(structure, selected, payload, snapshot, retrieval):
        if current['sweep']:
            task = current['task']
            scores = current['scores']
            points = sorted({r['score'] for r in scores})
            points.append(math.nextafter(points[-1], math.inf))
            trials, previous = [], None
            for threshold in points:
                seeds = {r['identity'] for r in scores if r['score'] >= threshold}
                rows, _, receipt = actual_close(structure, seeds, payload, snapshot, retrieval)
                counts['closure_replays'] += 1
                delivered = {r['evidence_id'] for r in rows}
                assert previous is None or delivered <= previous, 'Nonmonotone closure'
                previous = delivered
                trials.append({'threshold': threshold, 'direct_units': len(seeds),
                               'direct_ids': sorted(seeds), 'delivered_ids': sorted(delivered),
                               **coverage(rows, task, labels[task['id']]), 'closure': receipt})
            sweeps[task['id']] = trials
            save(work / 'sweeps' / (task['id'] + '.json'), trials)
        return actual_close(structure, selected, payload, snapshot, retrieval)

    selection.score_complete_units, structural.close_selection = score, close
    contexts = []
    try:
        # Each phase uses isolated prepared sources; public final queries recheck them.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for split in ('calibration', 'validation'):
                for name in sorted({t['document'] for t in tasks if t['split'] == split}):
                    group = [t for t in tasks if t['split'] == split and t['document'] == name]
                    project = work / split / name.removesuffix('.md') / 'project'
                    text = document(group[0]).read_text()
                    runtime.write_project(project, {name: text})
                    contexts.append((split, group, project, text))

            def public_group(context, policy=None, sweep=False):
                split, group, project, text = context
                with runtime.isolated_service(project.parent / 'state') as (service, config):
                    os.environ.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT='1',
                                      DOCATLAS_EXPERIMENT_MINI_PATH=str(args.model_path.resolve()),
                                      DOCATLAS_MINIMAL_CONTEXT_RECIPE=recipe['recipe'])
                    os.environ.pop('DOCATLAS_MINIMAL_CONTEXT_POLICY', None)
                    if policy:
                        os.environ['DOCATLAS_MINIMAL_CONTEXT_POLICY'] = str(policy)
                    inventory = runtime.index_project(service, config, project)
                    counts['public_prepares'] += 1
                    assert not inventory['excluded_or_failed_paths'] and not inventory['unexpected_paths']
                    save(project.parent / ('prepare-diagnostic.json' if sweep else 'prepare-policy.json'), inventory)
                    before = old.db_digest(inventory['storage_path'])
                    for task in group:
                        current.update(task=task, sweep=sweep)
                        arguments = {'question': task['question'], 'project_path': str(project), 'scope': 'project'}
                        if task.get('search_question'):
                            arguments['search_question'] = task['search_question']
                        tick = time.perf_counter()
                        with selection.observe_minimal_context() as observations:
                            packet = call_docs_tool_payload('get_docs_context', arguments, service)
                        counts['public_queries'] += 1
                        suffix = '-diagnostic' if sweep else '-policy'
                        save(work / 'packets' / (task['id'] + suffix + '.json'), packet)
                        save(work / 'observations' / (task['id'] + suffix + '.json'), observations)
                        assert len(observations) == 1 and packet.get('source_selection', {}).get('scan_complete'), packet
                        checked = old.evaluate_packet(packet, labels[task['id']], task, project, text,
                                      None if policy is None else json.loads(policy.read_text())['threshold'], observations[0])
                        # Canonical source-material hashes independently reconstructed from public bytes.
                        for row in packet.get('sources', []):
                            material = {k: row.get(k) for k in ('section', 'content', 'snippet')}
                            material['content'] = row['snippet']
                            material.update(path=row['path_or_url'], version=None)
                            assert digest(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()) == row['content_sha256']
                        result = {'id': task['id'], 'split': split, 'diagnostic': sweep,
                                  **coverage(packet.get('sources', []), task, labels[task['id']]),
                                  'direct_misses': [u['heading'] for u in checked['units'] if u['useful'] and not u['direct_keep']],
                                  'noanswer': not task['facts'], 'seconds': time.perf_counter()-tick,
                                  'json_tokens': projection_token_count(json.dumps(packet, ensure_ascii=False).encode()),
                                  'source_checks': 'PASS', 'policy_sha256': observations[0]['policy_sha256']}
                        results.append(result)
                        save(work / 'results.json', results)
                    assert old.db_digest(inventory['storage_path']) == before
                    assert (project / group[0]['document']).read_text() == text

            for c in contexts:
                if c[0] == 'calibration':
                    public_group(c, sweep=True)
            all_points = sorted({t['threshold'] for trials in sweeps.values() for t in trials[:-1]})
            all_points.append(math.nextafter(all_points[-1], math.inf))
            candidates = []
            for threshold in all_points:
                at = {key: next((t for t in trials if t['threshold'] >= threshold), trials[-1]) for key, trials in sweeps.items()}
                losses = {key: {'units': t['missing_units'], 'facts': t['missing_facts']} for key, t in at.items() if t['missing_units'] or t['missing_facts']}
                contaminated = [t['id'] for t in tasks if t['split'] == 'calibration' and not t['facts'] and at[t['id']]['source_rows']]
                candidates.append({'threshold': threshold, 'losses': losses, 'noanswer_contaminated': contaminated})
            save(work / 'global-breakpoints.json', candidates)
            retained = [c for c in candidates if not c['losses']]
            best = retained[-1] if retained else None
            summary = {'manifest_sha256': frozen, 'recipe': recipe, 'best': best,
                       'calibration_feasible': bool(best is not None and not best['noanswer_contaminated'])}
            if summary['calibration_feasible']:
                policy = {k: recipe[k] for k in ('schema_version', 'calibration_recipe', 'recipe', 'structural_recipe', 'model_revision', 'lanes')}
                policy.update(threshold=best['threshold'], calibration_sha256=frozen)
                policy_path = work / 'policy.json'
                save(policy_path, policy)
                policy_hash = digest(policy_path.read_bytes())
                for c in contexts:
                    public_group(c, policy_path)
                assert digest(policy_path.read_bytes()) == policy_hash
                summary['policy_sha256'] = policy_hash
                final = [r for r in results if not r['diagnostic']]
                summary['public_final_delivery_pass'] = all(not r['missing_units'] and not r['missing_facts'] and (not r['noanswer'] or r['source_rows'] == 0) for r in final)
            summary.update(counts=counts, results=results,
                           boundary='real in-process public prepare/query, real scoring once per exact input, score memo replay on final calibration; no installed/client proof')
            save(work / 'summary.json', summary)
            return summary
    finally:
        selection.score_complete_units, structural.close_selection = actual_score, actual_close
        save(work / 'runtime-counts.json', counts)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=('freeze', 'verify', 'run'))
    p.add_argument('--work-dir', type=Path)
    p.add_argument('--model-path', type=Path, default=Path('/tmp/opencode/step10-mini-assets'))
    args = p.parse_args()
    print(json.dumps(freeze() if args.command == 'freeze' else verify() if args.command == 'verify' else run(args), ensure_ascii=False, indent=2))
