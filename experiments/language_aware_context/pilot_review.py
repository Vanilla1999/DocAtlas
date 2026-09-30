"""Content-addressed, condition-masked review of genuine stored model outputs.

This module never generates answers or scores semantics. A reviewer must supply
all judgments; missing or changed records fail closed. Masking does not turn the
same experiment author into an independent judge. Preserve the key separately.
"""
from __future__ import annotations
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

CONDITIONS = frozenset(('A', 'B', 'A_packing', 'B_packing', 'oracle', 'no_context'))
BOOL_FIELDS = ('factually_correct', 'grounded', 'citations_valid', 'language_ok')


def record_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def blind_records(records: Iterable[dict], tasks: Mapping[str, dict], *,
                  token: Callable[[], str]) -> tuple[list[dict], list[dict]]:
    """Export only allowed review fields; deduplicate byte-identical review inputs.

    Use a cryptographically random token source in a real review. Deterministic
    tokens in unit tests test this mechanism, not the quality of model answers.
    """
    packets: list[dict] = []
    key: list[dict] = []
    by_content: dict[str, dict] = {}
    used_ids: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for record in records:
        task_id, condition = record.get('task_id'), record.get('condition')
        if task_id not in tasks or condition not in CONDITIONS:
            raise ValueError('unknown task or condition')
        if (task_id, condition) in seen:
            raise ValueError('duplicate task condition')
        seen.add((task_id, condition))
        task = tasks[task_id]
        if record.get('question') != task['question']:
            raise ValueError('question changed')
        if type(task['answerable']) is not bool:
            raise ValueError('invalid answerability')
        answer = record.get('answer', {}).get('text')
        evidence = record.get('evidence')
        if not isinstance(answer, str) or not isinstance(evidence, list):
            raise ValueError('missing genuine answer/evidence')
        visible = []
        source_ids = set()
        for source in evidence:
            if (not isinstance(source, dict) or not isinstance(source.get('id'), str)
                    or not isinstance(source.get('text'), str) or source['id'] in source_ids):
                raise ValueError('invalid evidence')
            source_ids.add(source['id'])
            visible.append({k: source.get(k) for k in ('id', 'path', 'text')})
        content = {'question': record['question'], 'answerable': task['answerable'],
                   'expected_facts': deepcopy(task['facts']), 'evidence': visible, 'answer': answer}
        content_hash = record_digest(content)
        packet = by_content.get(content_hash)
        if packet is None:
            opaque = token()
            if not isinstance(opaque, str) or not opaque or opaque in used_ids:
                raise ValueError('opaque ID collision or invalid ID')
            used_ids.add(opaque)
            packet = {'id': opaque, **content}
            packet['packet_sha256'] = record_digest(packet)
            packets.append(packet)
            by_content[content_hash] = packet
        key.append({'id': packet['id'], 'packet_sha256': packet['packet_sha256'],
                    'task_id': task_id, 'condition': condition, 'answerable': task['answerable'],
                    'language': task['query_language'], 'family': task['family']})
    return packets, key


def join_judgments(packets: list[dict], key: list[dict], judgments: list[dict]) -> list[dict]:
    """Join only after saving/sealing all judgments. Never fill missing decisions."""
    by_id: dict[str, dict] = {}
    for packet in packets:
        opaque = packet['id']
        raw = {k: v for k, v in packet.items() if k != 'packet_sha256'}
        if opaque in by_id or record_digest(raw) != packet['packet_sha256']:
            raise ValueError('duplicate or changed review packet')
        by_id[opaque] = packet
    scores: dict[str, dict] = {}
    expected_fields = {'id', 'packet_sha256', 'packet_complete', 'reason', *BOOL_FIELDS}
    for row in judgments:
        opaque = row.get('id')
        if set(row) != expected_fields or opaque not in by_id or opaque in scores:
            raise ValueError('unknown, incomplete or duplicate judgment')
        packet = by_id[opaque]
        if row['packet_sha256'] != packet['packet_sha256']:
            raise ValueError('judgment binding changed')
        if any(type(row[f]) is not bool for f in BOOL_FIELDS):
            raise ValueError('judgments must contain actual booleans')
        complete = row['packet_complete']
        if (packet['answerable'] and type(complete) is not bool) or (
                not packet['answerable'] and complete is not None):
            raise ValueError('wrong packet-completeness denominator')
        if not isinstance(row['reason'], str) or not row['reason'].strip():
            raise ValueError('review reason required')
        scores[opaque] = row
    if set(scores) != set(by_id):
        raise ValueError('missing judgments')
    linked: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    result = []
    for row in key:
        opaque = row['id']
        pair = (row['task_id'], row['condition'])
        if (opaque not in by_id or pair in pairs or row['condition'] not in CONDITIONS
                or row['packet_sha256'] != by_id[opaque]['packet_sha256']
                or row['answerable'] is not by_id[opaque]['answerable']):
            raise ValueError('review key binding changed')
        pairs.add(pair)
        linked.add(opaque)
        score = scores[opaque]
        result.append({**row, **score,
            'primary_success': all(score[f] for f in ('factually_correct', 'grounded', 'citations_valid'))})
    if linked != set(by_id):
        raise ValueError('unlinked review packet')
    return result
