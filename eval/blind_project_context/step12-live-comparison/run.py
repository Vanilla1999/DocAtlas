"""One explicitly authorized 12-session live diagnostic. Never reruns a session."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
WORK = Path('/tmp/opencode/step12-live-work')
PYTHON = Path('/tmp/opencode/step12-qwen-env/bin/python')
CLI = PYTHON.parent / 'doc-atlas'
MODEL = 'openai/gpt-6.1-terra#low'
POLICY = HERE.parent / 'step10-qwen-validation/provenance/original-policy.json'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api(*args):
    result = subprocess.run(['opencode', 'api', *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def setup():
    import yaml
    from docmancer.docs.application import context_evidence_scoring as scorer
    import torch
    import importlib.metadata
    scorer.verify_assets('/tmp/opencode/step12-qwen-assets')
    runtime = dict(torch=torch.__version__, cuda=torch.version.cuda,
        **{name: importlib.metadata.version(name) for name in ('transformers', 'tokenizers', 'safetensors')},
        capability=list(torch.cuda.get_device_capability()), dtype='bfloat16', attention='sdpa', batch=1)
    assert runtime == scorer.RUNTIME, runtime
    save(HERE / 'runtime.json', runtime)
    WORK.mkdir(exist_ok=False)
    project = WORK / 'project'
    project.mkdir()
    data = HERE.parent / 'step10-multidoc-gate'
    descriptor = next(p for p in json.loads((data / 'projects.json').read_text()) if p['id'] == 'meridian')
    for name in descriptor['project_documents']:
        (project / name).write_bytes((data / descriptor['root'] / name).read_bytes())
    (project / 'AGENTS.md').write_text('This documentation fixture is read-only. Never change its source documents.\n')
    catalog = {'schema_version': 1, 'code_files': [],
        'documentation_languages': {p: ['en'] for p in descriptor['project_documents']},
        'documents': [dict(path=p, role='other', scope='project', authority='source_of_truth',
            status='active', impact='track', description='Documentation source') for p in descriptor['project_documents']]}
    (project / 'docatlas.project-docs.yaml').write_text(yaml.safe_dump(catalog, sort_keys=False))
    save(HERE / 'sources.json', {p.name: sha(p) for p in project.iterdir()})
    state = Path.home() / '.local/share/docatlas-step12-live-state'
    state.mkdir(mode=0o700, exist_ok=False)
    env = dict(DOCATLAS_HOME=str(state), DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='0',
        DOCATLAS_CONTEXT_COMPRESSION='off', ORT_DISABLE_TELEMETRY='1')
    for key in list(os.environ):
        if key.startswith('DOCATLAS_'):
            del os.environ[key]
    os.environ.update(env)
    from docmancer.mcp._docs_server_part01 import create_local_mcp_service
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog
    service = create_local_mcp_service()
    storage = service.member_storage_policy
    cat = read_project_docs_catalog(project)
    exists = storage.validate(project, service.config.index.db_path)
    result = call_docs_tool_payload('prepare_docs', dict(action='sync_project_docs', project_path=str(project),
        mutation=dict(operation='sync_project_docs', confirm=True, storage_path=str(storage.db_path),
            expected_generation_id=storage.generation() if exists else None,
            catalog_sha256=sha(project / 'docatlas.project-docs.yaml'),
            documents=[dict(path=r.path, content_sha256=sha(project / r.path), catalog_entry_hash=catalog_entry_hash(r)) for r in cat.entries])), service)
    save(HERE / 'preparation.json', result)
    assert result.get('status') == 'success', result
    profile_path = TREE / 'integrations/opencode-v2-compact/documentation_profile.py'
    spec = importlib.util.spec_from_file_location('profile_builder', profile_path)
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    tasks = [t for t in json.loads((data / 'tasks.json').read_text()) if t['id'] in ('V-M1','V-M2','V-M3','V-M4')]
    save(HERE / 'tasks.json', tasks)
    for arm in ('qwen-off', 'qwen-one-hop', 'files'):
        for task in tasks:
            location = WORK / arm / task['id']
            location.mkdir(parents=True)
            out = HERE / arm / task['id']
            out.mkdir(parents=True)
            selected = dict(env)
            if arm != 'files':
                selected.update(DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT='1',
                    DOCATLAS_MINIMAL_CONTEXT_RECIPE=scorer.RECIPE,
                    DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH='/tmp/opencode/step12-qwen-assets',
                    DOCATLAS_MINIMAL_CONTEXT_POLICY=str(POLICY),
                    DOCATLAS_CONTEXT_LINKS='one-hop-v1' if arm == 'qwen-one-hop' else 'off')
            config, receipt = profile.build_profile(project_root=project, workspace=location,
                backend='files' if arm == 'files' else 'mcp', executable=CLI, python=PYTHON,
                server_environment=selected, agent_name='measure', model=MODEL, frozen=True, max_steps=12)
            config['plugins'].append(dict(package=str(HERE / 'observer'), options=dict(output=str(out / 'capture'))))
            save(location / 'opencode.json', config)
            save(out / 'config.json', config)
            save(out / 'profile.json', receipt)
            (out / 'question.txt').write_text(task['question'])
    save(HERE / 'setup-complete.json', dict(model=MODEL, sessions=12, preparation_calls=1, inference_calls=0))


def run():
    assert (HERE / 'setup-complete.json').exists()
    tasks = json.loads((HERE / 'tasks.json').read_text())
    before = json.loads((HERE / 'sources.json').read_text())
    for task in tasks:
        for arm in ('qwen-off', 'qwen-one-hop', 'files'):
            out = HERE / arm / task['id']
            if (out / 'started.json').exists():
                raise RuntimeError('Refusing automatic rerun: ' + str(out))
            location = WORK / arm / task['id']
            created = api('post', '/api/session', '--data', json.dumps(dict(location=dict(directory=str(location)), title=f'Step12 {arm} {task["id"]}')))
            session = created['data']['id']
            save(out / 'started.json', dict(session=session, model=MODEL))
            start = time.monotonic()
            with (out / 'raw.jsonl').open('x') as stdout, (out / 'stderr.log').open('x') as stderr:
                try:
                    result = subprocess.run(['opencode', 'run', '--session', session, '--model', MODEL,
                        '--agent', 'measure', '--format', 'json'], input=task['question'], text=True,
                        cwd=location, stdout=stdout, stderr=stderr, timeout=900)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    api('post', f'/api/session/{session}/interrupt', '--data', '{}')
                    code = None
            save(out / 'session.json', api('get', f'/api/session/{session}'))
            save(out / 'receipt.json', dict(session=session, exit=code, seconds=time.monotonic()-start))
            assert {p.name: sha(p) for p in (WORK / 'project').iterdir()} == before
            events = [json.loads(line) for line in (out / 'raw.jsonl').read_text().splitlines() if line.strip()]
            assert code == 0 and not any(e.get('type') == 'error' for e in events), str(out)
            print(arm, task['id'], 'completed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('setup', 'run'))
    args = parser.parse_args()
    setup() if args.action == 'setup' else run()
