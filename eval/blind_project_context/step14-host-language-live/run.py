"""Step14 installed setup and one non-resumable 12-session live run. No default run."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
WORK_ROOT = Path('/home/viadmin/.local/share/docatlas-eval/step14/work')
USER_HOME = Path('/home/viadmin')
USER_DATA = USER_HOME / '.local/share'
MODEL = 'openai/gpt-6.1-terra#low'
POLICY = HERE.parent / 'step10-qwen-validation/provenance/original-policy.json'
RUNTIME = HERE / 'session_runtime.py'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text())


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def frozen_inputs():
    subprocess.run([sys.executable, '-I', str(HERE / 'verify_inputs.py')], check=True)


def corpus_hashes(project):
    return {p.relative_to(project).as_posix(): sha(p) for p in project.rglob('*') if p.is_file()}


def gpu():
    def query(kind, fields):
        result = subprocess.run(['nvidia-smi', f'--query-{kind}={fields}', '--format=csv,noheader,nounits'],
                                text=True, capture_output=True, timeout=15, check=True)
        return [line.strip().split(', ') for line in result.stdout.splitlines() if line.strip()]
    return dict(monotonic_ns=time.monotonic_ns(),
                devices=query('gpu', 'uuid,memory.used,memory.free'),
                compute=query('compute-apps', 'gpu_uuid,pid,used_memory'))


def gpu_restored(before, after, slack):
    # Preserve ambient compute (e.g. the user's live Blender). Only a NEW GPU
    # consumer or unreleased memory prevents the next experimental session.
    devices_before = {row[0]: int(row[1]) for row in before['devices']}
    devices_after = {row[0]: int(row[1]) for row in after['devices']}
    compute_before = {(row[0], row[1]) for row in before['compute']}
    compute_after = {(row[0], row[1]) for row in after['compute']}
    return (compute_after <= compute_before and devices_before.keys() == devices_after.keys()
            and all(devices_after[key] <= value + slack for key, value in devices_before.items()))


def client_environment(work):
    # Normal documented standalone uses the same user's persistent data and
    # credentials. Do not inherit API keys, provider overrides or OPENCODE_DB:
    # this experiment uses the already connected OpenCode account.
    env = {k: os.environ[k] for k in ('PATH', 'LANG', 'LC_ALL', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
                                    'CUDA_VISIBLE_DEVICES') if k in os.environ}
    env.update(HOME=str(USER_HOME), XDG_CONFIG_HOME=str(work / 'client-config'),
        XDG_DATA_HOME=str(USER_DATA), XDG_STATE_HOME=str(work / 'client-state'),
        XDG_CACHE_HOME=str(work / 'client-cache'), TMPDIR=str(work / 'tmp'),
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    return env


def auth_topology(opencode, work):
    # Documented read-only command: no server startup, credential read or model
    # request. Check actual installed path resolution, not a guessed DB override.
    output = subprocess.run([str(opencode), 'debug', 'paths'], env=client_environment(work),
                            cwd=work, text=True, capture_output=True, check=True, timeout=30).stdout
    actual = dict(line.split(None, 1) for line in output.splitlines() if line.strip())
    expected = dict(home=str(USER_HOME), data=str(USER_DATA / 'opencode'),
        db=str(USER_DATA / 'opencode/opencode.db'), log=str(USER_DATA / 'opencode/log'),
        config=str(work / 'client-config/opencode'), state=str(work / 'client-state/opencode'),
        cache=str(work / 'client-cache/opencode'), tmp=str(work / 'tmp/opencode'))
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Installed OpenCode path topology differs from reviewed existing-user mode')
    return dict(auth='existing-user', checked_by='opencode debug paths (no server/provider start)',
        paths=actual, credential_values_accessed=False, credentials_copied=False,
        api_key_environment_forwarded=False, login_started=False,
        boundary='Private process/server, shared user data/credentials/session DB/native log; isolated config/state/cache. Normal OpenCode credential refresh may update shared data.')


def qualify(args):
    """No model loading: verify exact wheel contents, assets, CUDA package/device metadata."""
    if Path(sys.executable).absolute() != args.python.absolute() or not sys.flags.isolated:
        raise RuntimeError('Invoke with the installed --python using -I (no source checkout imports)')
    import docmancer
    from docmancer.docs.application import context_evidence_scoring as scorer
    import torch
    package = Path(docmancer.__file__).resolve().parent
    if package.is_relative_to(TREE) or not package.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('DocAtlas is not imported from the installed environment')
    if sha(args.wheel) != '0a7c36ff9f2b3066e6c810bdeca39a2f126458446f3c16a919ba5ac59afccadb':
        raise RuntimeError('Wheel does not match the explicitly supplied installer receipt')
    distribution = importlib.metadata.distribution('doc-atlas')
    direct = json.loads(distribution.read_text('direct_url.json') or '{}')
    if direct.get('dir_info', {}).get('editable'):
        raise RuntimeError('Editable installations are forbidden')
    with zipfile.ZipFile(args.wheel) as wheel:
        names = [n for n in wheel.namelist() if n.startswith('docmancer/') and not n.endswith('/')]
        if not names:
            raise RuntimeError('Wheel has no docmancer files')
        for name in names:
            installed = package.parent / name
            if not installed.is_file() or installed.read_bytes() != wheel.read(name):
                raise RuntimeError('Installed wheel mismatch: ' + name)
    scorer.verify_assets(str(args.assets))
    runtime = dict(torch=torch.__version__, cuda=torch.version.cuda,
                   **{n: importlib.metadata.version(n) for n in ('transformers', 'tokenizers', 'safetensors')},
                   capability=list(torch.cuda.get_device_capability(0)), dtype='bfloat16', attention='sdpa', batch=1)
    if runtime != scorer.RUNTIME or runtime != load(HERE.parent / 'step12-live-comparison/runtime.json'):
        raise RuntimeError('Pinned runtime mismatch: ' + json.dumps(runtime))
    return dict(wheel=str(args.wheel), wheel_sha256=sha(args.wheel), package=str(package),
                version=distribution.version, verified_wheel_members=len(names), runtime=runtime,
                recipe=scorer.RECIPE, assets={n: sha(args.assets / n) for n in scorer.ASSETS},
                asset_provenance_sha256=sha(args.assets / 'provenance.json'), inference_calls=0)


async def prepare(project, env, cli, output):
    """Real public installed stdio call, not a direct internal retrieval invocation."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    # Only derive the host-selected storage/consent target; mutation uses MCP.
    previous = dict(os.environ)
    try:
        for key in tuple(os.environ):
            if key.startswith('DOCATLAS_'):
                del os.environ[key]
        os.environ.update(env)
        service = create_local_mcp_service()
        storage = service.member_storage_policy
        catalog = read_project_docs_catalog(project)
        if storage.validate(project, service.config.index.db_path):
            raise RuntimeError('Refusing to adopt an existing member index')
        arguments = dict(action='sync_project_docs', project_path=str(project), mutation=dict(
            operation='sync_project_docs', confirm=True, storage_path=str(storage.db_path),
            expected_generation_id=None, catalog_sha256=sha(project / 'docatlas.project-docs.yaml'),
            documents=[dict(path=r.path, content_sha256=sha(project / r.path),
                            catalog_entry_hash=catalog_entry_hash(r)) for r in catalog.entries]))
        save(output / 'prepare-request.json', arguments)
        clean = {k: v for k, v in os.environ.items() if not k.startswith('DOCATLAS_')}
        clean.update(env)
        with (output / 'prepare.stderr.log').open('x') as stderr:
            async with stdio_client(StdioServerParameters(command=str(cli), args=['mcp', 'docs-serve'],
                                                         cwd=str(project), env=clean), errlog=stderr) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool('prepare_docs', arguments)
                    save(output / 'prepare-wire-response.json', result.model_dump(mode='json'))
        payload = result.structuredContent
        if not payload:
            payload = json.loads(next(part.text for part in result.content if part.type == 'text'))
        save(output / 'preparation.json', payload)
        if result.isError or payload.get('status') != 'success' or payload.get('metrics', {}).get('members') != 6:
            raise RuntimeError('Public preparation failed; inspect preserved response; no retry')
        return Path(storage.db_path)
    finally:
        os.environ.clear()
        os.environ.update(previous)


def paths(args):
    for name in ('work', 'state', 'python', 'assets', 'wheel', 'opencode'):
        p = getattr(args, name)
        if not p.is_absolute():
            raise ValueError('--' + name + ' must be absolute')
    if not args.work.resolve().is_relative_to(WORK_ROOT) or not args.state.resolve().is_relative_to(args.work.resolve()):
        raise ValueError('work must be inside the authorized step14/work; state must be inside this work')
    for ancestor in [args.work, *args.work.parents]:
        for name in ('opencode.json', 'opencode.jsonc', '.opencode/opencode.json', '.opencode/opencode.jsonc',
                     '.opencode/plugins', 'AGENTS.md'):
            if (ancestor / name).exists():
                raise ValueError('Unexpected ancestor configuration/instructions: ' + str(ancestor / name))


def setup(args):
    import yaml
    paths(args)
    frozen_inputs()
    out = HERE / args.attempt
    out.mkdir(mode=0o700, exist_ok=False)
    save(out / 'setup-started.json', dict(inference_calls=0, work=str(args.work)))
    args.work.mkdir(parents=True, mode=0o700, exist_ok=False)
    args.state.mkdir(parents=True, mode=0o700, exist_ok=False)
    # Confine library caches, config and temporary files; no installer directories are modified.
    for name in ('home', 'cache', 'tmp', 'client-config', 'client-state', 'client-cache'):
        (args.work / name).mkdir(mode=0o700)
    topology = auth_topology(args.opencode, args.work)
    save(out / 'auth-topology.json', topology)
    os.environ.update(HOME=str(args.work / 'home'), XDG_CACHE_HOME=str(args.work / 'cache'),
                      TMPDIR=str(args.work / 'tmp'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    qualification = qualify(args)
    save(out / 'qualification.json', qualification)
    version = subprocess.run([str(args.opencode), '--version'], capture_output=True, text=True, check=True).stdout.strip()
    if version not in ('2.2.5', 'opencode v2.2.5'):
        raise RuntimeError('Review native hooks/launcher on this OpenCode version first: ' + version)
    project = args.work / 'project'
    project.mkdir()
    data = HERE.parent / 'step10-multidoc-gate'
    descriptor = next(p for p in load(data / 'projects.json') if p['id'] == 'meridian')
    if len(descriptor['project_documents']) != 6:
        raise RuntimeError('Source roster changed')
    for name in descriptor['project_documents']:
        (project / name).write_bytes((data / descriptor['root'] / name).read_bytes())
    (project / 'AGENTS.md').write_text('This documentation fixture is read-only. Never change its source documents.\n')
    catalog = dict(schema_version=1, code_files=[],
        documentation_languages={p: ['en'] for p in descriptor['project_documents']},
        documents=[dict(path=p, role='other', scope='project', authority='source_of_truth', status='active',
                        impact='track', description='Documentation source') for p in descriptor['project_documents']])
    (project / 'docatlas.project-docs.yaml').write_text(yaml.safe_dump(catalog, sort_keys=False))
    save(out / 'sources.json', corpus_hashes(project))
    cli = args.python.parent / 'doc-atlas'
    env = dict(DOCATLAS_HOME=str(args.state), DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0',
               DOCATLAS_CONTEXT_COMPRESSION='off', ORT_DISABLE_TELEMETRY='1', PYTHONDONTWRITEBYTECODE='1')
    db = asyncio.run(asyncio.wait_for(prepare(project, env, cli, out), timeout=180))
    profile = module('step14_profile', TREE / 'integrations/opencode-v2-compact/documentation_profile.py')
    tasks = load(HERE / 'tasks.json')
    save(args.work / 'client-config/opencode/opencode.json', {'update': 'disable'})
    base_runtime = HERE.parent / 'step13-runtime-token-review/session_runtime.py'
    inputs = {str(RUNTIME): sha(RUNTIME), str(base_runtime): sha(base_runtime)}
    for task in tasks:
        for arm in ('A', 'B', 'C'):
            location = args.work / 'locations' / arm / task['id']
            location.mkdir(parents=True)
            case = out / arm / task['id']
            case.mkdir(parents=True, mode=0o700)
            selected = dict(env)
            if arm != 'C':
                selected.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT='1',
                    DOCATLAS_MINIMAL_CONTEXT_RECIPE=qualification['recipe'],
                    DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH=str(args.assets),
                    DOCATLAS_MINIMAL_CONTEXT_POLICY=str(POLICY), DOCATLAS_CONTEXT_LINKS='one-hop-v1')
            config, receipt = profile.build_profile(project_root=project, workspace=location,
                backend='files' if arm == 'C' else 'mcp', executable=cli, python=args.python,
                server_environment=selected, agent_name='measure', model=MODEL, frozen=True, max_steps=12,
                instruction_variant='concise-v1', language_preflight='host-v1' if arm == 'B' else 'model')
            config['compaction'] = {'auto': False}
            config['warming'] = False
            # Keep the built-in OpenAI connection/credential selected by the user.
            # Only disable body compression to retain readable native capture.
            config['providers'] = {'openai': {'settings': {'encoding': 'none'}}}
            config['plugins'].append(dict(package=str(HERE / 'observer'), options=dict(
                output=str(case / 'capture'), fatal=str(case / 'fatal.json'))))
            if arm != 'C':
                server = config['mcp']['servers']['docatlas']
                server['command'] = [str(args.python), '-I', str(HERE / 'observe_stdio.py'), str(case), *server['command']]
            save(location / 'opencode.json', config)
            save(case / 'config.json', config)
            save(case / 'profile.json', receipt)
            inputs[str(location / 'opencode.json')] = sha(location / 'opencode.json')
            for relative, digest in receipt['inputs'].items():
                inputs[str(TREE / 'integrations/opencode-v2-compact' / relative)] = digest
    for name in ('run.py', 'observe_stdio.py', 'account.py', 'observer/index.js', 'observer/package.json'):
        inputs[str(HERE / name)] = sha(HERE / name)
    save(out / 'setup-complete.json', dict(model=MODEL, sessions=12, steps=12, timeout=900,
        work=str(args.work), state=str(args.state), python=str(args.python), assets=str(args.assets),
        wheel=str(args.wheel), opencode=str(args.opencode), opencode_version=version, auth=args.auth,
        auth_topology=topology,
        db=str(db), db_sha256=sha(db), inputs=inputs, source_hashes=corpus_hashes(project),
        preparation_calls=1, inference_calls=0, status='PREPARED_NOT_LIVE_RESULT'))
    print('PREPARED: ' + str(out) + '; no inference/provider calls')


def run(args, continuation=None):
    out = HERE / args.attempt
    setup = load(out / 'setup-complete.json')
    frozen_inputs()
    for path, expected in setup['inputs'].items():
        if continuation is not None:
            expected = continuation['changes'].get(path, {}).get('new_sha256', expected)
        if sha(Path(path)) != expected:
            raise RuntimeError('Runner/profile/config changed since setup: ' + path)
    work, project, db = Path(setup['work']), Path(setup['work']) / 'project', Path(setup['db'])
    if setup['auth'] != 'existing-user':
        raise RuntimeError('Regenerate the profile for the reviewed existing-user authentication mode')
    if auth_topology(Path(setup['opencode']), work) != setup['auth_topology']:
        raise RuntimeError('Authentication/data topology changed after setup')
    env = client_environment(work)
    runtime = module('step14_runtime', RUNTIME)
    accounting = module('step14_account', HERE / 'account.py')
    baseline = gpu()
    for row in baseline['compute']:
        try:
            command = Path(f'/proc/{int(row[1])}/cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:
            continue
        if str(Path(setup['python']).parent / 'doc-atlas').encode() in command:
            raise RuntimeError('An installed step14 MCP already owns GPU memory; refusing another copy')
    save(out / ('continuation-started.json' if continuation else 'run-started.json'),
         dict(monotonic_ns=time.monotonic_ns(), gpu=baseline,
              manifest_sha256=sha(out / 'continuation-manifest.json') if continuation else None))
    completed = 2 if continuation else 0
    for task in load(HERE / 'tasks.json'):
        for arm in ('A', 'B', 'C'):
            if continuation is not None and [arm, task['id']] not in continuation['remaining']:
                continue
            case = out / arm / task['id']
            if corpus_hashes(project) != setup['source_hashes'] or sha(db) != setup['db_sha256']:
                raise RuntimeError('Corpus/index changed before session')
            before = gpu()
            if not gpu_restored(baseline, before, args.gpu_slack_mib):
                raise RuntimeError('New GPU process or memory appeared; refusing next session')
            save(case / 'started.json', dict(model=MODEL, monotonic_ns=time.monotonic_ns(), gpu=before))
            try:
                launched = runtime.launch_session(opencode=Path(setup['opencode']),
                    location=work / 'locations' / arm / task['id'], question=task['question'], env=env,
                    output=case / 'runtime', model=MODEL, agent='measure', timeout=900,
                    title=f'Step14 {arm} {task["id"]}',
                    owned_process_files=() if arm == 'C' else (case / 'mcp-process.json',),
                    fatal=case / 'fatal.json', capture=case / 'capture')
            finally:
                after = gpu()
                save(case / 'gpu-after.json', after)
                save(case / 'state-after.json', dict(sources=corpus_hashes(project), db_sha256=sha(db)))
            receipt = launched['receipt']
            evidence = accounting.summarize(case, arm, task['id'])
            save(case / 'accounting.json', evidence)
            if not gpu_restored(before, after, args.gpu_slack_mib):
                raise RuntimeError('GPU not released after owned cleanup; no further session')
            if corpus_hashes(project) != setup['source_hashes'] or sha(db) != setup['db_sha256']:
                raise RuntimeError('Corpus/index changed after session')
            if (not receipt['transport_pass'] or not receipt['cleanup']['no_live_owned_processes']
                    or (case / 'fatal.json').exists() or evidence['capture_errors'] or evidence['retries']
                    or not evidence['usage_coverage_complete'] or evidence['mcp_missing_responses']
                    or not evidence['provider_requests'] or evidence['session_ids_count'] != 1
                    or (arm == 'B' and evidence['host_preflight_verified'] is not True)):
                raise RuntimeError('Session/capture failed; raw preserved; automatic retry forbidden: ' + str(case))
            completed += 1
            print(arm, task['id'], 'captured; quality NOT graded', flush=True)
    save(out / 'run-complete.json', dict(sessions=completed, status='CAPTURED_NOT_QUALITY_GRADED'))


def main():
    os.umask(0o077)
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('setup', 'run'))
    parser.add_argument('--attempt', default='attempt-01')
    for name in ('python', 'assets', 'wheel', 'work', 'state', 'opencode'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--auth', choices=('existing-user',), default='existing-user')
    parser.add_argument('--gpu-slack-mib', type=int, default=128)
    args = parser.parse_args()
    if not args.attempt.startswith('attempt-') or Path(args.attempt).name != args.attempt:
        parser.error('attempt must be a new simple attempt-* directory name')
    if args.action == 'setup' and any(getattr(args, n) is None for n in ('python', 'assets', 'wheel', 'work', 'state', 'opencode')):
        parser.error('setup requires --python --assets --wheel --work --state --opencode')
    try:
        if args.action == 'setup':
            setup(args)
        else:
            run(args)
    except BaseException as exc:
        out = HERE / args.attempt
        if out.is_dir():
            failure = out / (args.action + '-exception.json')
            if not failure.exists():
                save(failure, dict(status='FAILED_NOT_RETRIED', exception_type=type(exc).__name__,
                    error=str(exc), boundary='Preserved partial work; inspect actual capture before counting operations'))
        raise


if __name__ == '__main__':
    main()
