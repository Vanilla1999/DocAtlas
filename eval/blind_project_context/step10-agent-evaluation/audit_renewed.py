"""Offline renewed T01 evidence audit; no provider calls or automatic fact grading."""
import hashlib
import json
from pathlib import Path
import re
import yaml

from account_sessions import account

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = Path('/tmp/opencode/terra-step10-renewed')
BASE = Path('/tmp/opencode/terra-step10-prepared')
SOURCE = Path('/tmp/opencode/step8-corpora2/L0-0/project')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    renewed = account(RUN)['sessions'][0]
    baseline = account(BASE, arm_filter='file-current', allowed_sessions={('L0', 'T01-ru')})['sessions'][0]
    old = next(s for s in load(HERE / 'baseline-valid.json')['sessions']
               if s['corpus'] == 'L0' and s['case'] == 'T01-ru')
    assert baseline['artifact_hashes'] == old['artifact_hashes']
    assert renewed['model'] == baseline['model']
    plans = [load(p) for p in (RUN / 'minimal-context-plan.json', BASE / 'file-current-plan.json')]
    questions = [next(c for c in p['cases'] if c['id'] == 'T01-ru') for p in plans]
    assert questions[0] == questions[1]
    assert plans[0]['model'] == plans[1]['model'] == 'openai/gpt-6.1-terra#low'
    assert plans[0]['steps'] == plans[1]['steps'] is None
    frozen = load(HERE / 'baseline-valid.json')['frozen_artifact_sha256']
    assert all(digest(ROOT / name) == value for name, value in frozen.items())
    observed = {}
    for tool in baseline['tool_trace']:
        if tool['tool'] != 'read':
            continue
        path = Path(tool['state']['input']['path'])
        lines = path.read_text().splitlines()
        numbered = re.findall(r'^(\d+): (.*)$', tool['state']['output'], re.M)
        assert numbered and all(lines[int(n)-1] == text for n, text in numbered)
        observed[str(path.relative_to(SOURCE))] = {'sha256': digest(path), 'matched_historical_lines': len(numbered)}
    call = next(t for t in renewed['tool_trace'] if t['tool'] == 'docatlas_get_docs_context')
    packet = json.loads(call['state']['output'])
    rows = [dict(zip(packet['source_columns'], row)) for row in packet['sources']]
    catalog = {d['path']: d for d in yaml.safe_load((SOURCE / 'docatlas.project-docs.yaml').read_text())['documents']}
    for row in rows:
        path = (SOURCE / row['path']).resolve()
        assert path.is_relative_to(SOURCE.resolve())
        assert row['scope'] == catalog[row['path']]['scope']
        raw = path.read_text()
        assert ''.join(raw.splitlines(keepends=True)[row['line_start']-1:row['line_end']]) == row['text']
        material = {'path': row['path'], 'section': row['section'], 'content': row['text'], 'snippet': row['text'], 'version': None}
        canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(canonical).hexdigest() == row['content_sha256']
    citations = re.findall(r'\]\(([^)]+)#L(\d+)-L(\d+)\) \((ev-[a-f0-9]+)\)', renewed['final_answer'])
    assert len(citations) == 6
    for path, start, end, ref in citations:
        assert any(r['ref'] == ref and r['path'] == path and r['line_start'] <= int(start)
                   and r['line_end'] >= int(end) for r in rows)
    result = {
        'question': questions[0], 'mcp_input': call['state']['input'],
        'question_exactly_preserved': call['state']['input']['question'] == questions[0]['question'],
        'model': renewed['model'], 'baseline_artifacts_unchanged': True,
        'frozen_artifacts_unchanged': frozen, 'historical_read_sources': observed,
        'source_rows_text_span_scope_hash_verified': len(rows), 'final_citation_refs_verified': len(citations),
        'source_selection': packet['source_selection'], 'context_quality': packet['context_quality'],
        'candidate_usage': renewed['usage'], 'baseline_usage': baseline['usage'],
        'input_with_cache_ratio': renewed['usage']['input_with_cache'] / baseline['usage']['input_with_cache'],
        'candidate_seconds': renewed['receipt']['seconds'], 'baseline_seconds': baseline['receipt']['seconds'],
        'limitations': ['Historical complete corpus hash manifest unavailable: equality established for the baseline actually read documents, frozen annotations, model/settings and corpus path, not retrospective full-store immutability.',
                       'Arm-specific prompts/tools differ intentionally. Single-case observational comparison, not a causal adapter benchmark.',
                       'Exact source/hash/citation checks do not grade claim entailment; manual grades are recorded separately.',
                       'No provider HTTP payload capture; usage is reconciled step_finish and persisted session telemetry.'],
    }
    (HERE / 'renewed-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
