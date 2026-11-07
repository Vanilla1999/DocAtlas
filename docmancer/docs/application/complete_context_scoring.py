"""Pinned local MaxP scoring with exhaustive question/body token coverage.

This is a scorer, not an admission or sufficiency policy. Callers must supply
source-checked structural units; windows never become delivery units. There is
no retrieval, model download, top-k, deadline or partial-success fallback here.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import math
from time import perf_counter

from .experimental_selection_modes import (
    JointSemanticRelevanceError, _load_mini, _RUNTIME_LOCK,
)


WINDOW_RECIPE = "complete-maxp-token-overlap-v1"
GATED_WINDOW_RECIPE = "complete-own-body-gated-maxp-v2"
FIT_WINDOW_RECIPE = "complete-fit-first-maxp-v4"
# Batch size controls resident tensors, never how many pairs are processed.
INFERENCE_BATCH = 16


@dataclass(frozen=True)
class ScoringUnit:
    identity: str
    body: str
    ancestor_context: str = ""
    heading_context: str = ""


def _windows(length: int, capacity: int):
    """Half-overlapping token intervals, including the final token exactly."""
    start = 0
    while start < length:
        end = min(length, start + capacity)
        yield start, end
        if end == length:
            return
        start += max(1, capacity // 2)


def score_complete_units(
    queries: Sequence[str], units: Iterable[ScoringUnit], model_path: str,
    *, own_body_gate: bool = False, fit_whole_pair: bool = False,
    record_intervals: bool = False,
) -> tuple[list[dict], dict]:
    """Score all lanes/windows using raw logits and return auditable counts.

    Only original question and a supplied full translation belong in ``queries``.
    Ancestor windows are paired with body windows, so ancestor-only windows can
    never independently select a unit. Every query, body and ancestor token is
    covered. The Cartesian recipe deliberately has no semantic work ceiling.
    Input source strings are never decoded/reconstructed from model tokens.
    V4 per-pair intervals are opt-in diagnostics; without record_intervals only
    aggregate recorded/omitted counts are kept, not a Cartesian-size trace.
    """
    if own_body_gate and fit_whole_pair:
        raise ValueError("Fit-first recipe does not reinterpret the historical own-body gate")
    if own_body_gate:
        # An ancestor introduction may disambiguate a relevant own body but
        # cannot by itself admit an unrelated child. Both exhaustive passes
        # retain every input token; this is a score gate, never a source quota.
        started = perf_counter()
        units = tuple(units)
        try:
            contextual, first = score_complete_units(queries, units, model_path)
        except JointSemanticRelevanceError as exc:
            raise JointSemanticRelevanceError(str(exc), {
                **exc.receipt, "recipe": GATED_WINDOW_RECIPE,
                "failed_pass": "contextual", "total_seconds": perf_counter() - started,
            }) from exc
        try:
            independent, second = score_complete_units(queries, (
                ScoringUnit(unit.identity, unit.body, unit.heading_context)
                for unit in units), model_path)
        except JointSemanticRelevanceError as exc:
            failed = {**exc.receipt, "recipe": GATED_WINDOW_RECIPE,
                      "failed_pass": "own_body", "total_seconds": perf_counter() - started}
            for key in ("model_pairs", "model_forwards", "model_input_tokens", "inference_seconds",
                        "model_load_attempts", "model_loads"):
                failed[key] = first[key] + exc.receipt.get(key, 0)
            raise JointSemanticRelevanceError(str(exc), failed) from exc
        scores = []
        for context, own in zip(contextual, independent, strict=True):
            if context["identity"] != own["identity"]:
                raise ValueError("own_body_gate_identity_mismatch")
            scores.append({**context, "score": min(context["score"], own["score"]),
                           "contextual_score": context["score"], "own_body_score": own["score"],
                           "pairs": context["pairs"] + own["pairs"]})
        receipt = {**first, "recipe": GATED_WINDOW_RECIPE,
                   "aggregation": "min_contextual_and_own_body_max_raw_logit",
                   "own_body_gate": True, "total_seconds": perf_counter() - started}
        for key in ("model_pairs", "model_forwards", "model_input_tokens", "inference_seconds",
                    "model_load_attempts", "model_loads"):
            receipt[key] = first[key] + second[key]
        return scores, receipt
    receipt = {
        "recipe": FIT_WINDOW_RECIPE if fit_whole_pair else WINDOW_RECIPE,
        "status": "scoring", "units": 0,
        "model_pairs": 0, "model_forwards": 0, "model_input_tokens": 0,
        "inference_seconds": 0.0, "model_load_attempts": 0, "model_loads": 0,
        "coverage": "all_query_body_ancestor_tokens", "aggregation": "max_raw_logit",
    }
    started = perf_counter()
    scores = []
    if fit_whole_pair:
        receipt.update(intervals_recorded=0, intervals_omitted=0)
    try:
        if not queries or any(not isinstance(q, str) or not q.strip() for q in queries):
            raise ValueError("Complete scoring requires nonempty original/translation lanes")
        with _RUNTIME_LOCK:
            runtime = _load_mini(model_path, receipt)
            tokenizer = runtime.tokenizer
            # The pinned XLM-R model has two extra positional slots for padding.
            # Tokenizer's finite advertised limit is the actual pair limit.
            maximum = int(tokenizer.model_max_length)
            positions = int(runtime.model.config.max_position_embeddings)
            if not 4 < maximum <= positions:
                raise ValueError("Pinned tokenizer does not advertise a valid finite context window")
            special = tokenizer.num_special_tokens_to_add(pair=True)
            capacity = maximum - special
            query_ids = [tokenizer(q, add_special_tokens=False, truncation=False)["input_ids"]
                         for q in queries]
            if any(not ids for ids in query_ids):
                raise ValueError("Original/translation lane has no model tokens")
            receipt.update(maximum_sequence_length=maximum, pair_special_tokens=special,
                           query_tokens=[len(ids) for ids in query_ids])
            for unit in units:
                if not unit.identity or not unit.body.strip():
                    raise ValueError("Scoring unit must identify a nonempty own body")
                body = tokenizer(unit.body, add_special_tokens=False, truncation=False,
                                 return_offsets_mapping=True)
                body_ids = body["input_ids"]
                context_ids = tokenizer(unit.ancestor_context, add_special_tokens=False,
                                        truncation=False)["input_ids"]
                if not body_ids:
                    raise ValueError("Scoring unit has no body tokens")
                best = -math.inf
                pending = []
                pairs = 0
                intervals = [] if fit_whole_pair and record_intervals else None

                def flush():
                    nonlocal best, pairs
                    if not pending:
                        return
                    inputs = tokenizer.pad(pending, padding=True, return_tensors="pt")
                    tick = perf_counter()
                    with runtime.torch.inference_mode():
                        logits = runtime.model(**inputs).logits
                        if logits.ndim != 2 or logits.shape[1] != 1:
                            raise ValueError("Pinned ranker must produce one raw logit per pair")
                        values = logits[:, 0].float().tolist()
                    receipt["inference_seconds"] += perf_counter() - tick
                    if not all(math.isfinite(value) for value in values):
                        raise ValueError("Mini produced a nonfinite score")
                    best = max(best, *values)
                    pairs += len(values)
                    receipt["model_pairs"] += len(values)
                    receipt["model_forwards"] += 1
                    receipt["model_input_tokens"] += sum(len(p["input_ids"]) for p in pending)
                    pending.clear()

                for lane, qids in enumerate(query_ids):
                    if fit_whole_pair and len(qids) + len(context_ids) + len(body_ids) <= capacity:
                        pending.append(tokenizer.prepare_for_model(
                            qids, pair_ids=context_ids + body_ids,
                            add_special_tokens=True, truncation=False,
                            return_attention_mask=True,
                        ))
                        if intervals is not None:
                            intervals.append({"lane": lane, "whole_pair": True,
                                              "query": [0, len(qids)],
                                              "ancestor": [0, len(context_ids)],
                                              "body": [0, len(body_ids)]})
                        if len(pending) == INFERENCE_BATCH:
                            flush()
                        continue
                    qcap = min(len(qids), capacity // 2)
                    pcap = capacity - qcap
                    ccap = min(len(context_ids), pcap // 3)
                    bcap = pcap - ccap
                    for qa, qb in _windows(len(qids), qcap):
                        for ba, bb in _windows(len(body_ids), bcap):
                            contexts = _windows(len(context_ids), ccap) if context_ids else ((0, 0),)
                            for ca, cb in contexts:
                                pair = tokenizer.prepare_for_model(
                                    qids[qa:qb], pair_ids=context_ids[ca:cb] + body_ids[ba:bb],
                                    add_special_tokens=True, truncation=False,
                                    return_attention_mask=True,
                                )
                                if len(pair["input_ids"]) > maximum:
                                    raise ValueError("Complete scoring pair exceeds physical model window")
                                pending.append(pair)
                                if intervals is not None:
                                    intervals.append({"lane": lane, "whole_pair": False,
                                                      "query": [qa, qb], "ancestor": [ca, cb],
                                                      "body": [ba, bb]})
                                if len(pending) == INFERENCE_BATCH:
                                    flush()
                flush()
                offsets = body["offset_mapping"]
                scores.append({"identity": unit.identity, "score": best, "pairs": pairs,
                               "body_tokens": len(body_ids), "ancestor_tokens": len(context_ids),
                               "body_token_coverage": [0, len(body_ids)],
                                "body_character_extent": [offsets[0][0], offsets[-1][1]]})
                if fit_whole_pair:
                    recorded = len(intervals) if intervals is not None else 0
                    scores[-1].update(intervals_recorded=recorded, intervals_omitted=pairs - recorded)
                    receipt["intervals_recorded"] += recorded
                    receipt["intervals_omitted"] += pairs - recorded
                    if intervals is not None:
                        scores[-1]["pair_token_intervals"] = intervals
                receipt["units"] += 1
        receipt["status"] = "complete"
        return scores, receipt
    except Exception as exc:
        receipt.update(status="scan_incomplete", error_type=type(exc).__name__, error=str(exc))
        raise JointSemanticRelevanceError("Complete semantic scan failed: " + str(exc), receipt) from exc
    finally:
        receipt["total_seconds"] = perf_counter() - started
