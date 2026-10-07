"""Host-side evidence delivery and bounded, explicitly requested source reads.

This module neither generates answers nor certifies semantic coverage. A host
decides which requested fact is missing; this boundary controls its source I/O.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import inspect
import re
from typing import Callable, Any

from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.application.action_packet import (
    estimate_action_packet_tokens,
)
from docmancer.docs.application._action_packet_part04 import _StrictValidator, _restore_dto
from docmancer.docs.application._action_packet_shared import _compact_value
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceAssignment
from docmancer.docs.application.evidence_selection import normalize_candidates, validate_assignment_binding
from docmancer.mcp._docs_server_schema import _PATCH_CONTEXT_OUTPUT_SCHEMA


class EvidenceDeliveryError(ValueError):
    pass


def validate_patch_context_payload(context: dict) -> None:
    """Validate visible v4 bindings, without claiming unseen retrieval authenticity."""
    if not isinstance(context, dict) or context.get('kind') != 'patch_context' or context.get('schema_version') != 4:
        raise EvidenceDeliveryError('invalid_patch_context')
    try:
        if context.get('estimated_tokens') != estimate_action_packet_tokens(context):
            raise EvidenceDeliveryError('patch_context_estimate_mismatch')
        errors = [error.message for error in _StrictValidator(_PATCH_CONTEXT_OUTPUT_SCHEMA).iter_errors(context)]
        if not errors:
            errors = _patch_wire_binding_errors(context)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise EvidenceDeliveryError('invalid_patch_context') from exc
    if errors:
        raise EvidenceDeliveryError('invalid_patch_context: ' + '; '.join(errors))


def _patch_wire_binding_errors(context: dict) -> list[str]:
    """Check exact visible witnesses, never recreate hidden selector metadata."""
    from docmancer.docs.application.model_visible_projection import _patch_recovery_errors

    errors = _patch_recovery_errors(context, context)
    sources = context.get('sources', [])
    by_id = {source['stable_id']: source for source in sources}
    if (len(by_id) != len(sources)
            or len({source['evidence_id'] for source in sources}) != len(sources)):
        errors.append('duplicate source identity')
    for source in sources:
        if hashlib.sha256(source['text'].encode('utf-8')).hexdigest() != source['content_sha256']:
            errors.append('source content hash mismatch')
        for prefix in ('char', 'line'):
            start, end = source.get(prefix + '_start'), source.get(prefix + '_end')
            if (start is None) != (end is None) or (start is not None and end < start):
                errors.append('invalid source span')
        if source.get('char_start') is not None and source['char_end'] - source['char_start'] != len(source['text']):
            errors.append('source character span mismatch')
        if source.get('line_start') is not None and source['line_end'] != source['line_start'] + source['text'].count('\n'):
            errors.append('source newline-window endpoint mismatch')
    requirements = context.get('requirements', [])
    if requirements != [_compact_value(_restore_dto(EvidenceRequirement, row)) for row in requirements]:
        errors.append('requirements differ from canonical DTO serialization')
    by_requirement = {row['requirement_id']: row for row in requirements}
    if len(by_requirement) != len(requirements):
        errors.append('duplicate requirement identity')
    canonical_requirements = tuple(_restore_dto(EvidenceRequirement, row) for row in requirements)
    visible_candidates, _ = normalize_candidates([
        {'stable_id': source['stable_id'], 'path': source['path'],
         'title': source['symbol_or_section'], 'content': source['text'],
         'authority': source['authority'], 'version_binding': source['version_binding'],
         **{key: source[key] for key in ('char_start', 'char_end', 'line_start', 'line_end') if key in source}}
        for source in sources
    ], result_kind='patch_context')
    by_candidate = {candidate.stable_id: candidate for candidate in visible_candidates}
    assignments = context.get('assignments', [])
    if assignments != [_compact_value(_restore_dto(EvidenceAssignment, row)) for row in assignments]:
        errors.append('assignments differ from canonical DTO serialization')
    assigned = [row['requirement_id'] for row in assignments]
    if assigned != sorted(set(assigned)):
        errors.append('assignment identities must be sorted unique')
    for assignment in assignments:
        source = by_id.get(assignment['evidence_id'])
        requirement = by_requirement.get(assignment['requirement_id'])
        if source is None or requirement is None:
            errors.append('unbound assignment identity')
            continue
        # These unit-less bindings depend on metadata absent from the wire.
        # Preserve them as unverified claims, never manufacture candidate fields.
        hidden_binding = assignment.get('unit_id') is None and requirement['kind'] in {
            'project_identity', 'module_id', 'exact_version', 'exact_snapshot',
        }
        if not hidden_binding:
            candidate = by_candidate.get(assignment['evidence_id'])
            if candidate is None or not validate_assignment_binding(
                _restore_dto(EvidenceRequirement, requirement), candidate,
                _restore_dto(EvidenceAssignment, assignment), requirements=canonical_requirements,
            ):
                errors.append('assignment canonical visible witness binding is invalid')
        if (assignment['path'] != source['path']
                or assignment['proof_role'] != requirement.get('proof_role', 'generic_fact')
                or assignment.get('qualifiers', []) != requirement.get('qualifiers', [])):
            errors.append('assignment attribution mismatch')
        text = source['text']
        start, end = assignment.get('unit_char_start'), assignment.get('unit_char_end')
        if assignment.get('unit_id') is not None:
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                errors.append('invalid assignment unit span')
                continue
            witness = text[start:end]
            digest = hashlib.sha256(witness.encode('utf-8')).hexdigest()
            unit_identity = hashlib.sha256(
                f"{assignment.get('unit_kind')}\0{start}\0{end}\0{witness}".encode('utf-8')
            ).hexdigest()
            if (digest != assignment.get('unit_content_hash') or not assignment.get('unit_kind')
                    or assignment['unit_id'] != 'unit-' + unit_identity[:20]):
                errors.append('assignment unit hash mismatch')
            char_start, char_end = (source.get('char_start') or 0) + start, (source.get('char_start') or 0) + end
            line_start = (source.get('line_start') or 0) + text[:start].count('\n')
            line_end = line_start + witness.count('\n')
        else:
            if any(assignment.get(key) is not None for key in (
                    'unit_kind', 'unit_char_start', 'unit_char_end', 'unit_content_hash')):
                errors.append('orphan assignment unit fields')
            digest = source['content_sha256']
            char_start, char_end = source.get('char_start'), source.get('char_end')
            line_start = source.get('line_start')
            line_end = line_start + text.count('\n') if line_start is not None else None
        if (assignment['projected_content_hash'] != digest
                or any(assignment.get(key) != value for key, value in (
                    ('char_start', char_start), ('char_end', char_end),
                    ('line_start', line_start), ('line_end', line_end)))):
            errors.append('assignment visible witness binding mismatch')
        for prefix in ('char', 'line'):
            source_start, source_end = source.get(prefix + '_start'), source.get(prefix + '_end')
            start, end = assignment.get(prefix + '_start'), assignment.get(prefix + '_end')
            if source_start is not None and (start is None or end is None
                    or not source_start <= start <= end <= source_end):
                errors.append('assignment escapes source window')
    if context['completeness'] == 'complete':
        mandatory = {row['requirement_id'] for row in requirements if row.get('mandatory', True)}
        if mandatory - set(assigned) or not any(row.get('unit_id') for row in assignments):
            errors.append('complete data lacks mandatory visible assignments')
    if context.get('missing', []) != sorted(set(context.get('missing', []))):
        errors.append('missing reasons must be sorted unique')
    mutation = context.get('mutation_intent') or {}
    if mutation:
        from docmancer.docs.application._action_packet_part03 import _mutation_payload
        from docmancer.docs.domain.mutation_intent import MutationIntentContract
        if mutation != _mutation_payload(_restore_dto(MutationIntentContract, mutation)):
            errors.append('mutation contract or request-plan hash/content mismatch')
    if mutation.get('resolved_targets') or mutation.get('preserved_targets'):
        errors.append('mutation resolution requires canonical local evidence unavailable on the wire')
    return errors


def extract_tool_payload(result: Any, *, structured_supported: bool = True) -> dict:
    """Consume one non-error packet; structured/text dual delivery must agree."""
    value = result.model_dump() if hasattr(result, 'model_dump') else result
    if not isinstance(value, dict):
        raise EvidenceDeliveryError('invalid_tool_result')
    if value.get('isError') is True:
        raise EvidenceDeliveryError('error_tool_result')
    if 'isError' in value and type(value['isError']) is not bool:
        raise EvidenceDeliveryError('invalid_tool_error_flag')
    structured = value.get('structuredContent')
    if structured is not None and not isinstance(structured, dict):
        raise EvidenceDeliveryError('malformed_structured_evidence')
    candidates = []
    for block in value.get('content') or ():
        if not isinstance(block, dict) or block.get('type') != 'text':
            continue
        try:
            payload = json.loads(block.get('text', ''))
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and any(key in payload for key in ('status', 'kind', 'result', 'schema_version')):
            candidates.append(payload)
    if len(candidates) != 1:
        if candidates or structured is None:
            raise EvidenceDeliveryError('missing_or_ambiguous_evidence_channel')
    if structured is not None:
        if not structured_supported:
            raise EvidenceDeliveryError('structured_evidence_unsupported: configure DOCATLAS_MCP_TEXT_FALLBACK=1')
        if candidates:
            from docmancer.docs.application.action_packet import serialize_action_packet
            try:
                identical = serialize_action_packet(structured) == serialize_action_packet(candidates[0])
            except (ValueError, TypeError) as exc:
                raise EvidenceDeliveryError('invalid_evidence_channel') from exc
            if not identical:
                raise EvidenceDeliveryError('conflicting_evidence_channels')
        return deepcopy(structured)
    return candidates[0]


class SourceReadController:
    """Issued-resource I/O guards, independent of retained v4 evidence size."""

    def __init__(self, context: dict, *, requested_facts: dict[str, str], read_resource: Callable[[str], dict]):
        patch = context.get('kind') == 'patch_context'
        if patch:
            validate_patch_context_payload(context)
        elif (context.get('kind') != 'docs_context' or len(context.get('sources') or ()) > 3
              or docs_context_budget_tokens(context) > 800):
            raise ValueError('source reads require bounded docs_context')
        if not requested_facts or (not patch and len(requested_facts) > 3) or any(
            not isinstance(value, str) or not value.strip() or len(value) > 500
            for value in requested_facts.values()
        ):
            raise ValueError('declare nonempty requested facts within the selected mode input guards')
        self.requested_facts = dict(requested_facts)
        self.supported_facts: set[str] = set()
        self._read_resource = read_resource
        self._allowed: dict[str, dict[str, Any]] = {}
        # V4 attribution never creates an opaque source-read capability.
        sources = () if patch else context.get('sources') or ()
        for source in sources:
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
        for target in (() if patch else context.get('read_next') or ()):
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
            for source in sources
            if isinstance(source, dict) and type(source.get('line_start')) is int
            and type(source.get('line_end')) is int
            and 0 < source['line_start'] <= source['line_end']
        ]
        self._seen_text = {' '.join(str(source.get('snippet') or '').split())
                           for source in sources if isinstance(source, dict)}
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
