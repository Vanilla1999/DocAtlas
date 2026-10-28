"""Finish evaluation of 100 completed real MCP calls, not a repeat benchmark.

The original cross-process-order assertion was invalid: A20-14 grouped-table
received a different upstream order. All 100 outputs preserve their OWN input
order, verified against pre-assembly selected_evidence_ids. Keep original failure.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

out = Path('/evidence')
out.mkdir(exist_ok=True)
root = Path('/sys/fs/cgroup')
def mem():
    return {k:(root/k).read_text().strip() for k in ('memory.max','memory.peak','memory.swap.max','memory.events')}
def save(name, value):
    (out/name).write_text(json.dumps(value, indent=2)+'\n')
rc = 1
start = time.monotonic()
try:
    before = mem()
    assert 1_500_000_000-4096 < int(before['memory.max']) <= 1_500_000_000 and before['memory.swap.max']=='0'
    archive = Path('/prior/runtime.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == '4f80c9b00892442b237c6bb180f9261ea76c4ee3b41242451a11388da87fdc79'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            target = (out/'original'/name).resolve()
            assert target.is_relative_to((out/'original').resolve())
            if name.endswith('/'):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
    original_mem = json.loads((out/'original/CGROUP_FINAL.json').read_text())
    events = dict(line.split() for line in original_mem['memory.events'].splitlines())
    assert int(events['oom']) == int(events['oom_kill']) == 0
    assert int(original_mem['memory.peak']) <= int(original_mem['memory.max']) <= 1500000000
    assert original_mem['driver_exit'] == 1  # the disclosed comparison assertion, not OOM
    records = []
    log = Path('/prior/runtime.log').read_text(encoding='utf-8-sig')
    for line in log.splitlines():
        marker = line.find('{"id": "A20-')
        if marker < 0:
            continue
        row = json.loads(line[marker:])
        if 'seconds' in row and 'facts' in row and 'policy' in row:
            records.append(row)
    assert len(records) == 100 and len({(r['policy'],r['id']) for r in records}) == 100
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    for r in records:
        wire = json.loads((out/'original/new20'/r['policy']/r['family']/(r['id']+'-reply.json')).read_text())
        assert projection_token_count(wire['content'][0]['text'].encode()) == r['tokens']
        assert bool(wire.get('isError')) == r['error']
    save('original/new20/RECORDS.json', records)
    save('PROVENANCE.json', {'runtime_run':40773895590, 'runtime_job':123118016158,
         'runtime_artifact_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
         'runtime_log_sha256':hashlib.sha256(Path('/prior/runtime.log').read_bytes()).hexdigest(),
         'original_failure':'cross-process source order assertion on A20-14 grouped-table',
         'new_inference_calls':0, 'runtime_calls_reused':105, 'product_and_gold_unchanged':True})
    rc = subprocess.run([sys.executable,'-I','/repo/eval/context_assembly/run.py','--resume-recorded',
          '--repo','/repo','--work','/tmp/unused','--out','/evidence/original/new20']).returncode
    if rc == 0:
        rc = subprocess.run([sys.executable,'-I','/repo/eval/context_assembly/recorded.py',
                             '--artifacts','/recorded','--out','/evidence/recorded58']).returncode
finally:
    after = mem()
    save('AUDIT_CGROUP.json', {**after,'driver_exit':rc,'seconds':time.monotonic()-start})
    events = dict(line.split() for line in after['memory.events'].splitlines())
    if int(events.get('oom','0')) or int(events.get('oom_kill','0')) or int(after['memory.peak'])>int(after['memory.max']):
        rc=137
sys.exit(rc)
