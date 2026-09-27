"""Exact canonical containment for coalescing unissued citations.

This does not change the existing retention contract for already visible rows.
Only a draft packet can replace two citations by one same-snapshot superset.
"""
from __future__ import annotations

import json
from .joint_context_candidates import _verified_document


def _occurrence(row: dict, snapshot: dict):
    source = (snapshot.get(row.get("evidence_id")) or {}).get("source")
    if not isinstance(source, dict):
        return None
    raw = _verified_document(source, row)
    if raw is None:
        return None
    ref = source["_reference_evidence"]
    text = row.get("snippet")
    if not isinstance(text, str) or not text:
        return None
    a, b = ref.get("char_start"), ref.get("char_end")
    if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(raw):
        return None
    start = raw.find(text, a, b)
    if start < 0 or raw.find(text, start + 1, b) >= 0:
        # Equal words at ambiguous occurrences are not a lineage proof.
        return None
    identity = json.dumps({
        "reference": ref["source"],
        "source": {k: source.get(k) for k in (
            "project_identity", "_source_snapshot_sha256", "_source_catalog_hash",
            "resolved_version", "generation_id", "doc_scope", "module_path",
        )},
        "public": {k: row.get(k) for k in (
            "project_identity", "path_or_url", "version_binding", "authority",
            "scope", "instruction_trust",
        )},
    }, sort_keys=True)
    return identity, start, start + len(text)


def retained_seed_mapping(previous: dict, previous_snapshot: dict,
                          trial: dict, trial_snapshot: dict) -> dict[str, str]:
    """Map every old occurrence to its validated containing draft citation.

    Empty means failure, not partial success. Policy and query coverage must be
    independently checked by the caller after these canonical bounds match.
    """
    candidates = [(row, _occurrence(row, trial_snapshot)) for row in trial.get("sources") or ()]
    mapping: dict[str, str] = {}
    for old in previous.get("sources") or ():
        occurrence = _occurrence(old, previous_snapshot)
        if occurrence is None:
            return {}
        identity, a, b = occurrence
        containing = [row for row, current in candidates if current is not None
                      and current[0] == identity and current[1] <= a < b <= current[2]]
        if not containing:
            return {}
        same = next((row for row in containing if row["evidence_id"] == old["evidence_id"]), containing[0])
        mapping[old["evidence_id"]] = same["evidence_id"]
    return mapping
