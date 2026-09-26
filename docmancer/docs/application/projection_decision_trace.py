"""Bounded private projector decisions. These events are neither context nor proof."""
from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_DECISION_EVENTS = 128


def _key(*parts: Any) -> str:
    # Hash only bounded identity material; never expose paths, prose or queries.
    raw = json.dumps([str(part or '')[:2048] for part in parts], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class ProjectionDecisionTrace:
    """One request/attempt's event log; no global state or selection side effects."""

    def __init__(self, diagnostics: dict[str, Any]) -> None:
        self.state: dict[str, Any] = {
            'schema_version': 1, 'events': [], 'counts': {},
            'variant_attempts': 0, 'omitted_events': 0,
            'selection_events_omitted': 0,
        }
        diagnostics['decision_trace'] = self.state

    def record(
        self, stage: str, decision: str, reason: str,
        candidate: Any, variant: Any = None, *,
        budget_tokens: int | None = None, previous: Any = None,
    ) -> None:
        """Record an executed branch, not an inference from missing final text."""
        key = f'{stage}:{reason}'
        counts = self.state['counts']
        counts[key] = counts.get(key, 0) + 1
        if len(self.state['events']) >= MAX_DECISION_EVENTS:
            self.state['omitted_events'] += 1
            self.state['selection_events_omitted'] += int(stage == 'selection')
            return
        candidate = candidate if isinstance(candidate, dict) else {}
        variant = variant if isinstance(variant, dict) else {}
        identity = _key(candidate.get('project_identity'),
                        candidate.get('stable_id') or candidate.get('stable_chunk_id')
                        or candidate.get('evidence_id') or candidate.get('path') or candidate.get('source'))
        def variant_key(value: dict[str, Any]) -> str:
            return _key(identity, value.get('evidence_id'), value.get('line_start'),
                        value.get('line_end'), value.get('snippet'))
        event = {'stage': stage, 'decision': decision, 'reason': reason,
                 'candidate_key': identity, 'variant_key': variant_key(variant)}
        if budget_tokens is not None:
            event['budget_tokens'] = int(budget_tokens)
        if isinstance(previous, dict):
            event['previous_variant_key'] = variant_key(previous)
        self.state['events'].append(event)
