"""Integrity helpers for fixed reader experiments.

No retrieval or model invocation lives here.  These helpers bind recorded model
outputs to exact case IDs, model identities, and rendered model inputs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any


_REQUIRED_MODEL_IDENTITY = (
    "model", "model_digest", "runtime_version", "chat_template_digest",
)


def pair_by_case_id(
    lanes: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Pair lanes by unique case ID, never by incidental list order."""

    if not lanes:
        return {}
    mapped: dict[str, dict[str, dict[str, Any]]] = {}
    expected: set[str] | None = None
    per_lane: dict[str, dict[str, dict[str, Any]]] = {}
    for lane, rows in lanes.items():
        lane_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            legacy_id = str(row.get("id") or "")
            record_id = str(row.get("case_id") or "")
            if legacy_id and record_id and legacy_id != record_id:
                raise ValueError(f"conflicting case id in lane {lane}")
            case_id = record_id or legacy_id
            if not case_id:
                raise ValueError(f"missing case id in lane {lane}")
            if case_id in lane_map:
                raise ValueError(f"duplicate case id in lane {lane}: {case_id}")
            lane_map[case_id] = row
        ids = set(lane_map)
        if expected is None:
            expected = ids
        elif ids != expected:
            raise ValueError(
                f"case id mismatch in lane {lane}: "
                f"missing={sorted(expected - ids)} extra={sorted(ids - expected)}"
            )
        per_lane[lane] = lane_map

    for case_id in sorted(expected or ()):
        mapped[case_id] = {
            lane: per_lane[lane][case_id]
            for lane in lanes
        }
    return mapped


def independent_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only actual model draws; cached/reused rows remain audit-only."""

    return [row for row in rows if not row.get("reused_from")]


def make_reader_record(
    *,
    case_id: str,
    arm: str,
    draw: int,
    system_prompt: str,
    question: str,
    rendered_context: str,
    model_identity: dict[str, Any],
    provider_response: dict[str, Any],
    reused_from: str | None = None,
) -> dict[str, Any]:
    """Bind one provider response to the exact frozen model input."""

    missing = [
        key for key in _REQUIRED_MODEL_IDENTITY
        if not isinstance(model_identity.get(key), str)
        or not str(model_identity[key]).strip()
    ]
    if missing:
        raise ValueError(f"incomplete model identity: {missing}")
    model_input = system_prompt + "\n\0" + question + "\n\0" + rendered_context
    result = {
        "case_id": str(case_id),
        "arm": str(arm),
        "draw": int(draw),
        "model_input_sha256": hashlib.sha256(
            model_input.encode("utf-8")
        ).hexdigest(),
        "model_input": {
            "system_prompt": system_prompt,
            "question": question,
            "rendered_context": rendered_context,
        },
        "model_identity": deepcopy(model_identity),
        "provider_response": deepcopy(provider_response),
    }
    if reused_from:
        result["reused_from"] = str(reused_from)
    return result
