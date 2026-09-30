"""Actual kernel/process IO assertions, not a JSON gold-key check."""
import json
from pathlib import Path
import socket
import sys

import pytest

from experiments.retrieval_ablation.isolation import run_isolated


def layout(tmp_path):
    app, public, output = [tmp_path / name for name in ('app', 'public', 'output')]
    for p in (app, public, output):
        p.mkdir()
    (public / 'source.md').write_text('Public source bytes.')
    return app, public, output


def test_real_worker_cannot_read_private_labels_even_by_absolute_path(tmp_path):
    app, public, output = layout(tmp_path)
    gold = tmp_path / 'private-labels.json'
    gold.write_text('THE_HIDDEN_ANSWER')
    code = f'''from pathlib import Path
try:
    Path({str(gold)!r}).read_text()
except (FileNotFoundError, PermissionError):
    pass
else:
    raise AssertionError("worker can read gold")
'''
    result = run_isolated(code, app=app, public=public, output=output)
    assert result.returncode == 0, result.stderr


def test_public_inputs_are_readonly_and_only_output_is_writable(tmp_path):
    app, public, output = layout(tmp_path)
    result = run_isolated('''from pathlib import Path
assert Path('/public/source.md').read_text() == 'Public source bytes.'
try:
    Path('/public/source.md').write_text('tampered')
except OSError:
    pass
else:
    raise AssertionError('input is writable')
Path('/output/ok').write_text('executed')
''', app=app, public=public, output=output)
    assert result.returncode == 0, result.stderr
    assert (public / 'source.md').read_text() == 'Public source bytes.'
    assert (output / 'ok').read_text() == 'executed'


def test_worker_has_no_host_loopback_network_or_host_proc(tmp_path):
    app, public, output = layout(tmp_path)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = run_isolated(f'''import socket, pathlib
assert not pathlib.Path('/proc/1/root').exists()
s = socket.socket()
s.settimeout(0.2)
try:
    s.connect(('127.0.0.1', {port}))
except OSError:
    pass
else:
    raise AssertionError('host loopback is reachable')
''', app=app, public=public, output=output)
    assert result.returncode == 0, result.stderr


def test_worker_cannot_remount_readonly_public_tree(tmp_path):
    app, public, output = layout(tmp_path)
    result = run_isolated('''import subprocess
p = subprocess.run(['/usr/bin/mount', '-o', 'remount,rw', '/public'], capture_output=True)
assert p.returncode != 0
''', app=app, public=public, output=output)
    assert result.returncode == 0, result.stderr


def test_host_credentials_are_not_inherited(tmp_path, monkeypatch):
    app, public, output = layout(tmp_path)
    monkeypatch.setenv('TEST_PRIVATE_TOKEN', 'must-not-reach-worker')
    result = run_isolated("import os; assert 'TEST_PRIVATE_TOKEN' not in os.environ",
                          app=app, public=public, output=output)
    assert result.returncode == 0, result.stderr


def test_worker_staging_excludes_review_cases_and_git(tmp_path):
    from experiments.retrieval_ablation.run import stage_worker
    app = tmp_path / 'app'
    digest = stage_worker(app)
    assert len(digest) == 64
    assert (app / 'docmancer/docs/data/o200k_base.tiktoken.gz').is_file()
    assert not (app / '.git').exists()
    assert not (app / 'experiments/retrieval_ablation/review.py').exists()
    assert not (app / 'eval/evidence_quality_v2/cases.json').exists()
    assert not (app / 'eval/evidence_quality_v2/sources').exists()
    assert not (app / 'tests').exists()
    assert not (app / 'eval/evidence_quality_v2/semantic.py').exists()
    assert not (app / 'eval/evidence_quality_v2/run.py').exists()
    assert not (app / 'experiments/language_aware_context/pilot_review.py').exists()


def test_real_sqlite_and_packet_modules_execute_inside_namespace(tmp_path):
    from experiments.retrieval_ablation.run import stage_worker
    app, public, output = [tmp_path / name for name in ('app', 'public', 'output')]
    stage_worker(app)
    public.mkdir()
    output.mkdir()
    code = '''import json, hashlib
from pathlib import Path
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from experiments.retrieval_ablation.adapters import native_diagnostic
text = '# Retry\\n\\nThe retry budget is three attempts.\\n'
filters = {'project_identity':'test','project_path':'/tmp/project','source_class':'project_doc','doc_scope':'project'}
metadata = {**filters, 'source_path':'retry.md','project_doc_path':'retry.md',
            'project_doc_content_hash':hashlib.sha256(text.encode()).hexdigest(),
            'authority':'source_of_truth','format':'markdown'}
store = SQLiteStore(Path('/tmp/index.db'))
store.add_documents([Document(source='retry.md',content=text,metadata=metadata)],recreate=True)
r = native_diagnostic(store,['What is the retry budget?'],filters=filters,sources={'retry.md':text})
assert r['model_visible_packet'].get('sources'), r
assert r['packet_audit_errors'] == []
Path('/output/result.json').write_text(json.dumps(r))
'''
    result = run_isolated(code, app=app, public=public, output=output)
    assert result.returncode == 0, result.stderr
    assert json.loads((output / 'result.json').read_text())['packet_status'] == 'VALIDATED_PROJECT_PACKET'


@pytest.mark.parametrize('arm', ['P', 'A'])
def test_actual_fixture_handler_executes_without_any_gold_files(tmp_path, arm):
    from experiments.retrieval_ablation.run import stage_worker
    app, public, output = [tmp_path / name for name in ('app', 'public', 'output')]
    stage_worker(app)
    public.mkdir()
    output.mkdir()
    (public / 'retry.md').write_text('# Retry\n\nThe retry budget is three attempts. Do not retry cancellation.\n')
    code = f'''import hashlib, json
from pathlib import Path
from experiments.retrieval_ablation.run import _execute_arm
p=Path('/public')
assert not Path('/app/eval/project_context_quality/cases.json').exists()
r=_execute_arm(p, {{'schema_version':1, 'sources':[{{'path':'retry.md', 'sha256':hashlib.sha256((p/'retry.md').read_bytes()).hexdigest()}}]}},
    {{'question':'What is the retry budget?'}}, {{'max_sections_per_source':2,'raw_hits':40,'unique_candidates':20}}, {arm!r})
assert r['execution_status'] == 'EXECUTED', r
assert r.get('packet_audit_errors', r.get('audit_errors')) == [], r
if {arm!r} == 'A':
    assert r['packet_status'] == 'VALIDATED_PROJECT_PACKET'
    assert r['model_visible_packet'].get('sources'), r
Path('/output/result.json').write_text(json.dumps(r, default=lambda x: sorted(x)))
'''
    completed = run_isolated(code, app=app, public=public, output=output)
    assert completed.returncode == 0, completed.stderr
