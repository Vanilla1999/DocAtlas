"""Conservative parent-context delivery from an already verified source snapshot.

Search and qualification select the seed. This module can grow its citation to
its complete Markdown section and append a short document introduction. Related
text is context, not an independently matched query or answer/edit authority.
It performs no search, file read, query rewrite, or source-policy relaxation.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any

from docmancer.core.structured_chunking import _atom_spans, parse_markdown_parents
from docmancer.docs.domain.evidence_qualification import evidence_policy_rejection_reason
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe
from .model_visible_projection import (
    DOCS_CONTEXT_MAX_TOKENS, MAX_DOCS_SOURCES, _docs_source, _refresh_estimate, _snapshot_entry,
    docs_context_budget_tokens,
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
    while end > start and raw[end - 1].isspace():
        end -= 1
    if end <= start:
        return None
    text = raw[start:end]
    new = deepcopy(original)
    new.update(content=text, display_text=text, snippet=text, char_start=start, char_end=end,
               line_start=raw.count('\n', 0, start) + 1,
               line_end=raw.count('\n', 0, end) + 1,
               heading_path=' > '.join(parent.heading_path), title=parent.title)
    # Rebind exact canonical bytes; never concatenate disjoint quotes or reuse
    # the old child boundary to certify a larger span.
    header = raw[parent.char_start:parent.char_end].splitlines(keepends=True)[0] if parent.level else ''
    new['_reference_evidence'].update(char_start=start, char_end=end, text=text, owner={
        'text': header, 'char_start': parent.char_start,
        'char_end': parent.char_start + len(header),
        'scope_start': parent.char_start, 'scope_end': parent.char_end,
        'logical_id': parent.logical_id,
    })
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
    row.update({key: new.get(key, public.get(key)) for key in
                ('project_identity', 'line_start', 'line_end', 'authority', 'scope')})
    if supplementary:
        new['_assigned_requirement_ids'] = []
        new['retrieval_query_matches'] = {}
        new['retrieval_query_ids'] = []
    # Coverage/assignments for retained evidence are intentionally NOT expanded.
    # The seed ID is opaque and retained; its digest and snapshot are recomputed.
    return row, new


def expand_structural_context(
    payload: dict, snapshot: dict, *, max_tokens: int, project_root: str = "",
    diagnostics: list | None = None,
) -> tuple[dict, dict]:
    """Keep all existing quotes and capabilities; spend spare space on structure.

    Empty/answered/checked packets and sources without a verified immutable
    reference snapshot are unchanged. The work is bounded by the source cap and
    a per-document size cap. Extra introductory quotes receive no query credit.
    """
    if (payload.get('kind') != 'docs_context'
            or payload.get('support_status') != 'retrieval_only'
            or any(payload.get(key) is not False for key in ('answer_supported', 'answer_available', 'edit_ready'))
            or (payload.get('context_quality') or {}).get('status') == 'checked'
            or not payload.get('sources') or len(payload['sources']) > MAX_DOCS_SOURCES):
        return payload, snapshot
    max_tokens = min(max_tokens, DOCS_CONTEXT_MAX_TOKENS)
    result, bindings = deepcopy(payload), deepcopy(snapshot)
    for seed in tuple(payload['sources']):
        original = (snapshot.get(seed['evidence_id']) or {}).get('source')
        if not isinstance(original, dict):
            continue
        raw = _verified_document(original, seed)
        if raw is None:
            continue
        ref = original['_reference_evidence']
        parents = parse_markdown_parents(raw, ref['source']['document_id'])
        if not parents or len(parents) > MAX_PARENT_SECTIONS:
            continue
        owner = next((p for p in parents if p.char_start <= ref['char_start'] <= ref['char_end'] <= p.char_end), None)
        if owner is None:
            continue
        options = [(owner.char_start, owner.char_end, owner, False)]
        first = parents[0]
        is_document_parent = first.level == 0 or (
            first.level == 1 and len(owner.heading_path) > len(first.heading_path)
            and owner.heading_path[:len(first.heading_path)] == first.heading_path)
        if first.char_start == 0 and first.logical_id != owner.logical_id and is_document_parent:
            atoms = _atom_spans(raw, first.char_start, first.char_end)
            first_body = next((a for a in atoms if a.atom_type != 'heading' and raw[a.start:a.end].strip()), None)
            if first_body and first_body.atom_type == 'prose':
                options.append((first.char_start, first_body.end, first, True))
        for start, end, parent, supplementary in options:
            proposal = _context_row(original, seed, raw, parent, start, end, supplementary=supplementary)
            if proposal is None:
                continue
            row, new = proposal
            # Existing capabilities are commitments, not free context space.
            # Keep their forward boundary and don't pre-consume a promised range.
            if (not supplementary and seed.get('source_uri')
                    and row['line_end'] != seed['line_end']):
                continue
            if any(target.get('path') == row['path_or_url']
                   and row['line_start'] <= target.get('line_end', 0)
                   and target.get('line_start', 0) <= row['line_end']
                   for target in payload.get('read_next') or ()):
                continue
            if not supplementary and seed.get('source_uri'):
                from .source_continuation import source_continuation_uri
                uri = source_continuation_uri(project_root, new)
                if not uri:
                    continue
                row['source_uri'] = uri
            text = row['snippet']
            same_document = [s for s in result['sources'] if s['path_or_url'] == row['path_or_url']]
            if any(text in s['snippet'] for s in same_document):
                continue
            if supplementary:
                if len(result['sources']) >= MAX_DOCS_SOURCES:
                    continue
            elif seed['snippet'] not in text or any(
                s['evidence_id'] != seed['evidence_id'] and s['snippet'] in text for s in same_document
            ):
                continue
            trial = deepcopy(result)
            if supplementary:
                trial['sources'].append(row)
            else:
                trial['sources'] = [row if s['evidence_id'] == seed['evidence_id'] else s for s in trial['sources']]
            _refresh_estimate(trial)
            cost = docs_context_budget_tokens(trial)
            if diagnostics is not None and len(diagnostics) < 12:
                diagnostics.append({'seed_id': seed['evidence_id'],
                    'kind': 'document_introduction' if supplementary else 'containing_section',
                    'decision': 'accepted' if cost <= max_tokens else 'token_budget',
                    'line_start': row['line_start'], 'line_end': row['line_end'], 'budget_tokens': cost})
            if cost <= max_tokens:
                result = trial
                bindings[row['evidence_id']] = _snapshot_entry(new, row)
    return result, bindings
