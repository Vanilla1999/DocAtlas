"""Eval-only token and usage accounting. Never changes the product estimator."""
from __future__ import annotations
import importlib.metadata
import json
from collections.abc import Iterable, Mapping
from math import ceil


def model_visible_text(wire: Mapping, mode: str) -> str:
    """Explicit host adapter: choose ONE channel; preserve literal text fallback."""
    if mode == 'structured':
        value = wire.get('structuredContent')
        if not isinstance(value, Mapping):
            raise ValueError('structured channel missing')
        if 'diagnostics' in value:
            raise ValueError('private diagnostics cannot become model input')
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if mode == 'text':
        blocks = wire.get('content')
        if not isinstance(blocks, list):
            raise ValueError('text channel missing')
        return '\n'.join(row['text'] for row in blocks if row.get('type') == 'text')
    raise ValueError('host mode must be structured or text')


def tokenizer():
    import tiktoken
    version = importlib.metadata.version('tiktoken')
    if version != '0.11.0':
        raise RuntimeError('experiment requires pinned tiktoken 0.11.0')
    return tiktoken.get_encoding('o200k_base')


def count_input(text: str, encoder=None) -> dict:
    encoder = encoder or tokenizer()
    return {'utf8_bytes': len(text.encode('utf-8')),
            'actual_tokens': len(encoder.encode(text, disallowed_special=())),
            'tokenizer': 'tiktoken/0.11.0:o200k_base'}


def summarize_usage(attempts: Iterable[Mapping]) -> dict:
    """Provider input already contains repeated history/schema. Failed turns count.

    Null means unobserved, not zero. Cached tokens are an input subset; reasoning
    tokens are an output subset and are never added twice to the total.
    """
    attempts = list(attempts)
    fields = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens')
    known = {field: 0 for field in fields}
    seen = {field: 0 for field in fields}
    for attempt in attempts:
        usage = attempt.get('usage') or {}
        for field in fields:
            value = usage.get(field)
            if value is None:
                continue
            if type(value) is not int or value < 0:
                raise ValueError('invalid reported token count')
            known[field] += value
            seen[field] += 1
        if usage.get('cached_input_tokens') is not None and usage.get('input_tokens') is not None:
            if usage['cached_input_tokens'] > usage['input_tokens']:
                raise ValueError('cached input exceeds total input')
        if usage.get('reasoning_tokens') is not None and usage.get('output_tokens') is not None:
            if usage['reasoning_tokens'] > usage['output_tokens']:
                raise ValueError('reasoning exceeds total output')
    complete = bool(attempts) and all(seen[f] == len(attempts) for f in fields[:2])
    result = {'attempt_count': len(attempts), 'usage_complete': complete,
              'failed_attempts': sum(a.get('error') is not None for a in attempts),
              'known_subtotals': {f: known[f] if seen[f] else None for f in fields},
              'observed_attempts_by_field': seen,
              'provider_total_tokens': known['input_tokens'] + known['output_tokens'] if complete else None,
              'monetary_cost': None}
    result['uncached_input_tokens'] = (known['input_tokens'] - known['cached_input_tokens']
        if attempts and seen['input_tokens'] == seen['cached_input_tokens'] == len(attempts) else None)
    return result


def percentiles(values: Iterable[float]) -> dict:
    values = sorted(values)
    if not values:
        return {'n': 0, 'p50': None, 'p95': None}
    return {'n': len(values), 'p50': values[max(0, ceil(.50*len(values))-1)],
            'p95': values[max(0, ceil(.95*len(values))-1)]}
