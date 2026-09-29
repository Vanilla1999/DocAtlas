"""Bounded synchronous scoring for isolated experiments, not a serving backend.

A cooperative stage deadline rejects late results and prevents subsequent calls.
It cannot interrupt an in-flight native inference; a production worker must supply
its own cancellation boundary. Cached successful results remain usable after an
execution failure/limit, but every cache hit records the degraded state.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
import time
from typing import Callable, Mapping, Any


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class BoundedScorer:
    def __init__(self, scorer: Callable[[str, str], float], *, max_evaluations: int = 60,
                 timeout: float = 10.0, score_range: tuple[float, float] | None = (-1.0, 1.0),
                 max_events: int = 256, capture_text: bool = False):
        if type(max_evaluations) is not int or max_evaluations < 1:
            raise ValueError('max_evaluations must be a positive integer')
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be positive and finite')
        if type(max_events) is not int or max_events < 1:
            raise ValueError('max_events must be a positive integer')
        if score_range is not None and (len(score_range) != 2 or
            not all(math.isfinite(x) for x in score_range) or score_range[0] >= score_range[1]):
            raise ValueError('invalid score range')
        self._scorer, self._max, self._timeout = scorer, max_evaluations, float(timeout)
        self._score_range = score_range
        self._count = 0
        self._cache: dict[tuple[str, str], float] = {}
        self._degraded = False
        self._degraded_reason: str | None = None
        self._started: float | None = None
        self._events: list[dict[str, Any]] = []
        self._max_events, self._capture_text = max_events, capture_text
        self._dropped = 0

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def degraded_reason(self) -> str | None:
        return self._degraded_reason

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._events))

    @property
    def summary(self) -> dict[str, Any]:
        return {'evaluations': self._count, 'cached_pairs': len(self._cache),
                'degraded': self._degraded, 'degraded_reason': self._degraded_reason,
                'events_dropped': self._dropped, 'timeout_seconds': self._timeout,
                'timeout_kind': 'cooperative_stage_deadline_not_cancellation'}

    def identity(self) -> dict[str, Any]:
        provider = getattr(self._scorer, 'identity', None)
        if callable(provider):
            result = provider()
            if not isinstance(result, Mapping):
                raise ValueError('scorer identity must be a mapping')
            result = deepcopy(dict(result))
            if result.get('verified') is True:
                fingerprint = result.get('fingerprint')
                if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                    or any(c not in '0123456789abcdef' for c in fingerprint)):
                    raise ValueError('verified scorer requires a content fingerprint')
            return result
        return {'kind': 'unverified_callable', 'verified': False}

    def _record(self, outcome: str, question: str, text: str, **fields: Any) -> None:
        if len(self._events) >= self._max_events:
            self._dropped += 1
            return
        event = {'outcome': outcome, 'question_sha256': text_digest(question),
                 'text_sha256': text_digest(text), 'text_chars': len(text),
                 'text_utf8_bytes': len(text.encode('utf-8')), 'evaluations': self._count,
                 'degraded': self.degraded, 'degraded_reason': self.degraded_reason, **fields}
        if self._capture_text:
            event.update(question=question, evidence_text=text)
        self._events.append(event)

    def record_decision(self, question: str, text: str, **fields: Any) -> None:
        """Record source/phase bindings separately from query/text score cache."""
        self._record('admission_decision', question, text, **fields)

    def _fail(self, reason: str, question: str, text: str, **fields: Any) -> None:
        self._degraded, self._degraded_reason = True, reason
        self._record(reason, question, text, **fields)

    def score(self, question: str, evidence_text: str) -> float | None:
        key = (text_digest(question), text_digest(evidence_text))
        if key in self._cache:
            value = self._cache[key]
            self._record('cache_hit', question, evidence_text, score=value)
            return value
        if self._degraded:
            self._record('degraded_no_inference', question, evidence_text)
            return None
        now = time.monotonic()
        if self._started is None:
            self._started = now
        if now - self._started >= self._timeout:
            self._fail('stage_deadline_exceeded', question, evidence_text)
            return None
        if self._count >= self._max:
            self._fail('evaluation_limit_reached', question, evidence_text)
            return None
        self._count += 1
        try:
            value = float(self._scorer(question, evidence_text))
        except Exception as error:
            self._fail('scorer_error', question, evidence_text, error_type=type(error).__name__)
            return None
        elapsed = time.monotonic() - self._started
        if elapsed >= self._timeout:
            self._fail('stage_deadline_exceeded', question, evidence_text, stage_elapsed_seconds=elapsed)
            return None
        if not math.isfinite(value):
            self._fail('nonfinite_score', question, evidence_text)
            return None
        if self._score_range is not None and not self._score_range[0] <= value <= self._score_range[1]:
            self._fail('score_out_of_range', question, evidence_text, score=value)
            return None
        observer = getattr(self._scorer, 'last_observation', None)
        try:
            observation = observer() if callable(observer) else None
        except Exception as error:
            self._fail('scorer_telemetry_error', question, evidence_text, error_type=type(error).__name__)
            return None
        self._cache[key] = value
        self._record('scored', question, evidence_text, score=value, stage_elapsed_seconds=elapsed,
                     input_observation=observation)
        return value
