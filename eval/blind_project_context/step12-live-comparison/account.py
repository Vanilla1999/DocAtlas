"""Offline raw-provider accounting; estimates never replace provider usage."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def usage_records(value):
    if isinstance(value, dict):
        if value.get('id') and isinstance(value.get('usage'), dict) and 'input_tokens' in value['usage']:
            yield value
        for v in value.values():
            yield from usage_records(v)
    elif isinstance(value, list):
        for v in value:
            yield from usage_records(v)
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            for line in value.splitlines():
                if line.startswith('data: '):
                    yield from usage_records(line[6:])
        else:
            if not isinstance(decoded, str):
                yield from usage_records(decoded)


def main():
    results = []
    for arm in ('qwen-off', 'qwen-one-hop', 'files'):
        for case in ('V-M1','V-M2','V-M3','V-M4'):
            root = HERE / arm / case
            capture = root / 'capture/events.jsonl'
            if not capture.exists():
                results.append(dict(arm=arm, case=case, status='NOT_RUN'))
                continue
            events = [json.loads(line) for line in capture.read_text().splitlines()]
            records = {r['id']: r for e in events for r in usage_records(e.get('data'))}
            totals = Counter()
            for r in records.values():
                u = r['usage']
                totals['input'] += u['input_tokens']
                totals['output'] += u['output_tokens']
                for key, field in [('cached','cached_tokens'), ('cache_write','cache_write_tokens')]:
                    v = u.get('input_tokens_details', {}).get(field)
                    if v is not None:
                        totals[key] += v
                v = u.get('output_tokens_details', {}).get('reasoning_tokens')
                if v is not None:
                    totals['reasoning'] += v
            if 'cached' in totals:
                totals['uncached'] = totals['input'] - totals['cached']
            result = dict(arm=arm, case=case, requests_with_usage=len(records),
                usage=dict(totals), provider_records=list(records.values()),
                retries=sum(e['type']=='retry' for e in events),
                capture_errors=sum(e['type']=='capture.error' for e in events))
            result['status'] = 'CAPTURED' if records else 'NO_USAGE'
            results.append(result)
    (HERE / 'accounting.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    for arm in ('qwen-off', 'qwen-one-hop', 'files'):
        totals = Counter()
        for r in results:
            if r['arm'] == arm:
                totals.update(r.get('usage', {}))
        print(arm, dict(totals))


if __name__ == '__main__':
    main()
