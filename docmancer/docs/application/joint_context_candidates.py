"""Verified structural alternatives; no question or answer labels in generation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

from docmancer.core.structured_chunking import _atom_spans, parse_markdown_parents
from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
from .model_visible_projection import (
    _docs_source,
)

MAX_SNAPSHOT_CHARS = 262_144
MAX_PARENT_SECTIONS = 4096


def _verified_document(original: dict, public: dict) -> str | None:
    ref = original.get('_reference_evidence')
    if not isinstance(ref, dict):
        return None
    raw = ref.get('raw_document')
    identity = ref.get('source') or {}
    if not isinstance(raw, str) or not raw or len(raw) > MAX_SNAPSHOT_CHARS:
        return None
    if hashlib.sha256(raw.encode('utf-8')).hexdigest() != identity.get('content_sha256'):
        return None
    if public.get('project_identity') != original.get('project_identity'):
        return None
    if public.get('path_or_url') != identity.get('canonical_path'):
        return None
    _, reason = prepare_reference_probe({}, candidate=original, evidence_text=public['snippet'])
    if reason is not None:
        return None
    return raw


def _context_row(original: dict, public: dict, raw: str, parent: Any,
                 start: int, end: int, *, supplementary: bool) -> tuple[dict, dict] | None:
    if end <= start:
        return None
    text = raw[start:end]
    new = deepcopy(original)
    new.update(content=text, display_text=text, snippet=text, char_start=start, char_end=end,
               line_start=raw.count('\n', 0, start) + 1,
               line_end=raw.count('\n', 0, end - 1) + 1,
               heading_path=' > '.join(parent.heading_path), title=parent.title)
    # Rebind exact canonical bytes; never concatenate disjoint quotes or reuse
    # the old child boundary to certify a larger span.
    header = raw[parent.char_start:parent.char_end].splitlines(keepends=True)[0] if parent.level else ''
    new['_reference_evidence'].update(char_start=start, char_end=end, text=text, owner={
        'text': header, 'char_start': parent.char_start,
        'char_end': parent.char_start + len(header),
        'scope_start': parent.char_start, 'scope_end': parent.char_end,
        'logical_id': parent.logical_id,
    } if parent.char_start <= start < end <= parent.char_end else None)
    _, reason = prepare_reference_probe({}, candidate=new, evidence_text=text)
    if reason is not None:
        return None
    probes = [value for value in (original.get('retrieval_query_matches') or {}).values()
              if isinstance(value, dict)] or [{}]
    if any(evidence_policy_rejection_reason(
        probe, visible_text=text, catalog_role=str(original.get('catalog_role') or ''),
        candidate=new, expected_project_identity=public['project_identity'],
        lifecycle_intent=original.get('_lifecycle_intent', 'current'),
    ) for probe in probes):
        return None
    row = _docs_source(new, evidence_id=None if supplementary else public['evidence_id'])
    if row is None:
        return None
    # A structural superset must retain every canonical seed byte, including
    # outer LF/CRLF; normalized presentation would invalidate containment.
    row['snippet'] = text
    row.update({key: new.get(key, public.get(key)) for key in
                ('project_identity', 'line_start', 'line_end', 'authority', 'scope')})
    if supplementary:
        new['_assigned_requirement_ids'] = []
        new['retrieval_query_matches'] = {}
        new['retrieval_query_ids'] = []
    # Coverage/assignments for retained evidence are intentionally NOT expanded.
    # The seed ID is opaque and retained; its digest and snapshot are recomputed.
    return row, new

def structural_spans(raw: str, start: int, end: int) -> tuple[tuple[int, int, str], ...]:
    """Coalesce lazy list continuations without changing index chunking.

    A continuation directly after a list marker belongs to that item. A prose
    paragraph after a blank line terminates it. Consecutive items stay one run.
    """
    out: list[tuple[int, int, str]] = []
    for atom in _atom_spans(raw, start, end):
        if out and out[-1][2] == "list":
            a, b, kind = out[-1]
            joined = atom.atom_type == "list" or (
                atom.atom_type == "prose" and not raw[a:b].endswith(("\n\n", "\r\n\r\n"))
            )
            if joined:
                out[-1] = (a, atom.end, kind)
                continue
        out.append((atom.start, atom.end, atom.atom_type))
    return tuple(out)


def source_options(public: dict, original: dict) -> tuple[list[tuple[dict, dict, str]], tuple[dict, dict] | None]:
    """Original plus at most two containing alternatives and one document intro."""
    options = [(deepcopy(public), deepcopy(original), "original")]
    raw = _verified_document(original, public)
    if raw is None:
        return options, None
    ref = original["_reference_evidence"]
    parents = parse_markdown_parents(raw, ref["source"]["document_id"])
    if not parents or len(parents) > MAX_PARENT_SECTIONS:
        return options, None
    start = raw.find(public["snippet"], ref["char_start"], ref["char_end"])
    end = start + len(public["snippet"])
    owner = next((p for p in parents if p.char_start <= start < end <= p.char_end), None)
    if owner is None:
        return options, None
    spans = structural_spans(raw, owner.char_start, owner.char_end)
    hits = [(a, b) for a, b, kind in spans if a < end and start < b and kind != "whitespace"]
    bounds = []
    if hits:
        bounds.append((min(start, hits[0][0]), max(end, hits[-1][1]), "complete_atom"))
    bounds.append((owner.char_start, owner.char_end, "containing_section"))
    seen = {public["snippet"]}
    for a, b, kind in bounds:
        proposal = _context_row(original, public, raw, owner, a, b, supplementary=False)
        if proposal is not None and proposal[0]["snippet"] not in seen:
            seen.add(proposal[0]["snippet"])
            options.append((*proposal, kind))
    intro = None
    first = parents[0]
    is_root = (first.level == 1 and len(owner.heading_path) > len(first.heading_path)
        and owner.heading_path[:len(first.heading_path)] == first.heading_path)
    if first.char_start == 0 and first.logical_id != owner.logical_id and is_root:
        body = next((a for a in _atom_spans(raw, first.char_start, first.char_end)
            if a.atom_type not in {"heading", "whitespace"} and raw[a.start:a.end].strip()), None)
        if body is not None and body.atom_type == "prose":
            intro = _context_row(original, public, raw, first, body.start, body.end, supplementary=True)
    return options, intro
