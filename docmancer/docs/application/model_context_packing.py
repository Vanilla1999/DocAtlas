"""Opt-in host-side, reversible metadata packing of already-selected evidence.

No scoring, source filtering, summaries, retrieval or semantic sufficiency claim.
Full response-bound citation refs and every source-text byte remain unchanged.
The existing MCP wire/default and ModelContextSession projection are unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .model_context_view import (
    FORMAT as BASE_FORMAT, META_KEY, _view, canonical, encode_model_result,
    restore_model_result, resolve_model_reference,
)
from .projection_tokenizer import projection_token_count

FORMAT = "docatlas.packed-model-context.v1"
POLICIES = ("paths-v1", "sections-v1")
NOTICE = "Each source uses source_catalog[source]. lines=[first,last], inclusive. Cite the unchanged full ref."
_RESERVED = frozenset({"source_catalog", "packing_policy", "packing_notice"})


def _pack(view: dict, policy: str) -> dict:
    if policy not in POLICIES:
        raise ValueError("unknown_model_context_packing_policy")
    if _RESERVED.intersection(view):
        raise ValueError("model_context_packing_field_collision")
    result = deepcopy(view)
    result.update(context_format=FORMAT, packing_policy=policy, packing_notice=NOTICE)
    catalog, seen, records = {}, {}, []
    for row in view["sources"]:
        if "source" in row or "lines" in row:
            raise ValueError("model_context_packing_source_collision")
        names = ("path", "section") if policy == "sections-v1" else ("path",)
        common = {name: deepcopy(row[name]) for name in names if name in row}
        key = canonical(common)
        if key not in seen:
            seen[key] = "d" + str(len(catalog) + 1)
            catalog[seen[key]] = common
        item = {name: deepcopy(value) for name, value in row.items() if name not in common}
        item["source"] = seen[key]
        if "line_start" in item and "line_end" in item:
            item["lines"] = [item.pop("line_start"), item.pop("line_end")]
        records.append(item)
    result["source_catalog"] = catalog
    result["sources"] = records
    return result


def _cost(view: dict) -> tuple[int, int, int]:
    raw = canonical(view).encode("utf-8")
    tokens = projection_token_count(raw)
    return tokens, len(raw), max(tokens, math.ceil(len(raw) / 4))


def pack_model_view(view: dict, metadata: dict, *, policy: str = "adaptive-v1") -> dict:
    """Validate an issued v1 view, then return ONLY its model-visible projection.

    Adaptive mode never increases o200k_base tokens, UTF-8 bytes, or the existing
    conservative context-budget estimate for the exact same response packet.
    Metadata stays private; same-packet comparison avoids random-ref token noise.
    """
    if policy not in (*POLICIES, "adaptive-v1"):
        raise ValueError("unknown_model_context_packing_policy")
    restore_model_result(view, metadata)
    original_cost = _cost(view)
    if policy in POLICIES:
        result = _pack(view, policy)
        if _cost(result)[2] > 12000:
            raise ValueError("model_context_packing_output_limit")
        return result
    eligible = [(original_cost, 0, view)]
    for index, name in enumerate(POLICIES, 1):
        candidate = _pack(view, name)
        cost = _cost(candidate)
        if all(a <= b for a, b in zip(cost, original_cost)):
            eligible.append((cost, index, candidate))
    return deepcopy(min(eligible, key=lambda value: (value[0], value[1]))[2])


def _original(metadata: dict) -> dict:
    manifest = metadata.get(META_KEY) if isinstance(metadata, dict) else None
    if (not isinstance(manifest, dict) or manifest.get("format") != BASE_FORMAT
            or not isinstance(manifest.get("packet"), dict)):
        raise ValueError("model_view_manifest_missing")
    original = _view(manifest["packet"])
    if original is None:
        raise ValueError("model_view_manifest_mismatch")
    return original


def unpack_model_view(view: dict, metadata: dict) -> dict:
    """Check the ENTIRE catalog, text, field-presence and reference binding."""
    if not isinstance(view, dict):
        raise ValueError("invalid_packed_model_view")
    if view.get("context_format") == BASE_FORMAT:
        restore_model_result(view, metadata)
        return deepcopy(view)
    if view.get("context_format") != FORMAT:
        raise ValueError("unknown_packed_model_view_format")
    original = _original(metadata)
    policy = view.get("packing_policy")
    if policy not in POLICIES or canonical(view) != canonical(_pack(original, policy)):
        raise ValueError("packed_model_view_manifest_mismatch")
    return original


def restore_packed_result(view: dict, metadata: dict) -> dict:
    """Restore the exact private machine packet, not a new source-read grant."""
    return restore_model_result(unpack_model_view(view, metadata), metadata)


def resolve_packed_reference(view: dict, metadata: dict, reference: str) -> dict:
    """Only full issued refs resolve, with the same scope/snapshot as v1."""
    return resolve_model_reference(unpack_model_view(view, metadata), metadata, reference)


def prepare_packed_context(result: Any, *, policy: str = "adaptive-v1") -> tuple[dict, dict]:
    """Host entry point after a REAL MCP response; do not feed metadata to LLM.

    Ineligible results (errors, denials, lifecycle, patch contexts) fail explicitly.
    The caller must retain its ordinary handling of those results, not fabricate
    a compact successful answer or an absence decision.
    """
    from docmancer.docs.interfaces.host_context import extract_tool_payload
    packet = extract_tool_payload(result)
    encoded = encode_model_result(packet)
    if encoded is None:
        raise ValueError("model_context_packing_ineligible_result")
    view, metadata = encoded
    return pack_model_view(view, metadata, policy=policy), metadata
