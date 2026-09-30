"""Existing canonical payload audit, independent of labels and semantic review."""
from __future__ import annotations
from pathlib import Path


def audit_payload(payload: dict, snapshot: dict, root: Path) -> list[str]:
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    for source in payload.get('sources') or []:
        path = (root / str(source.get('path_or_url') or '')).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append('source escapes the isolated corpus')
            continue
        text = path.read_text(encoding='utf-8')
        start, end = source.get('line_start'), source.get('line_end')
        snippet = str(source.get('snippet') or '')
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            errors.append('invalid source line range')
        elif snippet not in '\n'.join(text.splitlines()[start-1:end]):
            errors.append('source span does not occur inside claimed line range')
        if not snippet or snippet not in text:
            errors.append('noncontiguous or nonexistent source snippet')
        if payload.get('kind') == 'docs_context' and any(payload.get(k) is not False for k in ('answer_supported','answer_available','edit_ready')):
            errors.append('retrieval-only flag violation')
    return errors


