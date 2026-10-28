"""Replay 58 immutable real MCP responses; independent layout/source comparison."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

from docmancer.docs.application.context_assembly import assemble_context, render_layouts
from docmancer.docs.application.standalone_text_view import encode_standalone_text
from docmancer.docs.application.projection_tokenizer import projection_token_count as count

spec = importlib.util.spec_from_file_location('assembly_eval_driver', Path(__file__).with_name('run.py'))
eval_driver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = eval_driver
spec.loader.exec_module(eval_driver)


def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def run(root, out):
    os.environ['DOCATLAS_CONTEXT_ASSEMBLY'] = 'literal'
    out.mkdir(parents=True, exist_ok=True)
    result = {'cases': [], 'errors': 0, 'source_records': 0, 'paid_calls': 0, 'provider_usage': None}
    for suite, n in (('v40', 40), ('pilot', 10), ('fresh', 8)):
        paths = sorted((root / suite).rglob('*-reply.json'))
        assert len(paths) == n, (suite, len(paths))
        for path in paths:
            reply = json.loads(path.read_text())
            assert not reply.get('structuredContent') and len(reply['content']) == 1
            old_text = reply['content'][0]['text']
            packet = json.loads(old_text)
            baseline = encode_standalone_text(packet)
            if baseline is None:
                result['errors'] += 1
                assert all(assemble_context(old_text, policy=p) == old_text for p in eval_driver.POLICIES)
                continue
            base = json.loads(baseline)
            variants = render_layouts(baseline)
            result['source_records'] += len(base['sources'])
            costs = {}
            for p in eval_driver.POLICIES:
                text = assemble_context(baseline, policy=p)
                assert canonical(eval_driver.literal(json.loads(text))) == canonical(base)
                costs[p] = count(text.encode())
                eval_driver.save(out / 'replies' / suite / (path.stem+'-'+p+'.json'), json.loads(text))
            assert costs['adaptive'] == min(costs.values())
            chosen = assemble_context(baseline, policy='adaptive')
            winner = next(p for p, text in variants.items() if text == chosen)
            result['cases'].append({'id': path.stem, 'suite': suite, 'costs': costs, 'winner': winner,
                                    'exact_roundtrip': True, 'rows': len(base['sources'])})
    assert len(result['cases']) == 57 and result['errors'] == 1 and result['source_records'] == 373
    result['totals'] = {p: sum(c['costs'][p] for c in result['cases']) for p in eval_driver.POLICIES}
    assert result['totals']['literal'] == 62560, 'current main baseline changed'
    result['winner_counts'] = {p: sum(c['winner'] == p for c in result['cases']) for p in eval_driver.POLICIES[:-1]}
    result['note'] = 'Replay/projection, not new inference or a paid OpenCode conversation. All source fields and values preserved.'
    eval_driver.save(out / 'RESULT.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.artifacts, a.out)
