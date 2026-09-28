"""Canonical adjacency coalescing for unissued document-local context drafts."""
from __future__ import annotations

from docmancer.core.structured_chunking import _atom_spans, parse_markdown_parents
from .joint_context_candidates import _context_row
from .context_selection import qualified_query_ids


def bridge_options(seed: dict, original: dict, raw: str, start: int, end: int, retrieval: dict):
    """Bridge only headings/whitespace, never omit intervening source text.

    A cross-section quote has no single local owner. It is rebound to the exact
    document bytes and requalified from its visible body, not an invented owner.
    Already-issued resources are never edited by this draft-only operation.
    """
    ref = original["_reference_evidence"]
    old_start = raw.find(seed["snippet"], ref["char_start"], ref["char_end"])
    if old_start < 0:
        return None
    old_end = old_start + len(seed["snippet"])
    if old_end <= start:
        gap_start, gap_end = old_end, start
    elif end <= old_start:
        gap_start, gap_end = end, old_start
    else:
        return None
    if any(atom.atom_type not in {"heading", "whitespace"}
           for atom in _atom_spans(raw, gap_start, gap_end)):
        return None
    a, z = min(start, old_start), max(end, old_end)
    parents = parse_markdown_parents(raw, ref["source"]["document_id"])
    parent = next((p for p in parents if p.char_start <= a < p.char_end), None)
    if parent is None:
        return None
    proposal = _context_row(original, seed, raw, parent, a, z, supplementary=False)
    if proposal is None:
        return None
    row, source = proposal
    from .docs_context_projection import _requalify_visible_source
    texts = {str(q.get("query_id") or ""): str(q.get("text") or "")
             for q in (retrieval.get("documentation_query_plan") or {}).get("queries", [])
             if isinstance(q, dict)}
    visible = _requalify_visible_source({
        **source, **row, "_qualification_candidate": source,
        "_expected_project_identity": row["project_identity"],
    }, query_text=texts)
    if not qualified_query_ids((original,)) <= qualified_query_ids((visible,)):
        return None
    source.update(retrieval_query_matches=visible["retrieval_query_matches"],
                  retrieval_query_ids=visible["retrieval_query_ids"])
    return row, source
