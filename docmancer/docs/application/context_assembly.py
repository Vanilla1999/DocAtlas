"""Context Assembly: reversible layouts after selection, before MCP delivery.

No retrieval, model calls, evidence pruning or permission changes. The current
standalone object format remains the default until answering-model A/B passes.
All legends, original references and source capabilities stay in the text.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os

BASE = "docatlas.standalone-text.v1"
POLICIES = ("literal", "grouped", "table", "grouped-table", "adaptive")
_FORMATS = {p: f"docatlas.assembled-{p}.v1" for p in POLICIES[1:4]}
_LEGENDS = {
    "grouped": " Source objects inherit path/section from source_groups[group] (zero-based). Shared source_context applies to every source.",
    "table": " Each source array follows source_columns in order. Shared source_context applies to every source.",
    "grouped-table": " Each source array follows source_columns; group indexes source_groups (zero-based) for path/section. Shared source_context applies to every source.",
}
_RESERVED = {"source_groups", "source_columns"}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _cost(text: str) -> int:
    from .projection_tokenizer import projection_token_count
    return projection_token_count(text.encode("utf-8"))


def _group(view: dict) -> dict | None:
    result = deepcopy(view)
    groups, index, rows = [], {}, []
    for row in result["sources"]:
        if "group" in row:
            return None
        common = {k: row[k] for k in ("path", "section") if k in row}
        key = _json(common)
        if key not in index:
            index[key] = len(groups)
            groups.append(common)
        rows.append({"group": index[key], **{k: v for k, v in row.items() if k not in common}})
    result.update(source_groups=groups, sources=rows)
    return result


def _table(view: dict) -> dict | None:
    rows = view["sources"]
    columns = sorted(rows[0])
    # Null and missing are not interchangeable: heterogeneous rows stay objects.
    if any(sorted(row) != columns for row in rows):
        return None
    result = deepcopy(view)
    result["source_columns"] = columns
    result["sources"] = [[row[k] for k in columns] for row in rows]
    return result


def decode_context(view: dict) -> dict:
    """Restore the exact standalone *view*, not a full internal machine packet.

    Decoding is not authorization. Existing source readers still validate URIs,
    expiry, hashes and access. Reject ambiguous/malformed layouts explicitly.
    """
    fmt = view.get("context_format")
    if fmt == BASE:
        return deepcopy(view)
    policy = next((p for p, name in _FORMATS.items() if name == fmt), None)
    if policy is None:
        raise ValueError("unknown_context_assembly_format")
    result = deepcopy(view)
    notice = result.get("notice")
    legend = _LEGENDS[policy]
    if not isinstance(notice, str) or not notice.endswith(legend):
        raise ValueError("context_assembly_missing_legend")
    result["notice"] = notice[:-len(legend)]
    rows = result.get("sources")
    if not isinstance(rows, list) or not rows:
        raise ValueError("context_assembly_invalid_rows")
    if policy in {"table", "grouped-table"}:
        cols = result.pop("source_columns", None)
        if (not isinstance(cols, list) or not cols or
                any(not isinstance(c, str) for c in cols) or len(set(cols)) != len(cols)):
            raise ValueError("context_assembly_invalid_columns")
        if any(not isinstance(row, list) or len(row) != len(cols) for row in rows):
            raise ValueError("context_assembly_row_width")
        rows = [dict(zip(cols, row, strict=True)) for row in rows]
    elif "source_columns" in result:
        raise ValueError("context_assembly_unexpected_columns")
    if policy in {"grouped", "grouped-table"}:
        groups = result.pop("source_groups", None)
        if (not isinstance(groups, list) or not groups or
                any(not isinstance(g, dict) or set(g) - {"path", "section"} for g in groups)):
            raise ValueError("context_assembly_invalid_groups")
        restored = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("context_assembly_invalid_row")
            row = dict(row)
            i = row.pop("group", None)
            if type(i) is not int or not 0 <= i < len(groups) or set(row) & set(groups[i]):
                raise ValueError("context_assembly_invalid_group_reference")
            restored.append({**groups[i], **row})
        rows = restored
    elif "source_groups" in result:
        raise ValueError("context_assembly_unexpected_groups")
    result.update(context_format=BASE, sources=rows)
    return result


def render_layouts(text: str) -> dict[str, str]:
    """Offer reversible candidates with the old representation always present."""
    candidates = {"literal": text}
    if len(text.encode("utf-8")) > 48_000:
        return candidates  # existing full-packet safety boundary, not a new cap
    view = json.loads(text)
    if (not isinstance(view, dict) or view.get("context_format") != BASE or
            view.get("status") not in {"ok", "truncated"} or
            view.get("hard_stop") or view.get("requires_confirmation") or
            any(k in view for k in _RESERVED) or not isinstance(view.get("notice"), str)):
        return candidates
    rows = view.get("sources")
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        return candidates
    original = _json(view)
    grouped = _group(view)
    trials = {"grouped": grouped, "table": _table(view),
              "grouped-table": _table(grouped) if grouped is not None else None}
    for name, trial in trials.items():
        if trial is None:
            continue
        trial["context_format"] = _FORMATS[name]
        trial["notice"] += _LEGENDS[name]
        serialized = _json(trial)
        if max(_cost(serialized), math.ceil(len(serialized.encode("utf-8")) / 4)) > 12000:
            continue
        # Compare canonical bytes, not Python's loose bool/int equality.
        if _json(decode_context(trial)) != original:
            raise ValueError("context_assembly_roundtrip_mismatch")
        candidates[name] = serialized
    return candidates


def assemble_context(text: str, *, policy: str | None = None) -> str:
    """Select a layout only; adaptive minimizes complete o200k text incl. legend.

    Deterministic ties prefer literal, then grouped, table, grouped-table.
    No approximate score cutoff. No assumption that smaller means sufficient.
    """
    policy = policy if policy is not None else os.environ.get("DOCATLAS_CONTEXT_ASSEMBLY", "literal")
    if policy not in POLICIES:
        raise ValueError("invalid_DOCATLAS_CONTEXT_ASSEMBLY")
    if policy == "literal":
        return text
    try:
        candidates = render_layouts(text)
        if policy == "adaptive":
            return min(candidates.values(), key=_cost)
        return candidates.get(policy, text)
    except (ValueError, TypeError, KeyError, IndexError):
        # Optional presentation failure must never remove admitted evidence.
        return text
