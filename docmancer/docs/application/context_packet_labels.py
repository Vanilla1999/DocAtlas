"""Lossless factoring of repeated display breadcrumbs in one unissued packet.

Canonical source headings, quote bytes, identities and capabilities are unchanged.
At least one full breadcrumb remains per authenticated document; only a shared
prefix already displayed by that representative can be omitted on another row.
"""
from collections import defaultdict
from copy import deepcopy

from .joint_context_candidates import _verified_document
from .model_visible_projection import _refresh_estimate, _snapshot_entry


def compact_section_labels(payload: dict, snapshot: dict) -> tuple[dict, dict]:
    p, bindings = deepcopy(payload), deepcopy(snapshot)
    groups = defaultdict(list)
    for index, row in enumerate(p.get("sources", [])):
        original = (bindings.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(original, dict) or _verified_document(original, row) is None:
            continue
        label = row.get("section")
        if not isinstance(label, str) or label != str(original.get("heading_path") or original.get("title") or "document").strip():
            continue
        key = (row.get("project_identity"), row.get("path_or_url"),
               row.get("version_binding"), original.get("_source_snapshot_sha256"))
        groups[key].append((index, tuple(label.split(" > "))))
    for rows in groups.values():
        if len(rows) < 2:
            continue
        # A document introduction is the natural shared ancestor when present.
        anchor_index, anchor = min(rows, key=lambda item: (len(item[1]), item[0]))
        for index, parts in rows:
            if index == anchor_index:
                continue
            shared = 0
            for a, b in zip(anchor, parts):
                if a != b:
                    break
                shared += 1
            shared = min(shared, len(parts) - 1)
            if not shared:
                continue
            suffix = parts[shared:]
            # Do not make two distinct section paths indistinguishable.
            if any(other != parts and other[-len(suffix):] == suffix for _, other in rows):
                continue
            row = p["sources"][index]
            row["section"] = " > ".join(suffix)
            source = bindings[row["evidence_id"]]["source"]
            bindings[row["evidence_id"]] = _snapshot_entry(source, row)
    _refresh_estimate(p)
    return p, bindings
