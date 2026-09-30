"""Same-path, fresh-process paired regression repeats; no failure waivers.

Invoked through the existing ablation CLI. The original tests and conftest run
unchanged. This is test diagnosis, not retrieval quality or answer evaluation.
"""
from __future__ import annotations

from collections import Counter
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

TARGETS = (
    'tests/docs/test_context_completion_followup.py::test_priority_rule_available_in_first_packet_or_one_registered_read',
    'tests/docs/test_contiguous_seed_envelope.py::test_old_inspection_uri_survives_replacement_of_unissued_draft_locators',
)


def junit_cases(path):
    result = {}
    for node in ET.parse(path).getroot().iter('testcase'):
        key = node.get('classname', '') + '::' + node.get('name', '')
        if key in result:
            raise ValueError('duplicate JUnit case: ' + key)
        status, message = 'passed', ''
        for tag in ('error', 'failure', 'skipped'):
            detail = node.find(tag)
            if detail is not None:
                status, message = tag, detail.get('message', '')
                break
        result[key] = {'status': status, 'message': message}
    return result


def run_command(cmd, *, cwd, env, timeout):
    """Bound the process group and output capture, including detached pipe holders."""
    if type(timeout) is not int or timeout < 1:
        raise ValueError('positive integer timeout required')
    process = subprocess.Popen(cmd, cwd=cwd, env=env, text=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True, close_fds=True)
    try:
        log, _ = process.communicate(timeout=timeout)
        return process.returncode, log
    except subprocess.TimeoutExpired:
        # A child may keep stdout open after its parent exits. Kill the group,
        # not only pytest; otherwise communicate() can wait indefinitely.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            log, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired as exc:
            # A deliberately detached child is no longer in our process group.
            # Do not wait indefinitely for its inherited pipe or kill unrelated
            # processes. This trusted-test runner is not a sandbox boundary.
            log = exc.stdout or ''
            if isinstance(log, bytes):
                log = log.decode('utf-8', errors='replace')
            process.stdout.close()
            log += '\n[ablation: detached output holder; bounded capture ended]\n'
        return 124, log


def repeat_pair(repo: Path, *, base: str, head: str, output: Path, repeats=2,
                full_collection=True, targets=TARGETS, timeout=180):
    from .run import _external_new_directory, _no_symlinks, sha256
    if type(timeout) is not int or timeout < 1:
        raise ValueError('positive integer timeout required')
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError('repeats must be between one and three')
    repo = _no_symlinks(repo).resolve()
    def git(*args, check=True):
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                              text=True, check=check, timeout=30)
    revisions = {name: git('rev-parse', '--verify', value + '^{commit}').stdout.strip()
                 for name, value in (('base', base), ('head', head))}
    locks = {name: git('show', sha + ':uv.lock').stdout for name, sha in revisions.items()}
    if locks['base'] != locks['head']:
        raise ValueError('paired dependency locks differ')
    output = _external_new_directory(output)
    env = dict(os.environ, DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0',
               PYTHONHASHSEED='0', DOCATLAS_REGISTRY_API_URL='http://127.0.0.1:1')
    # Do not accidentally import the parent checkout through host PYTHONPATH.
    env.pop('PYTHONPATH', None)
    records = []
    modes = ('target_only', 'full_collection') if full_collection else ('target_only',)
    with tempfile.TemporaryDirectory(prefix='docatlas-paired-path-') as tmp:
        checkout, basetemp = Path(tmp) / 'checkout', Path(tmp) / 'pytest'
        for mode in modes:
            for iteration in range(repeats):
                order = ('base', 'head') if iteration % 2 == 0 else ('head', 'base')
                for name in order:
                    cell = output / f'{mode}-{iteration}-{name}'
                    cell.mkdir()
                    created = False
                    try:
                        setup = git('worktree', 'add', '--detach', str(checkout), revisions[name])
                        created = True
                        if basetemp.exists():
                            shutil.rmtree(basetemp)  # Owned unique scratch root only.
                        cmd = [sys.executable, '-m', 'pytest']
                        if mode == 'target_only':
                            cmd.extend(targets)
                        else:
                            cmd += ['tests/', '-k', ' or '.join(t.split('::')[-1] for t in targets),
                                    '-m', 'not advanced and not live and not live_network']
                        cmd += ['-q', '--basetemp', str(basetemp), '--junitxml', str(cell / 'junit.xml')]
                        code, log = run_command(cmd, cwd=checkout, env=env, timeout=timeout)
                        (cell / 'pytest.log').write_text(log)
                        cases = junit_cases(cell / 'junit.xml') if (cell / 'junit.xml').exists() else {}
                        execution = 'EXECUTED' if code in (0, 1) and cases else 'BLOCKED_ENV'
                        record = {'side': name, 'revision': revisions[name], 'mode': mode,
                            'iteration': iteration, 'cwd': str(checkout), 'basetemp': str(basetemp),
                            'command': cmd, 'returncode': code, 'execution_status': execution,
                            'counts': dict(Counter(r['status'] for r in cases.values())), 'cases': cases}
                        (cell / 'record.json').write_text(json.dumps(record, indent=2) + '\n')
                        records.append(record)
                    finally:
                        if created:
                            git('worktree', 'remove', '--force', str(checkout))
    comparison = []
    for mode in modes:
        for iteration in range(repeats):
            pair = {r['side']: r for r in records if r['mode'] == mode and r['iteration'] == iteration}
            left, right = pair['base']['cases'], pair['head']['cases']
            common = sorted(left.keys() & right.keys())
            evaluable = all(r['execution_status'] == 'EXECUTED' for r in pair.values())
            comparison.append({'mode': mode, 'iteration': iteration, 'execution_comparable': evaluable,
                'common_ids': common if evaluable else [],
                'base_only_ids': sorted(left.keys() - right.keys()),
                'head_only_ids': sorted(right.keys() - left.keys()),
                'differences': {k: {'base': left[k], 'head': right[k]} for k in common
                                if evaluable and left[k] != right[k]}})
    result = {'schema_version': 1, 'revisions': revisions,
        'lock_sha256': sha256(locks['base'].encode()), 'python': sys.version,
        'packages': sorted({(d.metadata.get('Name', ''), d.version) for d in metadata.distributions()}),
        'planned': len(modes) * repeats * 2, 'records': records, 'comparisons': comparison,
        'all_passed': all(r['returncode'] == 0 for r in records),
        'causal_conclusion': 'NOT_ESTABLISHED', 'quality_status': 'NOT_EVALUATED'}
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result
