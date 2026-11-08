"""Derive final metrics without changing raw evidence or filling missing measurements."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATTEMPT = HERE / 'attempt-02'


def load(path):
    return json.loads(path.read_text())


records = load(ATTEMPT / 'accounting-final.json')
verified = {(r['arm'], r['task']): r for r in load(HERE / 'provider-capture-verification.json')}
grades = {(r['arm'], r['task']): r for r in load(HERE / 'parent-semantic-review.json')['records']}
results = []
for row in records:
    arm, task = row['arm'], row['task']
    root = ATTEMPT / arm / task
    check = verified[arm, task]
    for key, original in [('input_tokens', 'input'), ('output_tokens', 'output'),
                          ('cached_tokens', 'cached'), ('uncached_tokens', 'uncached')]:
        assert check['usage'][key] == row['usage'][original], (arm, task, key)
    assert check['provider_requests'] == row['provider_requests']
    receipt_path = root / 'runtime/receipt.json'
    receipt = load(receipt_path) if receipt_path.exists() else None
    answer = receipt['answer'] if receipt else load(ATTEMPT / 'recovery-02/B-provider-completion.json')['answer']
    calls = row['model_tool_calls'].copy()
    if arm == 'B' and task == 'V-M4':
        # Inbound provider output, independently of incomplete CLI stdout.
        from verify_provider_capture import objects
        outputs = {}
        for line in (root / 'capture/events.jsonl').read_text().splitlines():
            event = json.loads(line)
            if event['type'] not in ('http.response', 'experimental.ws.receive'):
                continue
            for obj in objects(event['data']):
                if obj.get('object') == 'response' and obj.get('status') == 'completed':
                    outputs[obj['id']] = obj.get('output', [])
        calls = {}
        for output in outputs.values():
            for item in output:
                if item.get('type') == 'function_call':
                    calls[item['name']] = calls.get(item['name'], 0) + 1
        assert calls == {'docatlas_get_docs_context': 2}, calls
    grade = grades.get((arm, task))
    results.append(dict(arm=arm, task=task, usage=row['usage'], provider_requests=row['provider_requests'],
        seconds=receipt['seconds'] if receipt else None, model_tool_calls=calls,
        actual_mcp_calls=row['actual_mcp_calls'], qwen_pairs=row['qwen_pairs'],
        host_hint_binding_verified=row['host_hint_binding_verified'],
        host_timestamp_order_verified=row['host_timestamp_order_verified'],
        answer=answer, answer_source='runtime/receipt.json' if receipt else 'recovery-02/B-provider-completion.json + B-session-export.json',
        quality=({label: grade['grades'].count(label) for label in ('full','partial','missing','contradicted')} if grade else None),
        source_facts_found=len(grade['grades']) if grade else None,
        source_facts_delivered=len(grade['grades']) if grade else None,
        quality_evidence=['semantic-review-first-two.json','semantic-review-remaining.json','parent-semantic-review.json'] if grade else ['no-answer-review.json'],
        measurement_gap=('Bun/Python clock epochs differ; first-request hint is verified, chronological timestamp ordering unknown' if (arm,task)==('B','V-M1') else
                         'Coordinator killed by outer 120-second tool timeout; provider results complete, CLI incomplete, end-to-end seconds unknown' if (arm,task)==('B','V-M4') else None)))
totals = {}
for arm in 'ABC':
    rows = [r for r in results if r['arm'] == arm]
    totals[arm] = dict(usage={k:sum(r['usage'][k] for r in rows) for k in ('input','cached','uncached','output')},
        provider_requests=sum(r['provider_requests'] for r in rows), sessions=len(rows),
        source_facts_found=sum(r['source_facts_found'] or 0 for r in rows),
        source_facts_delivered=sum(r['source_facts_delivered'] or 0 for r in rows),
        quality={k:sum((r['quality'] or {}).get(k,0) for r in rows) for k in ('full','partial','missing','contradicted')},
        measured_session_seconds=sum(r['seconds'] or 0 for r in rows),
        timing_complete=all(r['seconds'] is not None for r in rows))
with (HERE / 'results.json').open('x') as stream:
    json.dump(dict(status='12_COMPLETED_WITH_MEASUREMENT_GAPS', sessions=results, totals=totals,
                  model_retries=0, orchestration_agent_usage_included=False), stream, ensure_ascii=False, indent=2)
print(json.dumps(totals, ensure_ascii=False, indent=2))
