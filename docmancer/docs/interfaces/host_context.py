"""Host-side evidence delivery and bounded, explicitly requested source reads.

This module neither generates answers nor certifies semantic coverage. A host
decides which requested fact is missing; this boundary controls its source I/O.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Callable, Any

from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens


class EvidenceDeliveryError(ValueError):
    pass


def extract_tool_payload(result: Any, *, structured_supported: bool = True) -> dict:
    """Consume the evidence once, or diagnose an unsupported delivery channel."""
    value = result.model_dump() if hasattr(result, 'model_dump') else result
    if not isinstance(value, dict):
        raise EvidenceDeliveryError('invalid_tool_result')
    structured = value.get('structuredContent')
    if isinstance(structured, dict):
        if not structured_supported:
            raise EvidenceDeliveryError('structured_evidence_unsupported: configure DOCATLAS_MCP_TEXT_FALLBACK=1')
        return deepcopy(structured)
    candidates = []
    for block in value.get('content') or ():
        if not isinstance(block, dict) or block.get('type') != 'text':
            continue
        try:
            payload = json.loads(block.get('text', ''))
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and 'status' in payload:
            candidates.append(payload)
    if len(candidates) != 1:
        raise EvidenceDeliveryError('missing_or_ambiguous_evidence_channel')
    return candidates[0]


class SourceReadController:
    """Per-question read budget, restricted to locators in returned evidence."""

    def __init__(self, context: dict, *, requested_facts: dict[str, str], read_resource: Callable[[str], dict]):
        if (context.get('kind') != 'docs_context' or len(context.get('sources') or ()) > 3
            or docs_context_budget_tokens(context) > 800):
            raise ValueError('source reads require bounded docs_context')
        if not 1 <= len(requested_facts) <= 3 or any(
            not isinstance(value, str) or not value.strip() or len(value) > 500
            for value in requested_facts.values()
        ):
            raise ValueError('declare one to three requested facts before reading')
        self.requested_facts = dict(requested_facts)
        self.supported_facts: set[str] = set()
        self._read_resource = read_resource
        self._allowed = {
            source['source_uri']: {
                'path': source['path_or_url'], 'project_identity': source['project_identity'],
                'line_end': source['line_end'], 'content_sha256': None,
            }
            for source in context.get('sources') or ()
            if isinstance(source, dict) and isinstance(source.get('source_uri'), str)
            and re.fullmatch(r'docatlas://source/[0-9a-f]{24}', source['source_uri'])
            and type(source.get('line_end')) is int and source['line_end'] > 0
        }
        self._seen_uris: set[str] = set()
        # Different locators can refer to overlapping sections of one file.
        # Citation hashes describe snippets, not file snapshots, so initial
        # intervals use an unknown snapshot and conservatively match any read.
        self._seen_spans: list[tuple[str, str, str | None, int, int]] = [
            (source.get('project_identity'), source.get('path_or_url'), None,
             source['line_start'], source['line_end'])
            for source in context.get('sources') or ()
            if isinstance(source, dict) and type(source.get('line_start')) is int
            and type(source.get('line_end')) is int
            and 0 < source['line_start'] <= source['line_end']
        ]
        self._seen_text = {' '.join(str(source.get('snippet') or '').split())
                           for source in context.get('sources') or () if isinstance(source, dict)}
        self.read_attempts = 0
        self.extra_tokens = 0
        self.results: list[dict] = []

    def mark_supported(self, fact_id: str) -> None:
        """Record a host judgment, never a server proof of semantic support."""
        if fact_id not in self.requested_facts:
            raise ValueError('unknown requested fact')
        self.supported_facts.add(fact_id)

    def read(self, uri: str, *, missing_fact_id: str) -> dict:
        if missing_fact_id not in self.requested_facts or missing_fact_id in self.supported_facts:
            return self._stop('no_concrete_missing_fact')
        if self.read_attempts >= 2:
            return self._stop('read_budget_exhausted')
        if uri in self._seen_uris or uri not in self._allowed:
            return self._stop('unknown_or_repeated_source')
        expected = self._allowed.pop(uri)
        self._seen_uris.add(uri)
        self.read_attempts += 1
        result = self._read_resource(uri)
        if not isinstance(result, dict) or docs_context_budget_tokens(result) > 600:
            return self._stop('invalid_or_oversized_read')
        self.extra_tokens += docs_context_budget_tokens(result)
        if result.get('status') not in {'complete', 'truncated'} or not result.get('snippet'):
            return self._stop(str(result.get('reason_code') or 'source_unavailable'))
        start, end = result.get('line_start'), result.get('line_end')
        if (type(start) is not int or type(end) is not int or start != expected['line_end'] + 1
            or end < start or end - start >= 40 or result.get('path') != expected['path']
            or result.get('project_identity') != expected['project_identity']
            or not isinstance(result.get('snippet'), str)
            or not isinstance(result.get('content_sha256'), str)
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', result['content_sha256'])
            or (expected['content_sha256'] and result['content_sha256'] != expected['content_sha256'])):
            return self._stop('source_binding_mismatch')
        if any(project == result['project_identity'] and path == result['path']
               and (digest is None or digest == result['content_sha256'])
               and start <= seen_end and seen_start <= end
               for project, path, digest, seen_start, seen_end in self._seen_spans):
            return self._stop('repeated_source_span')
        text = ' '.join(str(result['snippet']).split())
        if not text or text in self._seen_text:
            return self._stop('no_new_source_text')
        self._seen_text.add(text)
        self._seen_spans.append((result['project_identity'], result['path'],
                                 result['content_sha256'], start, end))
        self.results.append(deepcopy(result))
        continuation = result.get('continuation')
        if isinstance(continuation, str) and re.fullmatch(r'docatlas://source/[0-9a-f]{24}', continuation):
            self._allowed[continuation] = {**expected, 'line_end': end,
                                            'content_sha256': result['content_sha256']}
        return deepcopy(result)

    @staticmethod
    def _stop(reason: str) -> dict:
        return {'status': 'stopped', 'reason_code': reason}
