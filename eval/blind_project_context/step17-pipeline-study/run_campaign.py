"""Sequential old-dataset DEV campaign. Importing this module does not run MCP.

The independent legacy scorer is used only after public stdio calls finish.
Partial attempts are preserved and block resume; choose a new output root to retry.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
BLIND = HERE.parent
ROOT = BLIND.parents[1]
DEFAULT_ROOT = Path('/home/viadmin/.local/share/docatlas-eval/step17')
PIN = Path('/home/viadmin/.local/share/docatlas-eval/step16/paired-campaign/B-12000/run.json')
CACHE = Path('/home/viadmin/.local/share/docatlas-eval/step16/paired-cache')
ARMS = ('control', 'no_stop', 'no_redundancy', 'relative', 'prune_off', 'prune_union', 'competing_rows')
BUDGETS = (3000, 6000)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    # Never replace artifacts from another attempt. Callers own this output file.
    with Path(path).open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=1, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def dev_cases(case_ids=None):
    cases = [c for c in load(BLIND / 'questions.json')['cases'] if c['split'] == 'dev']
    if case_ids is not None:
        if not case_ids or set(case_ids) - {c['id'] for c in cases}:
            raise ValueError('only known old-dataset dev case IDs are allowed')
        cases = [c for c in cases if c['id'] in case_ids]
    return cases


def validate_run(out, selected=None):
    """Validate exact selected DEV universe and wire hashes; missing is an error."""
    out = Path(out)
    run = load(out / 'run.json')
    ids = run['selected_cases']
    allowed = {c['id'] for c in dev_cases()}
    if not ids or len(ids) != len(set(ids)) or set(ids) - allowed:
        raise ValueError('run is not strictly old DEV')
    if selected is not None and ids != list(selected):
        raise ValueError('selected dev cases changed')
    if run['corpora'] != ['L0', 'L2'] or run['jobs'] != 2 or run['observer'] is not False:
        raise ValueError('requires L0/L2, jobs=2, no observer')
    if run['questions_sha256'] != sha(BLIND / 'questions.json'):
        raise ValueError('question hash mismatch')
    expected = {(corpus, case) for corpus in run['corpora'] for case in ids}
    records = run['records']
    keys = [(r['corpus'], r['case_id']) for r in records]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('missing, duplicate or unexpected records')
    for record in records:
        path = (out / record['payload']).resolve()
        if not path.is_relative_to(out.resolve()) or sha(path) != record['payload_sha256']:
            raise ValueError('payload path/hash mismatch')
        if record['is_error'] or record.get('portions'):
            raise ValueError('MCP error or unexpected continuation')
    return run


def score_run(out, selected_cases=None, *, write=True):
    """Reusable offline API -> selected-dev score dict; never invokes inference.

    Uses score.score's audited span-union oracle, not trace heuristics. It reads
    the existing old oracle/audit files offline, but evaluates DEV entries only.
    No fresh_eval or holdout reports are opened/written.
    """
    out = Path(out).resolve()
    run = validate_run(out, selected_cases)
    scorer = module('step17_old_scorer', BLIND / 'score.py')
    result = scorer.score(out)
    expected = {(corpus, cid) for corpus in run['corpora'] for cid in run['selected_cases']}
    keys = [(c['corpus'], c['case_id']) for c in result['cases']]
    if len(keys) != len(set(keys)) or set(keys) != expected or any(c['split'] != 'dev' for c in result['cases']):
        raise ValueError('scorer returned a different universe')
    result['scope'] = 'old dataset selected dev only; missing records never pass'
    if write:
        save(out / 'score.json', result)
    return result


def environment(arm, budget, trace):
    old = load(PIN)['server_environment']
    # Explicit allowlist: never inherit a legacy trace, HOME or arm configuration.
    keys = ('DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH', 'DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT',
            'DOCATLAS_CONTEXT_COMPRESSION', 'DOCATLAS_MCP_TEXT_FALLBACK', 'DOCATLAS_MCP_COMPACT_TEXT')
    env = {k: old[k] for k in keys}
    env.update(DOCATLAS_OFFLINE='1', HF_HUB_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0',
               DOCATLAS_EXPERIMENT_QWEN_STUDY='1', DOCATLAS_EXPERIMENT_PAIRED_QWEN='1',
               DOCATLAS_EXPERIMENT_PAIRED_CACHE=str(CACHE),
               DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS=str(budget),
               DOCATLAS_EXPERIMENT_PAIRED_TRACE=str(trace),
               DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE=arm if arm in ARMS[:4] else 'control',
               DOCATLAS_EXPERIMENT_QWEN_STUDY_PRUNING={'prune_off': 'off', 'prune_union': 'body_union'}.get(arm, 'control'),
               DOCATLAS_EXPERIMENT_QWEN_STUDY_UNITS='competing_rows' if arm == 'competing_rows' else 'control',
               DOCATLAS_EXPERIMENT_QWEN_STUDY_UNIT_GUARD='conservative' if arm == 'competing_rows' else 'off')
    return env


def disk_check(*paths, minimum=1024**3):
    values = {}
    for path in paths:
        path = Path(path)
        while not path.exists():
            path = path.parent
        free = shutil.disk_usage(path).free
        values[str(path)] = free
        if free < minimum:
            raise RuntimeError(f'need at least {minimum} free bytes at {path}; available {free}')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--work-root', required=True, type=Path)
    parser.add_argument('--reuse-first', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--arm', action='append', choices=ARMS)
    parser.add_argument('--budget', action='append', type=int, choices=BUDGETS)
    parser.add_argument('--case', action='append')
    parser.add_argument('--split', choices=('dev',), default='dev', help='only old development cases are permitted')
    parser.add_argument('--min-free-gib', type=float, default=1)
    args = parser.parse_args()
    if args.min_free_gib < 1:
        parser.error('disk floor cannot be less than 1 GiB')
    out, work = args.output_root.resolve(), args.work_root.resolve()
    if out == work or out.is_relative_to(work):
        parser.error('output root must not be inside work root')
    ids = [c['id'] for c in dev_cases(args.case)]
    arms = list(dict.fromkeys(args.arm or ARMS))
    budgets = list(dict.fromkeys(args.budget or BUDGETS))
    if not CACHE.is_dir():
        parser.error(f'required existing cache missing: {CACHE}')
    if work.exists() and not (args.reuse_first or args.resume):
        parser.error('existing work requires --reuse-first (never delete it)')
    if args.reuse_first and not work.is_dir():
        parser.error('--reuse-first requires existing work')
    free = disk_check(out, work, CACHE, minimum=int(args.min_free_gib * 1024**3))
    runner = module('step17_old_runner', BLIND / 'run.py')
    code = runner.git_state(ROOT)
    config = {'arms': arms, 'budgets': budgets, 'selected_cases': ids, 'corpora': ['L0', 'L2'],
              'jobs': 2, 'work_root': str(work), 'source_tree': str(ROOT), 'pin_sha256': sha(PIN),
              'code_manifest_sha256': code['code_manifest_sha256'],
              'scripts': {p.name: sha(p) for p in (Path(__file__), HERE / 'summarize_campaign.py')},
              'environments': {f'{a}-{b}': environment(a, b, out / f'{a}-{b}.jsonl.gz') for b in budgets for a in arms}}
    manifest = out / 'campaign.json'
    if out.exists():
        if not args.resume or not manifest.is_file() or load(manifest)['config'] != config:
            parser.error('existing output requires --resume and identical campaign config/code')
    else:
        out.mkdir(parents=True)
        save(manifest, {'status': 'STARTED', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                        'config': config, 'source_state': code, 'disk_free_bytes': free})
    # Campaign lock also serializes validation/resume decisions.
    import fcntl
    with (out / '.campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for budget in budgets:
            for arm in arms:
                name = f'{arm}-{budget}'
                dest, trace = out / name, out / f'{name}.jsonl.gz'
                completed = dest / 'COMPLETED.json'
                if completed.exists():
                    receipt = load(completed)
                    validate_run(dest, ids)
                    if receipt['config'] != config['environments'][name] or any(sha(dest / p) != h for p, h in receipt['artifacts'].items()):
                        raise ValueError(f'{name}: completed receipt no longer validates')
                    from summarize_campaign import summarize_run
                    if not summarize_run(out, name, config)['valid']:
                        raise ValueError(f'{name}: completed score/trace validation failed')
                    print(f'skip validated COMPLETED {name}', flush=True)
                    continue
                if dest.exists() or trace.exists() or (out / f'{name}.start.json').exists():
                    raise RuntimeError(f'{name}: partial attempt preserved; use a new output root, no automatic rerun')
                disk = disk_check(out, work, CACHE, minimum=int(args.min_free_gib * 1024**3))
                reuse = work.exists()
                cmd = [sys.executable, str(BLIND / 'run.py'), str(dest), '--source-tree', str(ROOT),
                       '--split', 'dev', '--corpus', 'L0', '--corpus', 'L2', '--jobs', '2',
                       '--work-root', str(work), '--keep-work', '--no-observer']
                if reuse:
                    cmd.append('--reuse-work')
                for cid in ids:
                    cmd += ['--case', cid]
                env = config['environments'][name]
                for k, v in env.items():
                    cmd += ['--env', f'{k}={v}']
                save(out / f'{name}.start.json', {'status': 'STARTED', 'command': cmd, 'environment': env,
                     'started_at_utc': datetime.now(timezone.utc).isoformat(), 'source_state': code, 'disk_free_bytes': disk})
                # Original runner opens a sibling work lock before creating work.
                work.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(cmd, check=True, cwd=ROOT)
                started = time.perf_counter()
                scored = score_run(dest, ids)
                scoring_seconds = time.perf_counter() - started
                from summarize_campaign import inspect_trace
                run = validate_run(dest, ids)
                checked = inspect_trace(trace, run, budget,
                                        expected_arm=f'step17_{arm if arm in ARMS[:4] else "control"}')
                over_budget = any(max(c['o200k_tokens'], (c['utf8_bytes'] + 3) // 4) > budget for c in scored['cases'])
                code_changed = run['source_tree']['code_manifest_sha256'] != code['code_manifest_sha256']
                env_changed = any(run['server_environment'].get(k) != v for k, v in env.items())
                if scored['anomalies'] or checked['errors'] or over_budget or code_changed or env_changed:
                    raise RuntimeError(f'{name}: invalid score/trace/budget/provenance; no completion marker')
                save(completed, {'status': 'COMPLETED', 'config': env, 'offline_scoring_seconds': scoring_seconds,
                     'artifacts': {p: sha(dest / p) for p in ('run.json', 'score.json', '../' + trace.name)}})
    print(f'Completed requested selected-dev campaign: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
