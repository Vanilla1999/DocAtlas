"""Replay frozen wires only; no service calls, retrieval or network access."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlparse
import re

from eval.evidence_quality_v2.semantic import assess_context
from eval.evidence_quality_v2.grounded import extract_visible_sources
from eval.evidence_quality_v2.revised_gold import revised_case
from eval.evidence_quality_v2.run import load_protocol, registry_for, documents_for

REPO = Path(__file__).resolve().parents[4]
BASELINE = '5672a16c'


def old_module(path):
    code = subprocess.check_output(['git', 'show', f'{BASELINE}:{path}'], cwd=REPO, text=True)
    namespace = {'__name__': 'step05_baseline', '__file__': str(REPO / path)}
    exec(compile(code, path, 'exec'), namespace)
    return namespace


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    old = old_module('eval/evidence_quality_v2/semantic.py')['assess_context']
    old_mapping = old_module('eval/evidence_quality_v2/grounded.py')['extract_visible_sources']
    _, cases, manifest = load_protocol()
    raw = REPO / 'roadmap/search-quality-2026-10-01/audit/raw'
    rows, hashes = [], {}
    for case in cases:
        project = case['project_group']
        registry = registry_for(project, manifest)
        path = raw / 'external80/native' / f'{case["id"]}.json'
        if path.exists():
            wire = json.loads(path.read_text())['wire']
            payload = wire.get('structuredContent') or json.loads(wire['content'][0]['text'])
            rows.append({'system': 'docatlas', 'id': case['id'],
                'original': old(case, payload, registry),
                'revised': assess_context(revised_case(case), payload, registry)})
            hashes[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for limit in (1, 3, 5):
            path = raw / 'grounded/native' / str(limit) / f'{case["id"]}.json'
            if not path.exists():
                continue
            wire = json.loads(path.read_text())['wire']
            text = '\n'.join(block['text'] for block in wire['content'] if block['type'] == 'text')
            urls = re.findall(r'(?m)^Result \d+: (file://[^\n]+)', text)
            if not urls:
                raise ValueError('No frozen result paths: ' + str(path))
            relative = next(row['path'] for row in manifest['sources']
                            if row['project'] == project and unquote(urlparse(urls[0]).path).endswith('/' + row['path']))
            root = Path(unquote(urlparse(urls[0]).path))
            for _ in Path(relative).parts:
                root = root.parent
            documents = documents_for(project, manifest)
            before, old_binding = old_mapping(text, root, documents)
            after, binding = extract_visible_sources(text, root, documents)
            rows.append({'system': f'grounded-{limit}', 'id': case['id'],
                'original': old(case, {'sources': before}, registry),
                'revised': assess_context(revised_case(case), {'sources': after}, registry),
                'original_binding': old_binding, 'revised_binding': binding})
            hashes[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {}
    for system in sorted({row['system'] for row in rows}):
        group = [row for row in rows if row['system'] == system]
        summary[system] = {key: dict(Counter(row[key]['context_sufficiency'] for row in group))
                           for key in ('original', 'revised')}
        summary[system]['changed_cases'] = [row['id'] for row in group
            if row['original']['context_sufficiency'] != row['revised']['context_sufficiency']]
        summary[system]['review_queue_cases'] = {key: sum(bool(row[key]['review_queue']) for row in group)
                                                for key in ('original', 'revised')}
    for name, value in [('rows.json', rows), ('summary.json', summary), ('provenance.json', {
        'baseline': BASELINE, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        'raw_sha256': hashes, 'retrieval_calls': 0,
        'gold_revision': 'Only uv-06 example removed via explicit revised_case overlay; frozen cases unchanged',
        'scope': 'Semantic support and formatting mapping; not answer correctness or a citation-integrity success gate',
    })]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output.resolve())
