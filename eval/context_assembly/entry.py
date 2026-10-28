"""All fixture/runtime processes share the hard 1.5 GB cgroup; no swap."""
import json
from pathlib import Path
import subprocess
import sys
import time

out = Path('/evidence')
out.mkdir(exist_ok=True)
root = Path('/sys/fs/cgroup')
def memory():
    return {k: (root / k).read_text().strip() for k in
            ('memory.max', 'memory.peak', 'memory.swap.max', 'memory.events')}
def save(name, value):
    (out / name).write_text(json.dumps(value, indent=2) + '\n')

rc = 1
started = time.monotonic()
try:
    mem = memory()
    assert 1_500_000_000 - 4096 < int(mem['memory.max']) <= 1_500_000_000
    assert mem['memory.swap.max'] == '0'
    save('CGROUP_START.json', mem)
    rc = subprocess.run([sys.executable, '-I', '/repo/eval/context_assembly/run.py',
        '--repo', '/repo', '--work', '/tmp/context-assembly-work', '--out', '/evidence/new20']).returncode
    if rc == 0:
        rc = subprocess.run([sys.executable, '-I', '/repo/eval/context_assembly/recorded.py',
            '--artifacts', '/recorded', '--out', '/evidence/recorded58']).returncode
finally:
    mem = memory()
    events = dict(line.split() for line in mem['memory.events'].splitlines())
    save('CGROUP_FINAL.json', {**mem, 'driver_exit': rc, 'seconds': time.monotonic()-started})
    if int(events.get('oom_kill', '0')) or int(events.get('oom', '0')):
        rc = 137
    if int(mem['memory.peak']) > int(mem['memory.max']):
        rc = 137
sys.exit(rc)
