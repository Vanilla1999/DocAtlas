"""Offline Step14 capture accounting. Missing usage is null, never a tokenizer estimate."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def decoded(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def usage_records(value):
    if isinstance(value, dict):
        if value.get('id') and isinstance(value.get('usage'), dict) and 'input_tokens' in value['usage']:
            yield value
        for child in value.values():
            yield from usage_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from usage_records(child)
    elif isinstance(value, str):
        parsed = decoded(value)
        if not isinstance(parsed, str):
            yield from usage_records(parsed)
        else:
            for line in value.splitlines():
                if line.startswith('data: '):
                    yield from usage_records(line[6:])


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def packet(message):
    result = message.get('result', {})
    if not isinstance(result, dict):
        return {}
    if isinstance(result.get('structuredContent'), dict):
        return result['structuredContent']
    for part in result.get('content', []):
        if isinstance(part, dict) and part.get('type') == 'text':
            parsed = decoded(part.get('text'))
            if isinstance(parsed, dict):
                return parsed
    return {}


def summarize(root, arm, task):
    events = rows(root / 'capture/events.jsonl')
    stdio = rows(root / 'stdio-events.jsonl')
    requests = [e for e in events if e['type'] in ('http.request', 'experimental.ws.send')]
    first = requests[0] if requests else None
    records = {r['id']: r for e in events for r in usage_records(e.get('data'))}
    usage = {}
    fields = {'input': ('input_tokens',), 'output': ('output_tokens',),
              'cached': ('input_tokens_details', 'cached_tokens'),
              'cache_write': ('input_tokens_details', 'cache_write_tokens'),
              'reasoning': ('output_tokens_details', 'reasoning_tokens')}
    for name, keys in fields.items():
        values = []
        for record in records.values():
            value = record['usage']
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            values.append(value)
        usage[name] = sum(values) if values and all(isinstance(v, (int, float)) for v in values) else None
    usage['uncached'] = usage['input'] - usage['cached'] if usage['input'] is not None and usage['cached'] is not None else None
    calls = [e for e in stdio if e['direction'] == 'request' and e['message'].get('method') in ('tools/call', 'resources/read')]
    completed = {e['message'].get('id'): e for e in stdio if e['direction'] == 'response' and 'id' in e['message']}
    status = []
    qwen_receipts = []
    for call in calls:
        message = call['message']
        response = completed.get(message.get('id'))
        if message.get('params', {}).get('name') == 'docs_status':
            status.append(dict(arguments=message['params'].get('arguments'),
                request_monotonic_ns=call['monotonic_ns'],
                response_monotonic_ns=response['monotonic_ns'] if response else None,
                request_wall_time_ns=call.get('wall_time_ns'),
                response_wall_time_ns=response.get('wall_time_ns') if response else None,
                payload=packet(response['message']) if response else None))
        if response:
            # Preserve actual minimal-context metadata; no invented score/pair totals.
            payload = packet(response['message'])
            if message.get('params', {}).get('name') == 'get_docs_context':
                qwen_receipts.append(dict(request_id=message.get('id'), context_quality=payload.get('context_quality'),
                    metrics=payload.get('metrics'), minimal_context=payload.get('minimal_context'),
                    source_selection=payload.get('source_selection'),
                    reason_code=payload.get('reason_code')))
    first_body = decoded(first['data']) if first else None
    body_text = '\n'.join(strings(first_body))
    hints = re.findall(r'<docatlas_language_preflight>\s*(\{[^<>]*?\})\s*</docatlas_language_preflight>', body_text)
    hints = [decoded(hint) for hint in hints]
    prompt_audits = [e for e in events if e['type'] == 'prompt.admitted']
    config = json.loads((root / 'config.json').read_text())
    binding = (json.loads(config['mcp']['servers']['docatlas']['environment']['DOCATLAS_PROJECT_BINDING'])
               if arm != 'C' else None)
    first_ns = int(first['monotonic_ns']) if first else None
    first_wall_ms = first.get('wall_time_ms') if first else None
    host_verified = None
    hint_verified = None
    timing_verified = None
    if arm == 'B':
        hint_verified = False
        for s in status:
            payload = s['payload'] or {}
            audit = next((p['data'].get('metadata', {}).get('docatlas_language_preflight')
                          for p in prompt_audits if p['sessionID'] == first.get('sessionID')), None) if first else None
            if (payload.get('project_binding') == binding and payload.get('documentation_language', {}).get('languages') == ['en'] and
                    payload.get('documentation_language', {}).get('status') == 'declared' and
                    audit and audit.get('binding_validated') is True and audit.get('project_binding') == binding and
                    any(isinstance(h, dict) and h.get('status') == 'declared' and h.get('languages') == ['en']
                        and h.get('hint_only') is True and h.get('prompt_id') == audit.get('prompt_id') for h in hints)):
                hint_verified = True
                if (first_wall_ms is not None and s['request_wall_time_ns'] is not None
                        and s['response_wall_time_ns'] is not None):
                    # Date.now is millisecond-granular. Require a response strictly
                    # before the START of the provider-hook millisecond bucket.
                    timing_verified = (s['request_wall_time_ns'] <= s['response_wall_time_ns']
                                       < int(first_wall_ms) * 1_000_000)
        host_verified = (timing_verified if hint_verified else False)
    raw = rows(root / 'runtime/raw.jsonl')
    tool_calls = [e['part'] for e in raw if e.get('type') == 'tool_use']
    tasks = json.loads((HERE / 'tasks.json').read_text())
    question = next(t['question'] for t in tasks if t['id'] == task)
    ids = {e['sessionID'] for e in events if e.get('sessionID')}
    capture_errors = [e for e in events if e['type'] == 'capture.error']
    pair_values = [(r.get('source_selection') or {}).get('model_pairs') for r in qwen_receipts]
    if first and question not in body_text:
        capture_errors.append({'type': 'original_question_not_found_in_first_request'})
    return dict(arm=arm, task=task, status='CAPTURED' if events else 'NOT_RUN',
        provider_requests=len(requests), provider_requests_by_kind=dict(Counter(e.get('kind') for e in requests)),
        session_ids=sorted(ids), session_ids_count=len(ids), requests_with_usage=len(records), usage=usage,
        usage_coverage_complete=bool(requests) and len(records) == len(requests),
        provider_records=[{'id': r['id'], 'usage': r['usage']} for r in records.values()],
        retries=sum(e['type'] == 'retry' for e in events), capture_errors=capture_errors,
        first_provider_monotonic_ns=first_ns, first_provider_language_hints=hints,
        first_provider_wall_time_ms=first_wall_ms,
        original_question_in_first_request=question in body_text if first else None,
        status_observations=status, host_preflight_verified=host_verified,
        host_hint_binding_verified=hint_verified, host_timestamp_order_verified=timing_verified,
        host_timestamp_reason=('legacy_cross_process_clock_mismatch_no_python_wall_capture'
                               if arm == 'B' and timing_verified is None else None),
        model_tool_calls=dict(Counter(p.get('tool') for p in tool_calls)),
        actual_mcp_calls=dict(Counter(e['message'].get('params', {}).get('name', e['message'].get('method')) for e in calls)),
        mcp_missing_responses=sum(e['message'].get('id') not in completed for e in calls),
        qwen_receipts=qwen_receipts, qwen_pairs=sum(pair_values)
            if pair_values and all(type(v) is int for v in pair_values) else None,
        answer='\n'.join(e.get('part', {}).get('text', '') for e in raw if e.get('type') == 'text'),
        answer_quality='NOT_GRADED', source_facts_quality='NOT_GRADED',
        timing_boundary='wall-v2: Python time.time_ns versus JS Date.now, same-host epoch clock; JS millisecond resolution, wall-clock steps not excluded. Monotonic clocks are process-local only. Legacy Python wall time is never reconstructed. Not remote arrival.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', default='attempt-01')
    parser.add_argument('--output', type=Path, required=True, help='New file; must remain inside this evaluation directory')
    args = parser.parse_args()
    if Path(args.attempt).name != args.attempt or not args.output.resolve().is_relative_to(HERE):
        parser.error('Only evaluation-local input/output paths are permitted')
    result = [summarize(HERE / args.attempt / a / t, a, t)
              for t in ('V-M1', 'V-M2', 'V-M3', 'V-M4') for a in ('A', 'B', 'C')
              if (HERE / args.attempt / a / t / 'config.json').exists()]
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
