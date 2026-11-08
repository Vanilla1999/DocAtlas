"""Authorized one-shot recovery: inspect B/V-M4, run ONLY unstarted C/V-M4."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
OUT = HERE / 'attempt-02'
RECOVERY = OUT / 'recovery-02'
EXPECTED_MANIFEST = '34cf80203ab975649bc312bab63d20d9865ce81831bc14c950fdb32a80bf81fb'
SESSION = 'ses_e45ba8e12ffemMNVd4DWE6CSaC'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    os.umask(0o077)
    sys.dont_write_bytecode = True
    run = module('step14_recovery_run', HERE / 'run.py')
    account = module('step14_recovery_account', HERE / 'account.py')
    setup = run.load(OUT / 'setup-complete.json')
    manifest = run.load(OUT / 'continuation-manifest.json')
    if run.sha(OUT / 'continuation-manifest.json') != EXPECTED_MANIFEST:
        raise RuntimeError('Reviewed continuation manifest changed')
    if run.sha(OUT / 'setup-complete.json') != manifest['original_setup_sha256']:
        raise RuntimeError('Original setup changed')
    if run.sha(HERE / 'continuation.py') != manifest['continuation_script_sha256']:
        raise RuntimeError('Reviewed continuation coordinator changed')
    for path, original in setup['inputs'].items():
        expected = manifest['changes'].get(path, {}).get('new_sha256', original)
        if run.sha(Path(path)) != expected:
            raise RuntimeError('Config/runtime/capture input changed: ' + path)
    for path, expected in manifest['preserved_evidence'].items():
        if run.sha(Path(path)) != expected:
            raise RuntimeError('Original A/B evidence changed: ' + path)
    run.frozen_inputs()
    work, db = Path(setup['work']), Path(setup['db'])
    project = work / 'project'
    if run.corpus_hashes(project) != setup['source_hashes'] or run.sha(db) != setup['db_sha256']:
        raise RuntimeError('Corpus/index changed')
    target = OUT / 'C/V-M4'
    if any((target / name).exists() for name in ('started.json', 'runtime', 'capture', 'fatal.json')):
        raise RuntimeError('C/V-M4 has already started; no retry permitted')
    prior_files = {}
    prior_receipts = {}
    for task in ('V-M1', 'V-M2', 'V-M3', 'V-M4'):
        for arm in ('A', 'B', 'C'):
            root = OUT / arm / task
            if root == target:
                continue
            if not (root / 'started.json').exists():
                raise RuntimeError('Unexpected unstarted case; authorization is only C/V-M4')
            prior_files.update({str(p): run.sha(p) for p in root.rglob('*') if p.is_file()})
            if (arm, task) == ('B', 'V-M4'):
                if (root / 'runtime/receipt.json').exists():
                    raise RuntimeError('Unexpected B receipt; inspect rather than overwrite assumptions')
                continue
            receipt = run.load(root / 'runtime/receipt.json')
            if (receipt['transport_pass'] is not True or receipt['cleanup']['no_live_owned_processes'] is not True
                    or receipt['cleanup']['leader_reaped'] is not True):
                raise RuntimeError('Prior session incomplete: ' + str(root))
            prior_receipts[arm + '/' + task] = 'successful recorded transport and cleanup'
    RECOVERY.mkdir(mode=0o700, exist_ok=False)
    run.save(RECOVERY / 'coordinator-timeout.json', dict(
        cause='Parent reports outer shell timeout of 120 seconds killed continuation coordinator while B/V-M4 was executing',
        attribution='external harness timeout, not a model retry', observed_wall_time_ns=time.time_ns(),
        missing_runtime_receipt='B/V-M4/runtime/receipt.json', fabricated_receipt=False,
        authorization='Recover existing evidence, then run only never-started C/V-M4',
        reviewed_manifest_sha256=EXPECTED_MANIFEST, recovery_script_sha256=run.sha(Path(__file__))))
    run.save(RECOVERY / 'preserved-prior-evidence.json', prior_files)
    root = OUT / 'B/V-M4'
    process_rows = run.load(root / 'mcp-process.json')['processes']
    observations = []
    for pid in [224777, *[row['pid'] for row in process_rows]]:
        proc = Path(f'/proc/{pid}/stat')
        observations.append(dict(pid=pid, exists=proc.exists()))
        if proc.exists():
            raise RuntimeError('Previously owned PID currently exists; manual identity review required, no signals sent')
    before = run.gpu()
    if not run.gpu_restored(run.load(root / 'started.json')['gpu'], before, 128):
        raise RuntimeError('GPU not restored relative to B start')
    run.save(RECOVERY / 'cleanup-observed.json', dict(processes=observations, gpu=before,
        source_hashes=run.corpus_hashes(project), db_sha256=run.sha(db),
        boundary='Post-hoc process absence/GPU state, not a reconstructed cleanup receipt or known exit code'))
    state = run.load(root / 'capture/state.json')
    if not (state['requests'] == state['completed'] == len(state['usage_ids']) == 3 and state['capture_errors'] == 0):
        raise RuntimeError('B provider capture incomplete')
    events = account.rows(root / 'capture/events.jsonl')
    if {e.get('sessionID') for e in events if e.get('sessionID')} != {SESSION}:
        raise RuntimeError('B session mismatch')
    records = {r['id']: r for e in events for r in account.usage_records(e.get('data'))}
    if set(records) != set(state['usage_ids']) or any(r.get('status') != 'completed' for r in records.values()):
        raise RuntimeError('B lacks complete provider responses')
    final = records[state['usage_ids'][-1]]
    answer = '\n'.join(part['text'] for item in final.get('output', [])
        if item.get('type') == 'message' and item.get('role') == 'assistant' and item.get('status') == 'completed'
        for part in item.get('content', []) if part.get('type') == 'output_text')
    if not answer:
        raise RuntimeError('B final provider answer absent')
    evidence = account.summarize(root, 'B', 'V-M4')
    if (not evidence['usage_coverage_complete'] or evidence['host_preflight_verified'] is not True
            or evidence['mcp_missing_responses'] or evidence['capture_errors'] or evidence['retries']):
        raise RuntimeError('B native capture validation failed')
    run.save(RECOVERY / 'B-provider-completion.json', dict(session=SESSION,
        final_response_id=final['id'], final_response_status=final['status'], answer=answer,
        provider_records=evidence['provider_records'], usage=evidence['usage'],
        cli_answer=evidence['answer'], cli_capture_complete=False,
        runtime_receipt_present=False, transport_exit_status=None,
        host_preflight_verified=evidence['host_preflight_verified'],
        boundary='Answer and all three usage records recovered from actual completed provider bodies; not a synthesized CLI/runtime receipt'))
    # Read-only shared-session export through the current managed service. No
    # prompt/interrupt/delete/credential endpoint and no standalone process here.
    for name, endpoint in (
        ('B-session-info.json', f'/api/session/{SESSION}'),
        ('B-session-export.json', f'/api/experimental/session/{SESSION}/export?sanitize=false')):
        result = subprocess.run([setup['opencode'], 'api', 'get', endpoint],
                                capture_output=True, text=True, check=True, timeout=30)
        run.save(RECOVERY / name, json.loads(result.stdout))
    exported = run.load(RECOVERY / 'B-session-export.json')
    answer_in_export = answer in '\n'.join(account.strings(exported))
    run.save(RECOVERY / 'B-export-verification.json', dict(final_provider_answer_in_export=answer_in_export,
        provider_final_response_id=final['id'], session=SESSION, read_only_api=True))
    if not answer_in_export:
        raise RuntimeError('B final answer not found in durable session export; stop for review')
    if run.auth_topology(Path(setup['opencode']), work) != setup['auth_topology']:
        raise RuntimeError('Existing-user topology changed')
    # Recheck immediately before the only authorized model run.
    if (target / 'started.json').exists() or (target / 'runtime').exists() or (target / 'capture').exists():
        raise RuntimeError('C/V-M4 concurrently started')
    if run.corpus_hashes(project) != setup['source_hashes'] or run.sha(db) != setup['db_sha256']:
        raise RuntimeError('Corpus/index changed during recovery')
    runtime = module('step14_recovery_runtime', HERE / 'session_runtime.py')
    task = next(t for t in run.load(HERE / 'tasks.json') if t['id'] == 'V-M4')
    run.save(target / 'started.json', dict(model=run.MODEL, monotonic_ns=time.monotonic_ns(), gpu=before,
        recovery='recovery-02', only_authorized_case='C/V-M4'))
    try:
        launched = runtime.launch_session(opencode=Path(setup['opencode']), location=work / 'locations/C/V-M4',
            question=task['question'], env=run.client_environment(work), output=target / 'runtime',
            model=run.MODEL, agent='measure', timeout=900, title='Step14 C V-M4',
            owned_process_files=(), fatal=target / 'fatal.json', capture=target / 'capture')
    finally:
        after = run.gpu()
        run.save(target / 'gpu-after.json', after)
        run.save(target / 'state-after.json', dict(sources=run.corpus_hashes(project), db_sha256=run.sha(db)))
    c_account = account.summarize(target, 'C', 'V-M4')
    run.save(target / 'accounting.json', c_account)
    subprocess.run([sys.executable, '-B', '-I', str(HERE / 'account.py'), '--attempt', 'attempt-02',
                    '--output', str(OUT / 'accounting-final.json')], check=True, timeout=30)
    unchanged = all(run.sha(Path(p)) == digest for p, digest in prior_files.items())
    passed = (launched['receipt']['transport_pass'] and c_account['usage_coverage_complete']
        and not c_account['capture_errors'] and not c_account['retries']
        and run.gpu_restored(before, after, 128) and unchanged
        and run.corpus_hashes(project) == setup['source_hashes'] and run.sha(db) == setup['db_sha256'])
    run.save(RECOVERY / 'recovery-complete.json', dict(
        status='COMPLETED_WITH_B_CLI_CAPTURE_GAP' if passed else 'C_OR_RECOVERY_CHECK_FAILED',
        prior_receipts=prior_receipts, preserved_prior_files_unchanged=unchanged,
        new_sessions=1, only_new_case='C/V-M4', C_transport_pass=launched['receipt']['transport_pass'],
        B_provider_responses_completed=3, B_durable_answer_verified=answer_in_export,
        B_runtime_receipt_reconstructed=False, total_started_sessions=12,
        accounting='attempt-02/accounting-final.json',
        accounting_boundary='B/V-M4 CLI-derived answer/tool counters incomplete; actual provider usage/answer and MCP calls retained separately. B/V-M1 timestamp ordering remains unknown.',
        answer_quality='NOT_GRADED'))
    print(json.dumps(dict(recovery_status='completed' if passed else 'failed', new_sessions=1,
                         provider_requests_C=c_account['provider_requests'], recovery=str(RECOVERY))))
    if not passed:
        raise RuntimeError('Recovery final checks failed; no automatic rerun')


if __name__ == '__main__':
    main()
