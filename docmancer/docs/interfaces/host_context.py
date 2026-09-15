"""Host-side evidence delivery and bounded, explicitly requested source reads.

This module neither generates answers nor certifies semantic coverage. A host
decides which requested fact is missing; this boundary controls its source I/O.
"""
from __future__ import annotations

from copy import deepcopy
import json
import inspect
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
        self._allowed: dict[str, dict[str, Any]] = {}
        for source in context.get('sources') or ():
            if (not isinstance(source, dict) or not isinstance(source.get('source_uri'), str)
                or not re.fullmatch(r'docatlas://source/[0-9a-f]{24}', source['source_uri'])
                or type(source.get('line_end')) is not int or source['line_end'] <= 0):
                continue
            self._allow_reference(source['source_uri'], {
                'mode': 'forward',
                'path': source.get('path_or_url'),
                'project_identity': source.get('project_identity'),
                'line_end': source['line_end'],
                'content_sha256': None,
            })
        for target in context.get('read_next') or ():
            if not self._valid_range_target(target):
                continue
            self._allow_reference(target['source_uri'], {
                'mode': 'range',
                'path': target['path'],
                'project_identity': target['project_identity'],
                'line_start': target['line_start'],
                'line_end': target['line_end'],
                'snapshot_sha256': target['snapshot_sha256'],
            })
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


    def _allow_reference(self, uri: str, expected: dict[str, Any]) -> None:
        """Register one opaque capability, failing closed on ambiguous reuse."""
        current = self._allowed.get(uri)
        if current is None:
            self._allowed[uri] = expected
        elif current != expected:
            self._allowed.pop(uri, None)

    @staticmethod
    def _valid_range_target(target: Any) -> bool:
        return bool(
            isinstance(target, dict)
            and isinstance(target.get('source_uri'), str)
            and re.fullmatch(r'docatlas://source/[0-9a-f]{24}', target['source_uri'])
            and isinstance(target.get('path'), str) and target['path']
            and isinstance(target.get('project_identity'), str) and target['project_identity']
            and type(target.get('line_start')) is int and type(target.get('line_end')) is int
            and 0 < target['line_start'] <= target['line_end']
            and isinstance(target.get('snapshot_sha256'), str)
            and re.fullmatch(r'sha256:[0-9a-f]{64}', target['snapshot_sha256'])
        )

    def mark_supported(self, fact_id: str) -> None:
        """Record a host judgment, never a server proof of semantic support."""
        if fact_id not in self.requested_facts:
            raise ValueError('unknown requested fact')
        self.supported_facts.add(fact_id)

    def _begin_read(self, uri: str, missing_fact_id: str):
        if missing_fact_id not in self.requested_facts or missing_fact_id in self.supported_facts:
            return None, self._stop('no_concrete_missing_fact')
        if self.read_attempts >= 2:
            return None, self._stop('read_budget_exhausted')
        if uri in self._seen_uris or uri not in self._allowed:
            return None, self._stop('unknown_or_repeated_source')
        expected = self._allowed.pop(uri)
        self._seen_uris.add(uri)
        self.read_attempts += 1
        return expected, None

    def read(self, uri: str, *, missing_fact_id: str) -> dict:
        expected, stopped = self._begin_read(uri, missing_fact_id)
        if stopped:
            return stopped
        try:
            result = self._read_resource(uri)
        except Exception:
            return self._stop('source_read_failed')
        return self._accept_read(result, expected)

    async def aread(self, uri: str, *, missing_fact_id: str) -> dict:
        """Authorize before I/O; apply the same boundary to async MCP clients."""
        expected, stopped = self._begin_read(uri, missing_fact_id)
        if stopped:
            return stopped
        try:
            result = self._read_resource(uri)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            return self._stop('source_read_failed')
        return self._accept_read(result, expected)

    def _accept_read(self, result: dict, expected: dict) -> dict:
        if not isinstance(result, dict) or docs_context_budget_tokens(result) > 600:
            return self._stop('invalid_or_oversized_read')
        self.extra_tokens += docs_context_budget_tokens(result)
        if result.get('status') not in {'complete', 'truncated'} or not result.get('snippet'):
            return self._stop(str(result.get('reason_code') or 'source_unavailable'))
        start, end = result.get('line_start'), result.get('line_end')
        digest = result.get('content_sha256')
        if (type(start) is not int or type(end) is not int or end < start or end - start >= 40
            or result.get('path') != expected['path']
            or result.get('project_identity') != expected['project_identity']
            or not isinstance(result.get('snippet'), str)
            or not isinstance(digest, str)
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)):
            return self._stop('source_binding_mismatch')

        mode = expected.get('mode', 'forward')
        if mode == 'range':
            if (start != expected.get('line_start') or end > expected.get('line_end', -1)
                or digest != expected.get('snapshot_sha256')):
                return self._stop('source_binding_mismatch')
            if not self._range_adds_unseen_lines(
                result['project_identity'], result['path'], digest, start, end,
            ):
                return self._stop('repeated_source_span')
        else:
            if (start != expected['line_end'] + 1
                or (expected.get('content_sha256') and digest != expected['content_sha256'])):
                return self._stop('source_binding_mismatch')
            if self._overlaps_seen(
                result['project_identity'], result['path'], digest, start, end,
            ):
                return self._stop('repeated_source_span')

        text = ' '.join(str(result['snippet']).split())
        if not text or text in self._seen_text:
            return self._stop('no_new_source_text')
        self._seen_text.add(text)
        self._seen_spans.append((result['project_identity'], result['path'], digest, start, end))
        self.results.append(deepcopy(result))
        continuation = result.get('continuation')
        if isinstance(continuation, str) and re.fullmatch(r'docatlas://source/[0-9a-f]{24}', continuation):
            if mode == 'range':
                if end < expected['line_end']:
                    self._allow_reference(continuation, {
                        **expected, 'line_start': end + 1,
                    })
            else:
                self._allow_reference(continuation, {
                    **expected, 'line_end': end, 'content_sha256': digest,
                })
        return deepcopy(result)

    def _overlaps_seen(
        self, project: str, path: str, digest: str, start: int, end: int,
    ) -> bool:
        return any(
            seen_project == project and seen_path == path
            and (seen_digest is None or seen_digest == digest)
            and start <= seen_end and seen_start <= end
            for seen_project, seen_path, seen_digest, seen_start, seen_end in self._seen_spans
        )

    def _range_adds_unseen_lines(
        self, project: str, path: str, digest: str, start: int, end: int,
    ) -> bool:
        """Return whether a registered target contributes any unseen source line."""
        intervals = sorted(
            (seen_start, seen_end)
            for seen_project, seen_path, seen_digest, seen_start, seen_end in self._seen_spans
            if seen_project == project and seen_path == path
            and (seen_digest is None or seen_digest == digest)
            and seen_end >= start and seen_start <= end
        )
        cursor = start
        for seen_start, seen_end in intervals:
            if seen_end < cursor:
                continue
            if seen_start > cursor:
                return True
            cursor = max(cursor, seen_end + 1)
            if cursor > end:
                return False
        return cursor <= end

    @staticmethod
    def _stop(reason: str) -> dict:
        return {'status': 'stopped', 'reason_code': reason}
