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


# Managed per-question sessions use a different, history-deduplicated model
# input shape than the single-response v1 view above. Pack only public model
# fields here; ModelContextSession keeps exact original source rows privately.
MANAGED_FORMAT = "docatlas.packed-managed-context.v1"
MANAGED_NOTICE = "Source keys refer to source_catalog. Cite each exact ref, path and line span."
MANAGED_MODES = ("off", "paths-v1", "sections-v1", "adaptive-v1")
_MANAGED_RESERVED = frozenset(("context_format", "packing_policy", "packing_notice", "source_catalog"))


def _pack_managed(view: dict, policy: str) -> dict:
    """Catalog repeated source attributes without changing any original text."""
    if policy not in POLICIES or _MANAGED_RESERVED.intersection(view):
        raise ValueError("invalid_managed_packing_policy_or_collision")
    rows = view.get("sources")
    if not isinstance(rows, list) or not rows:
        raise ValueError("managed_packing_requires_sources")
    result = deepcopy(view)
    result.update(context_format=MANAGED_FORMAT, packing_policy=policy,
                  packing_notice=MANAGED_NOTICE)
    catalog, seen, compact = {}, {}, []
    for row in rows:
        if (not isinstance(row, dict) or "source" in row or "lines" in row
                or not isinstance(row.get("ref"), str)
                or not isinstance(row.get("text"), str)):
            raise ValueError("invalid_managed_source")
        names = ("path", "section") if policy == "sections-v1" else ("path",)
        common = {name: deepcopy(row[name]) for name in names if name in row}
        key = canonical(common)
        if key not in seen:
            ident = "d" + str(len(catalog) + 1)
            seen[key] = ident
            catalog[ident] = common
        item = {name: deepcopy(value) for name, value in row.items() if name not in common}
        item["source"] = seen[key]
        if "line_start" in item and "line_end" in item:
            item["lines"] = [item.pop("line_start"), item.pop("line_end")]
        compact.append(item)
    result["source_catalog"] = catalog
    result["sources"] = compact
    return result


def unpack_managed_model_input(view: dict) -> dict:
    """Decode the model representation. The session, not this decoder, owns refs.

    This is not a source-read/citation authorization function. The caller must
    still call ModelContextSession.resolve on a retained exact source ref.
    """
    if not isinstance(view, dict):
        raise ValueError("invalid_managed_model_input")
    if not _MANAGED_RESERVED.intersection(view):
        return deepcopy(view)
    if (view.get("context_format") != MANAGED_FORMAT
            or view.get("packing_policy") not in POLICIES
            or view.get("packing_notice") != MANAGED_NOTICE
            or not isinstance(view.get("source_catalog"), dict)
            or not isinstance(view.get("sources"), list)):
        raise ValueError("invalid_managed_packed_view")
    catalogue = view["source_catalog"]
    originals, visited = [], set()
    for row in view["sources"]:
        if not isinstance(row, dict) or not isinstance(row.get("source"), str):
            raise ValueError("invalid_managed_packed_source")
        code = row["source"]
        meta = catalogue.get(code)
        if not isinstance(meta, dict) or set(meta) - {"path", "section"}:
            raise ValueError("invalid_managed_catalogue")
        visited.add(code)
        item = {k: deepcopy(v) for k, v in row.items() if k not in {"source", "lines"}}
        if set(item).intersection(meta) or "line_start" in item and "lines" in row:
            raise ValueError("invalid_managed_source_collision")
        item.update(deepcopy(meta))
        if "lines" in row:
            span = row["lines"]
            if (not isinstance(span, list) or len(span) != 2
                    or any(type(value) is not int or value < 1 for value in span)
                    or span[0] > span[1] or "line_end" in item):
                raise ValueError("invalid_managed_line_span")
            item["line_start"], item["line_end"] = span
        originals.append(item)
    if visited != set(catalogue):
        raise ValueError("unused_or_malformed_managed_catalogue")
    result = {k: deepcopy(v) for k, v in view.items()
              if k not in _MANAGED_RESERVED and k != "sources"}
    result["sources"] = originals
    # Reject noncanonical packed inputs; prevents hidden/colliding/extra fields.
    if canonical(_pack_managed(result, view["packing_policy"])) != canonical(view):
        raise ValueError("managed_view_not_canonical")
    return result


def pack_managed_model_input(view: dict, *, policy: str = "adaptive-v1") -> dict:
    """Host-managed counterpart of adaptive-v1: never enlarge a single input.

    Use the identical source identity and issued short refs. For multiple source
    rows compare whole serialized representations, including catalogue cost.
    For smaller inputs or hostile/ineligible content retain the original form.
    """
    if policy not in MANAGED_MODES:
        raise ValueError("unknown_managed_packing_policy")
    if policy == "off" or not isinstance(view, dict) or not view.get("sources"):
        return deepcopy(view)
    original = _cost(view)
    if policy in POLICIES:
        packed = _pack_managed(view, policy)
        if _cost(packed)[2] > 12000:
            raise ValueError("managed_packing_output_limit")
        return packed
    variants = [(original, 0, view)]
    for index, candidate_mode in enumerate(POLICIES, 1):
        candidate = _pack_managed(view, candidate_mode)
        cost = _cost(candidate)
        if all(after <= before for after, before in zip(cost, original)):
            variants.append((cost, index, candidate))
    best = deepcopy(min(variants, key=lambda item: (item[0], item[1]))[2])
    if best is not view and canonical(unpack_managed_model_input(best)) != canonical(view):
        raise ValueError("managed_packing_integrity_mismatch")
    return best
