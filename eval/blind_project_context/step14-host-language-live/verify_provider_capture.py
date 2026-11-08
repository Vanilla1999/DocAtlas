"""Independent offline reconciliation of inbound provider usage and request identity."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = json.loads((HERE / 'tasks.json').read_text())


def objects(raw):
    if isinstance(raw, dict):
        yield raw
        for value in raw.values():
            yield from objects(value)
    elif isinstance(raw, list):
        for value in raw:
            yield from objects(value)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            for line in raw.splitlines():
                if line.startswith('data: ') and line != 'data: [DONE]':
                    yield from objects(line[6:])
        else:
            if not isinstance(parsed, str):
                yield from objects(parsed)


def main():
    results = []
    for task in TASKS:
        for arm in 'ABC':
            root = HERE / 'attempt-02' / arm / task['id']
            events = [json.loads(line) for line in (root / 'capture/events.jsonl').read_text().splitlines()]
            outbound = [e for e in events if e['type'] in ('http.request', 'experimental.ws.send')]
            records = {}
            for event in events:
                if event['type'] not in ('http.response', 'experimental.ws.receive'):
                    continue
                for value in objects(event['data']):
                    if value.get('object') == 'response' and value.get('id') and isinstance(value.get('usage'), dict):
                        if value['usage'].get('input_tokens') is not None:
                            records[value['id']] = value
            assert len(outbound) == len(records) and outbound, (arm, task['id'], 'incomplete usage')
            for event in outbound:
                body = json.loads(event['data'])
                assert body['model'] == 'gpt-6.1-terra', (arm, task['id'], 'model')
                assert body['reasoning']['effort'] == 'low', (arm, task['id'], 'effort')
            first = json.loads(outbound[0]['data'])
            text = [c.get('text') for item in first['input'] if item.get('role') == 'user'
                    for c in item.get('content', []) if isinstance(c, dict)]
            assert task['question'] in text, (arm, task['id'], 'original question')
            assert all(r['status'] == 'completed' and r['model'] == 'gpt-6.1-terra' for r in records.values())
            usage = {k: sum(r['usage'][k] for r in records.values()) for k in ('input_tokens', 'output_tokens')}
            usage['cached_tokens'] = sum(r['usage']['input_tokens_details']['cached_tokens'] for r in records.values())
            usage['uncached_tokens'] = usage['input_tokens'] - usage['cached_tokens']
            assert 0 <= usage['cached_tokens'] <= usage['input_tokens']
            results.append(dict(arm=arm, task=task['id'], provider_requests=len(outbound), usage=usage,
                                response_ids=list(records), status='PASS_PROVIDER_IDENTITY_AND_USAGE'))
    with (HERE / 'provider-capture-verification.json').open('x') as stream:
        json.dump(results, stream, ensure_ascii=False, indent=2)
    print('PASS: 12 real Terra Low sessions, original questions and complete inbound provider usage')


if __name__ == '__main__':
    main()
