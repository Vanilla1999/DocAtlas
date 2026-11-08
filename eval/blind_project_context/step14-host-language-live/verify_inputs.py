"""Offline immutable input integrity check; no imports from the product and no inference."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((HERE / 'manifest.json').read_text())
errors = []
for path, expected in manifest['files'].items():
    source = TREE / path
    if not source.is_file() or digest(source) != expected:
        errors.append(path)
tasks = json.loads((HERE / 'tasks.json').read_text())
if [task['id'] for task in tasks] != ['V-M1', 'V-M2', 'V-M3', 'V-M4']:
    errors.append('task IDs/order')
if sum(len(task['facts']) for task in tasks) != 19:
    errors.append('fact count')
if (HERE / 'tasks.json').read_bytes() != (HERE.parent / 'step12-live-comparison/tasks.json').read_bytes():
    errors.append('tasks not byte-identical')
if errors:
    raise SystemExit('FAIL: ' + ', '.join(errors))
print('PASS immutable input hashes; NOT a readiness or runtime check')
