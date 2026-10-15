"""Offline correction: validate saved DTOs against raw sources, without product calls.

The run exported committed content hashes but not generation_sources metadata.
The full historical _prepare audit therefore cannot be used on that export.
"""
import importlib.util
import json
from pathlib import Path
import hashlib

REPO = Path('/tmp/opencode/pr211-no-terminal-budget')
CORPUS = REPO/'eval/prepared_model_comparison40'
OUT = REPO/'reports/pr211-no-terminal-budget-20261015'
spec = importlib.util.spec_from_file_location('offline', CORPUS/'evaluate.py')
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
gold = json.loads((CORPUS/'gold_spans.json').read_text())['cases']
if isinstance(gold, list):
    gold = {c['id']: c for c in gold}
cases = {c['id']: c for c in json.loads((CORPUS/'questions.json').read_text())['cases']}
results = json.loads((OUT/'CALLS.json').read_text())
for result in results:
    case = cases[result['case_id']]
    prep = json.loads((OUT/'preparation'/(case['project_group']+'.json')).read_text())
    sources = {}
    hashes = {s['path']: s['content_sha256'] for s in prep['snapshot_sources']}
    for relative, digest in hashes.items():
        raw = (CORPUS/'sources'/case['project_group']/relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        content = raw.decode()
        offsets = [0]
        for line in content.splitlines(keepends=True):
            offsets.append(offsets[-1]+len(line))
        sources[relative] = {'content': content, 'raw': raw, 'line_offsets': offsets, 'sha256': digest, 'errors': []}
    prepared = {'root': prep['root'], 'sources': sources}
    dto = json.loads((OUT/(case['id']+'-dto.json')).read_bytes())
    verified, intervals, errors = ev._source_rows(dto, prepared)
    oracle = ev._gold(case, gold[case['id']], prepared, intervals)
    parts = [p for c in oracle['claims'] for w in c['witness_sets'] for p in w['parts']]
    result.update(coverage=[{'covered': p['covered_characters'], 'expected': p['expected_characters']} for p in parts], source_errors=errors, oracle_errors=oracle['errors'], oracle_pass=oracle['all_documented_claims_covered'] and not errors and not oracle['errors'])
    assessment = {'boundary': 'saved public DTO vs frozen raw sources and committed content hashes; full snapshot metadata audit NOT MEASURED', 'oracle': oracle, 'verified_sources': verified, 'source_errors': errors}
    (OUT/(case['id']+'-raw-assessment.json')).write_text(json.dumps(assessment, ensure_ascii=False, indent=2)+'\n')
(OUT/'RAW_RESULTS.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(results, ensure_ascii=False, indent=2))
