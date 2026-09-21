"""Verify prepared owner bytes against the current source, without I/O.

Catalog membership is source eligibility, never a package/namespace certificate.
Only the current body and its actual structural owner can supply subject context.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
from typing import Any, Mapping

from docmancer.core.structured_chunking import parse_markdown_parents


@lru_cache(maxsize=16)
def _document_structure(raw: str, document_id: str):
    # Cache immutable parsing inputs, not an approval. Scope/hash/window checks
    # below are performed on every call, including replay and cropped snippets.
    return (hashlib.sha256(raw.encode('utf-8')).hexdigest(),
            tuple(parse_markdown_parents(raw, document_id)))


def prepared_owner_rejection(evidence: Mapping[str, Any]) -> str | None:
    """Check source window and structural owner, rejecting malformed claims."""
    raw = evidence.get('raw_document')
    identity = evidence.get('source') or {}
    if not isinstance(raw, str) or not isinstance(identity, Mapping):
        return 'subject_binding_unavailable'
    digest, parents = _document_structure(raw, str(identity.get('document_id') or ''))
    if digest != identity.get('content_sha256'):
        return 'reference_raw_content_mismatch'
    start, end = evidence.get('char_start'), evidence.get('char_end')
    if (type(start) is not int or type(end) is not int
            or not 0 <= start <= end <= len(raw)
            or raw[start:end] != evidence.get('text')):
        return 'reference_raw_window_mismatch'
    owner = evidence.get('owner')
    if owner is None:
        return None
    if not isinstance(owner, Mapping):
        return 'invalid_subject_owner'
    owners = [p for p in parents if p.char_start <= start and end <= p.char_end]
    if len(owners) != 1:
        return 'ambiguous_subject_owner'
    parent = owners[0]
    header = raw[parent.char_start:parent.char_end].splitlines(keepends=True)[0] if parent.level else ''
    expected = {'text': header, 'char_start': parent.char_start,
                'char_end': parent.char_start + len(header),
                'scope_start': parent.char_start, 'scope_end': parent.char_end,
                'logical_id': parent.logical_id}
    if any(owner.get(key) != value for key, value in expected.items()):
        return 'invalid_subject_owner'
    return None
