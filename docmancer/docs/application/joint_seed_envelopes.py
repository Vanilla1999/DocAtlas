"""Canonical hulls of multiple draft quotes within one authenticated section.

No question terms or answer labels enter this generator. It proposes the exact
contiguous span between existing occurrences, optionally with the immediately
preceding prose block. Normal policy, lineage, budget and coverage checks apply.
"""
from docmancer.core.structured_chunking import parse_markdown_parents
from .joint_context_candidates import (
    MAX_PARENT_SECTIONS, _context_row, _verified_document, structural_spans,
)


def seed_envelopes(payload: dict, snapshot: dict) -> list[tuple[int, tuple]]:
    groups: dict[tuple, list] = {}
    for index, row in enumerate(payload.get("sources", [])):
        source = (snapshot.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(source, dict):
            continue
        raw = _verified_document(source, row)
        if raw is None:
            continue
        ref = source["_reference_evidence"]
        start = raw.find(row["snippet"], ref["char_start"], ref["char_end"])
        end = start + len(row["snippet"])
        parents = parse_markdown_parents(raw, ref["source"]["document_id"])
        if len(parents) > MAX_PARENT_SECTIONS:
            continue
        owner = next((p for p in parents if p.char_start <= start < end <= p.char_end), None)
        if owner is None:
            continue
        key = (row["project_identity"], row["path_or_url"], source.get("_source_snapshot_sha256"),
               source.get("_source_catalog_hash"), source.get("resolved_version"), owner.logical_id)
        groups.setdefault(key, []).append((index, row, source, raw, owner, start, end))
    result = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        index, row, source, raw, owner, _, _ = rows[0]
        if any(item[3] != raw for item in rows):
            continue
        atoms = [a for a in structural_spans(raw, owner.char_start, owner.char_end) if a[2] != "whitespace"]
        left, right = min(item[5] for item in rows), max(item[6] for item in rows)
        hits = [i for i, (a, z, _) in enumerate(atoms) if a < right and left < z]
        if not hits:
            continue
        start, end = min(left, atoms[hits[0]][0]), max(right, atoms[hits[-1]][1])
        bounds = [(start, end)]
        if hits[0] > 0 and atoms[hits[0] - 1][2] == "prose":
            bounds.append((atoms[hits[0] - 1][0], end))
        seen = {row["snippet"]}
        for a, z in bounds:
            proposal = _context_row(source, row, raw, owner, a, z, supplementary=False)
            if proposal is not None and proposal[0]["snippet"] not in seen:
                seen.add(proposal[0]["snippet"])
                result.append((index, (*proposal, "seed_envelope")))
    return result
