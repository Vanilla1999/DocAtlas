"""Existing canonical payload audit, independent of labels and semantic review."""
from __future__ import annotations
from pathlib import Path
from contextlib import nullcontext
from docmancer.docs.domain.read_delivery_limits import ReadDeliveryLimits, use_read_delivery_limits
from docmancer.docs.domain.source_coordinates import source_line_text


def audit_payload(payload: dict, snapshot: dict, root: Path, *,
                  delivery_limits: ReadDeliveryLimits | None = None) -> list[str]:
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    # The manifest/caller selects the policy; payload fields cannot relax it.
    with use_read_delivery_limits(delivery_limits) if delivery_limits is not None else nullcontext():
        errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    for source in payload.get('sources') or []:
        path = (root / str(source.get('path_or_url') or '')).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append('source escapes the isolated corpus')
            continue
        text = path.read_bytes().decode('utf-8')
        start, end = source.get('line_start'), source.get('line_end')
        snippet = str(source.get('snippet') or '')
        try:
            claimed_text = source_line_text(text, start, end)
        except ValueError:
            errors.append('invalid source line range')
        else:
            if snippet not in claimed_text:
                errors.append('source span does not occur inside claimed line range')
        if not snippet or snippet not in text:
            errors.append('noncontiguous or nonexistent source snippet')
        if payload.get('kind') == 'docs_context' and any(payload.get(k) is not False for k in ('answer_supported','answer_available','edit_ready')):
            errors.append('retrieval-only flag violation')
    return errors


