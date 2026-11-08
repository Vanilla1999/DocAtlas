"""Explicit one-shot attempt-02 clock-correction continuation; seal is offline."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
OUT = HERE / 'attempt-02'
ORIGINAL_SETUP = '5ed89fc9337d13c913d74b63844446c4466a8064e383512133d6c8f50157c0e1'
OLD = {
    'run.py': '64a8e83552ecb1512244bbb61c7f9dff361e534da1c8524989782ca8cbcf5989',
    'account.py': '072c21a4179fbe746a804f936e7624067f8092b0fc178e1ef6244ed1733bc3d5',
    'observe_stdio.py': 'd151e1f5ddb5eeb82faf733903a96f8a4032b3340f0b4f08a5cbf02ba95098ed',
    'observer/index.js': '9d7b1a6aeb8a7506b79ff65b979b9395b8b94b6ce21d9b14713ebfe466bca643',
}
DONE = [['A', 'V-M1'], ['B', 'V-M1']]
REMAINING = [['C', 'V-M1']] + [[a, f'V-M{i}'] for i in (2, 3, 4) for a in ('A', 'B', 'C')]


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def validate(run, manifest=None):
    if run.sha(OUT / 'setup-complete.json') != ORIGINAL_SETUP:
        raise RuntimeError('Original setup receipt changed')
    setup = run.load(OUT / 'setup-complete.json')
    changes = {}
    for path, expected in setup['inputs'].items():
        relative = str(Path(path).relative_to(HERE)) if Path(path).is_relative_to(HERE) else None
        actual = run.sha(Path(path))
        if relative in OLD:
            if expected != OLD[relative]:
                raise RuntimeError('Unexpected pre-correction capture version: ' + path)
            changes[path] = dict(old_sha256=expected, new_sha256=actual)
        elif actual != expected:
            raise RuntimeError('Unapproved config/source/runtime change: ' + path)
    if len(changes) != 4:
        raise RuntimeError('Expected exactly four reviewed experiment-only input changes')
    if manifest:
        if (manifest['changes'] != changes or manifest['completed'] != DONE or manifest['remaining'] != REMAINING
                or manifest['original_setup_sha256'] != ORIGINAL_SETUP or manifest['capture_version'] != 'wall-v2'
                or manifest['continuation_script_sha256'] != run.sha(Path(__file__))):
            raise RuntimeError('Continuation inputs differ from reviewed manifest')
        for path, expected in manifest['preserved_evidence'].items():
            if run.sha(Path(path)) != expected:
                raise RuntimeError('Preserved original evidence changed: ' + path)
    run.frozen_inputs()
    project = Path(setup['work']) / 'project'
    if run.corpus_hashes(project) != setup['source_hashes'] or run.sha(Path(setup['db'])) != setup['db_sha256']:
        raise RuntimeError('Corpus/member DB changed')
    account = import_file('step14_clock_account', HERE / 'account.py')
    revised = {}
    for arm, task in DONE:
        root = OUT / arm / task
        receipt = run.load(root / 'runtime/receipt.json')
        cleanup = receipt['cleanup']
        if (receipt['transport_pass'] is not True or receipt['returncode'] != 0
                or receipt['session_status'] != 'finished' or receipt['failures'] or receipt['capture_errors']
                or receipt['provider_capture_completed_before_cleanup'] is not True
                or cleanup['no_live_owned_processes'] is not True or cleanup['leader_reaped'] is not True
                or cleanup['registration_errors'] or not cleanup['registered_processes']
                or any(p['exit_verified'] is not True for p in cleanup['registered_processes'])
                or (root / 'fatal.json').exists()):
            raise RuntimeError('Prior session was not successfully cleaned up: ' + arm)
        state = run.load(root / 'state-after.json')
        if state != dict(sources=setup['source_hashes'], db_sha256=setup['db_sha256']):
            raise RuntimeError('Prior session modified corpus/index: ' + arm)
        if not run.gpu_restored(run.load(root / 'started.json')['gpu'], run.load(root / 'gpu-after.json'), 128):
            raise RuntimeError('Prior GPU release failed: ' + arm)
        result = account.summarize(root, arm, task)
        if (not result['usage_coverage_complete'] or result['capture_errors'] or result['retries']
                or result['mcp_missing_responses'] or result['session_ids_count'] != 1):
            raise RuntimeError('Prior provider/tool capture incomplete: ' + arm)
        if arm == 'B' and (result['host_hint_binding_verified'] is not True
                           or result['host_timestamp_order_verified'] is not None
                           or result['host_preflight_verified'] is not None):
            raise RuntimeError('Expected legacy B hint verified and timestamp ordering UNKNOWN')
        revised[arm] = result
    for arm, task in REMAINING:
        root = OUT / arm / task
        if any((root / name).exists() for name in ('started.json', 'runtime', 'capture', 'mcp-started.json',
                                                  'mcp-process.json', 'fatal.json')):
            raise RuntimeError('Continuation may launch only the ten unstarted sessions: ' + str(root))
    if (OUT / 'continuation-started.json').exists():
        raise RuntimeError('Continuation already started; automatic resume/retry forbidden')
    return changes, revised


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('seal', 'run'))
    parser.add_argument('--manifest-sha256', help='Required externally reviewed exact manifest hash for run')
    args = parser.parse_args()
    run = import_file('step14_clock_run', HERE / 'run.py')
    path = OUT / 'continuation-manifest.json'
    if args.action == 'seal':
        changes, revised = validate(run)
        evidence = {}
        for arm, task in DONE:
            for file in (OUT / arm / task).rglob('*'):
                if file.is_file():
                    evidence[str(file)] = run.sha(file)
        for name in ('run-started.json', 'run-exception.json', 'setup-complete.json', 'sources.json'):
            evidence[str(OUT / name)] = run.sha(OUT / name)
        for arm, result in revised.items():
            run.save(OUT / arm / 'V-M1/accounting-clock-v2.json', result)
        run.save(path, dict(capture_version='wall-v2', original_setup_sha256=ORIGINAL_SETUP,
            changes=changes, continuation_script_sha256=run.sha(Path(__file__)),
            preserved_evidence=evidence, completed=DONE, remaining=REMAINING,
            reason='B/V-M1 transport succeeded; Bun hrtime epoch is incompatible with Python monotonic. Preserve old ordering as UNKNOWN; do not rerun A/B.',
            required_review='Parent must review exact changes and pass this manifest SHA256 explicitly.',
            boundary='New B sessions still require hint/binding AND strict captured wall-time ordering. No source/config/policy/production edits.'))
        print('SEALED OFFLINE; provider calls=0; manifest SHA256=' + run.sha(path))
    else:
        if not args.manifest_sha256 or run.sha(path) != args.manifest_sha256:
            parser.error('Pass the externally reviewed exact --manifest-sha256')
        manifest = run.load(path)
        validate(run, manifest)
        run.run(SimpleNamespace(attempt='attempt-02', gpu_slack_mib=128), continuation=manifest)


if __name__ == '__main__':
    main()
