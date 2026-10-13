"""Host-only opt-in selection of native candidates, before presentation packing.

An experiment may select existing objects but cannot mint source bindings,
qualification, or authority. Downstream validators remain unchanged.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from docmancer.docs.domain.original_body_discovery import (
    original_body_discovery_binding,
    experimental_selector_settings,
    policy_candidate_admission_active,
    source_valid_candidate_admission_active,
)

_SELECTOR = ContextVar("experimental_native_candidate_selector", default=None)
_OBSERVER = ContextVar("experimental_native_selection_observer", default=None)


def native_rank_selection_active() -> bool:
    """Use native rank inside a live, source-bound documentation read."""
    return experimental_selector_settings() is not None


@dataclass
class SelectionObservation:
    """Diagnostics returned to a host observer; never source authorization."""

    calls: int = 0
    errors: list[str] = field(default_factory=list)


@contextmanager
def experimental_selection_observer(observer):
    """Observe copies after selection; diagnostic failures cannot change it.

    A host can inspect the yielded state's errors to detect missing receipts.
    No original candidate object is exposed through this observer.
    """
    state = SelectionObservation()
    token = _OBSERVER.set((observer, state))
    try:
        yield state
    finally:
        _OBSERVER.reset(token)


@contextmanager
def experimental_candidate_selector(selector):
    """Set a synchronous host experiment callback; never populated from wire data."""
    token = _SELECTOR.set(selector)
    try:
        yield
    finally:
        _SELECTOR.reset(token)


def _diagnostic_value(value, *, key=""):
    if key == "raw_document" and isinstance(value, str):
        return {"sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(), "characters": len(value)}
    if isinstance(value, dict):
        return {str(name): _diagnostic_value(item, key=str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_diagnostic_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return {"type": type(value).__qualname__, "value": str(value)}


def _candidate_receipt(chunk):
    metadata = _diagnostic_value(chunk.metadata or {})
    reference = metadata.get("_reference_evidence") or {}
    source = reference.get("source") or {}
    text_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
    identity = [source, reference.get("char_start"), reference.get("char_end"), chunk.chunk_index, text_hash]
    return {
        "id": hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8")).hexdigest(),
        "source": chunk.source, "chunk_index": chunk.chunk_index, "score": chunk.score,
        "text": chunk.text, "text_sha256": text_hash,
        "path": source.get("canonical_path"),
        "span": [reference.get("char_start"), reference.get("char_end")],
        "binding": source, "metadata": metadata,
    }


def _observe_selection(question, pool, excluded, original, selection):
    configured = _OBSERVER.get()
    if configured is None:
        return
    observer, state = configured
    state.calls += 1
    try:
        # Constructing the verbose receipt is strictly optional. Raw documents
        # are represented by hashes; the exact native model inputs remain text.
        receipt = {
            "schema_version": 1, "question": question,
            "pool": [_candidate_receipt(chunk) for chunk in pool],
            "complete_candidates": [_candidate_receipt(chunk) for chunk in original],
            "excluded": [{"candidate": _candidate_receipt(chunk), "reason": reason,
                          "original_ordinal": ordinal} for chunk, reason, ordinal in excluded],
            "selection": selection,
        }
        observer(deepcopy(receipt))
    except Exception as exc:
        state.errors.append(type(exc).__name__ + ": " + str(exc))


def select_experimental_candidates(candidates, *, question):
    if native_rank_selection_active():
        from docmancer.docs.domain.original_body_discovery import experimental_context_max_tokens
        if experimental_context_max_tokens() is None:
            raise ValueError("native-rank selection requires a fixed experimental context cap")
        pool, excluded, seen = [], [], set()
        for ordinal, chunk in enumerate(candidates):
            metadata = chunk.metadata or {}
            trace = (metadata.get("retrieval_query_matches") or {}).get("query-original") or {}
            binding = original_body_discovery_binding(
                question=question, body=chunk.text, candidate=metadata,
            )
            if binding is None or not (trace.get("qualified") is True or trace.get("literal_context_admission")):
                excluded.append((chunk, "no_checked_original_admission", ordinal))
            elif binding in seen:
                excluded.append((chunk, "duplicate_exact_native_occurrence", ordinal))
            else:
                seen.add(binding)
                pool.append(chunk)
        _observe_selection(question, pool, excluded, candidates, {
            "mode": "native_acquisition_rank", "status": "final_budget_only",
            "selected_indices": list(range(len(pool))), "top_k": None,
            "model_forward_attempts": 0, "model_forwards": 0,
        })
        return pool
    # No heuristic or callback selector outside a verified native read. The
    # public projector requires a live receipt before delivering project bytes.
    return candidates
