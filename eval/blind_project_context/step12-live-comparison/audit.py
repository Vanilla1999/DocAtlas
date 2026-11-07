"""Offline source/usage audit after preserving all raw sessions."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'step10-multidoc-gate/projects/validation/meridian'


def main():
    records = json.loads((HERE / 'accounting.json').read_text())
    tasks = {t['id']: t for t in json.loads((HERE / 'tasks.json').read_text())}
    report = []
    for r in records:
        root = HERE / r['arm'] / r['case']
        events = [json.loads(line) for line in (root / 'raw.jsonl').read_text().splitlines()]
        captured = [json.loads(line) for line in (root / 'capture/events.jsonl').read_text().splitlines()]
        sends = [json.loads(e['data']) for e in captured if e['type'] == 'experimental.ws.send']
        assert sends and all(s['model'] == 'gpt-6.1-terra' and s['reasoning']['effort'] == 'low' for s in sends)
        original = tasks[r['case']]['question']
        assert sends[0]['input'][0]['content'][0]['text'] == original
        assert (root / 'question.txt').read_text() == original
        text = []; rows = []; errors = []; pairs = 0; calls = []
        for e in events:
            if e['type'] != 'tool_use':
                continue
            part = e['part']; state = part['state']; name = part['tool']; output = state.get('output','')
            calls.append(dict(tool=name, input=state.get('input'), status=state['status']))
            if name == 'docatlas_get_docs_context':
                assert state['input']['question'] == original
                packet = json.loads(output)
                sel = packet.get('source_selection',{})
                pairs += sel.get('model_pairs',0)
                if packet.get('reason_code') == 'scan_incomplete':
                    errors.append(packet)
                for row in packet.get('sources',[]):
                    source = (SOURCE / row['path']).read_text()
                    assert row['text'] in source
                    assert row['text'] == ''.join(source.splitlines(keepends=True)[row['line_start']-1:row['line_end']])
                    rows.append(row)
                    text.append(row['text'])
            elif name in ('read','grep'):
                text.append(output)
                if name == 'read':
                    path = Path(state['input']['path'])
                    assert path == Path('/tmp/opencode/step12-live-work/project') or path.parent == Path('/tmp/opencode/step12-live-work/project')
                    src = SOURCE / path.name
                    if src.exists():
                        lines = src.read_text().splitlines()
                        for n, line in re.findall(r'^(\d+): ?(.*)$', output, re.M):
                            assert lines[int(n)-1] == line
        delivered = [any(quote in t for t in text) for _, quote in tasks[r['case']]['facts']]
        system = schemas = rest = 0
        for record in r['provider_records']:
            usage = record['usage']; attr = usage['attribution']
            assert sum(v['input_tokens'] for group in attr.values() for v in group.values()) == usage['input_tokens']
            system += attr['request_fields'].get('instructions',{}).get('input_tokens',0)
            schemas += attr['request_fields'].get('tools',{}).get('input_tokens',0)
        rest = r['usage']['input'] - system - schemas
        step_usage = [e['part']['tokens'] for e in events if e['type']=='step_finish']
        assert sum(t['input'] + t['cache']['read'] for t in step_usage) == r['usage']['input']
        assert sum(t['output'] + t['reasoning'] for t in step_usage) == r['usage']['output']
        row = dict(arm=r['arm'], case=r['case'], delivered=delivered,
            delivery_count=sum(delivered), total_facts=len(delivered), checked_source_rows=len(rows),
            successful_qwen_pairs=pairs, errors=errors, calls=calls,
            provider_input_categories=dict(instructions=system, tool_schemas=schemas, question_tools_results_history=rest),
            usage=r['usage'], requests=r['requests_with_usage'],
            seconds=json.loads((root/'receipt.json').read_text())['seconds'])
        report.append(row)
    (HERE / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for arm in ('qwen-off','qwen-one-hop','files'):
        subset=[r for r in report if r['arm']==arm]
        print(arm, 'facts',sum(r['delivery_count'] for r in subset),'requests',sum(r['requests'] for r in subset),
            'seconds',round(sum(r['seconds'] for r in subset),2),'categories',
            {k:sum(r['provider_input_categories'][k] for r in subset) for k in subset[0]['provider_input_categories']})
    manifest = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for arm in ('qwen-off','qwen-one-hop','files') for p in (HERE/arm).rglob('*') if p.is_file()}
    (HERE / 'raw-manifest.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
