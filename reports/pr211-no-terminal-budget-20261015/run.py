import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/tmp/opencode/pr211-no-budget-runtime')
REPO = Path('/tmp/opencode/pr211-no-terminal-budget')
CORPUS = REPO / 'eval/prepared_model_comparison40'
OUT = REPO / 'reports/pr211-no-terminal-budget-20261015'
sys.path.insert(0, str(BASE / 'site'))
# /tmp/opencode is group-writable (0775); the real storage policy rejects it.
# Private TemporaryDirectory homes under sticky /tmp satisfy that policy.
os.environ['TMPDIR'] = '/tmp'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')

runtime = load('fixture_runtime', REPO / 'eval/evidence_quality_v2/runtime.py')
helpers = load('run_helpers', CORPUS / 'run.py')
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.docs.application.projection_tokenizer import projection_token_count
assert Path(context_tools.__file__).is_relative_to(BASE / 'site')
assert Path(context_tools.__file__).read_bytes() == (REPO / 'docmancer/docs/interfaces/mcp/context_tools.py').read_bytes()
OUT.mkdir(parents=True, exist_ok=False)
cases = [c for c in json.loads((CORPUS / 'questions.json').read_text())['cases'] if c['id'] in {'V40-P03', 'V40-E01'}]
families = {f['id']: f for f in json.loads((CORPUS / 'source_plan.json').read_text())['families']}
frozen = {str(p.relative_to(REPO)): helpers.sha(p.read_bytes()) for p in CORPUS.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
save(OUT / 'MANIFEST.json', {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(), 'installed_module': context_tools.__file__, 'wheel_sha256': helpers.sha(next((BASE/'wheels').glob('*.whl')).read_bytes()), 'context_tools_sha256': helpers.sha(Path(context_tools.__file__).read_bytes()), 'boundary': 'installed wheel; in-process public MCP dispatcher; real isolated SQLite; current local default without experiment flags', 'cases': cases, 'frozen_inputs': frozen, 'preparations_planned': 2, 'context_calls_planned': 2, 'model_calls': 0})
(OUT / 'product.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', 'docmancer/docs/interfaces/mcp/context_tools.py'], cwd=REPO))
results = []
for case in cases:
    group = case['project_group']
    root = BASE / 'projects' / group
    documents = {p: (CORPUS/'sources'/group/p).read_text() for p in families[group]['paths']}
    runtime.write_project(root, documents)
    print('PREPARE ' + case['id'], flush=True)
    with runtime.isolated_service(BASE / 'state' / group) as (service, config):
        with helpers.time_limit(180):
            inventory = runtime.index_project(service, config, root)
        # Raw committed source verification; prepared-parent experiments are off.
        import sqlite3
        with sqlite3.connect(inventory['storage_path']) as db:
            snapshots = [{'path': str(Path(source).relative_to(root)), 'content_sha256': helpers.sha(content.encode())} for source, content in db.execute('SELECT source, content FROM generation_sources WHERE generation_id=?', (inventory['generation_id'],))]
        assert {s['path']: s['content_sha256'] for s in snapshots} == {p: helpers.sha(t.encode()) for p,t in documents.items()}
        save(OUT/'preparation'/(group+'.json'), {'root': str(root), 'inventory': inventory, 'snapshot_sources': snapshots})
        before_db, before_files = helpers.logical_state(inventory), helpers.source_state(root)
        args = {'question': case['question'], 'project_path': str(root), 'scope': 'project'}
        save(OUT/(case['id']+'-request.json'), args)
        start = time.perf_counter()
        with helpers.time_limit(90):
            payload = call_docs_tool_payload('get_docs_context', args, service)
        elapsed = time.perf_counter() - start
        wire = json.dumps(payload, ensure_ascii=False).encode()
        (OUT/(case['id']+'-dto.json')).write_bytes(wire)
        result = {'case_id': case['id'], 'seconds': elapsed, 'kind': payload.get('kind'), 'status': payload.get('status'), 'reason_code': payload.get('reason_code'), 'sources': len(payload.get('sources') or []), 'wire_bytes': len(wire), 'codec_tokens': projection_token_count(wire), 'database_unchanged': helpers.logical_state(inventory) == before_db, 'project_files_unchanged': helpers.source_state(root) == before_files}
        results.append(result)
        save(OUT/'CALLS.json', results)
        print(json.dumps(result), flush=True)
        assert result['database_unchanged'] and result['project_files_unchanged']

assert all(helpers.sha((REPO/p).read_bytes()) == digest for p,digest in frozen.items())
print('Both calls complete; offline assessment runs separately', flush=True)
