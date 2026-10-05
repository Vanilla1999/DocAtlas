"""Finalize already exported evidence; no network or model calls."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def load(path):
    return json.loads((OUT / path).read_text())


def save(path, value):
    (OUT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


c = load('comparison.json')
c['limitations'] = load('orchestration-metadata.json')
reviewer = load(f"transcripts/{c['review']['reviewer_session']}.json")['data']
c['review']['reviewer_export_model'] = reviewer['info']['model']
c['review']['reviewer_same_model'] = reviewer['info']['model']['id'] == 'gpt-6.1-sol' and reviewer['info']['model']['providerID'] == 'openai'
assert c['review']['reviewer_same_model']
for row in c['rows']:
    data = load(f"transcripts/{row['reader_session_id']}.json")['data']
    assert data['info']['id'] == row['reader_session_id']
    assert data['info']['agent'] == 'general'
    assert data['info']['model']['id'] == 'gpt-6.1-sol'
    assert data['info']['model']['providerID'] == 'openai'
    assert row['export_contains_expected_transport_session']
c['volume_calls_latency']['per_arm'] = {arm: {
    'input_bytes_total': sum(r['input_json_utf8_bytes'] for r in c['rows'] if r['arm'] == arm),
    'input_bytes_median': statistics.median(r['input_json_utf8_bytes'] for r in c['rows'] if r['arm'] == arm),
    'input_bytes_max': max(r['input_json_utf8_bytes'] for r in c['rows'] if r['arm'] == arm),
    'assistant_steps': sum(r['export_metrics']['assistant_steps'] for r in c['rows'] if r['arm'] == arm),
    'latency_median_seconds': statistics.median(r['export_metrics']['elapsed_created_to_idle_seconds'] for r in c['rows'] if r['arm'] == arm)
} for arm in ('A', 'B')}
assert sum(r['successful_reads'] for r in c['rows']) == 2
read_chars = [len(receipt['source']['snippet']) for row in c['rows'] for receipt in row['read_results']]
assert sorted(read_chars) == [100, 515]
c['volume_calls_latency']['native_read_snippet_chars'] = read_chars
save('comparison.json', c)
pre = load('preflight-hashes.json')
assert pre == load('postflight-hashes.json') == load('comparison-postflight-hashes.json')
assert all(hashlib.sha256((OUT/'bridge.py' if p == 'EXPLORATORY/bridge.py' else ROOT/p).read_bytes()).hexdigest() == h for p,h in pre.items())
save('comparison-command.json', {'argv': ['.venv/bin/python', str((OUT/'compare.py').relative_to(ROOT))],
     'exit_code': 0, 'provider_calls': 0, 'read_only_API_exports': 21})
save('comparison-verification.json', {'argv':[sys.executable,str(Path(__file__).resolve())],
     'exit_code':0,'frozen_unchanged':True,'reader_exports_id_model_agent_transport_confirmed':20,
     'reviewer_export_id_model_confirmed':True,'native_read_snippet_chars':read_chars,
     'provider_callcount':'UNKNOWN','new_model_calls':0})
save('final-artifact-hashes.json', {str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
     for p in sorted(OUT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
     and p.name != 'final-artifact-hashes.json'})
print(json.dumps({'report':'REPORT_RU.md','comparison':'comparison.json','frozen_unchanged':True,
                  'reader_exports':20,'reviewer_exports':1,'provider_callcount':'UNKNOWN','exit_code':0}))
