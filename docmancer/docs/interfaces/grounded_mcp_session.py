"""Provider-independent host session over a live MCP ClientSession.

The caller assesses semantic sufficiency. This adapter binds its judgments to
verbatim evidence and controls I/O; it never certifies the generated answer.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import PurePosixPath

from .host_context import SourceReadController, extract_tool_payload, validate_patch_context_payload
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens


class GroundedMCPSession:
    @classmethod
    async def start(cls, client, *, arguments: dict, requested_facts: dict[str, str],
                    structured_supported: bool = True):
        arguments = deepcopy(arguments)
        if not arguments.get('question') or not arguments.get('project_path'):
            raise ValueError('a question and project path are required')
        context = extract_tool_payload(await client.call_tool('get_docs_context', arguments),
                                       structured_supported=structured_supported)
        return cls(client, arguments, context, requested_facts)

    def __init__(self, client, arguments, context, requested_facts):
        if any(context.get(flag) is True for flag in ('answer_supported', 'answer_available', 'edit_ready')):
            raise ValueError('grounded project sessions require retrieval-only evidence')
        self.arguments = deepcopy(arguments)
        self._context = deepcopy(context)
        self._client = client
        self._patch = context.get('kind') == 'patch_context'
        if arguments.get('context_format') == 'patch_context' and not self._patch:
            raise ValueError('explicit patch representation was not delivered')
        if not self._patch and docs_context_budget_tokens(context) > 800:
            raise ValueError('project response exceeds the host evidence budget')
        reading_context = context if context.get('kind') in {'docs_context', 'patch_context'} else {'kind': 'docs_context', 'sources': []}
        self._controller = SourceReadController(reading_context, requested_facts=requested_facts,
                                                 read_resource=self._read_resource)
        self._evidence = {s['evidence_id']: deepcopy(s) for s in reading_context.get('sources', [])
                          if s.get('evidence_id')}
        self._known: dict[str, dict] = {}
        self._recovery_context = None
        self._recovery_attempts = 0
        self._stopped_reason = None

    @property
    def context(self) -> dict:
        """Full retained response; callers cannot alter recovery advisories."""
        return deepcopy(self._context)

    @property
    def evidence(self) -> dict:
        """Retained citation ids for host judgments; callers cannot mutate state."""
        return deepcopy(self._evidence)

    @property
    def recovery_context(self) -> dict | None:
        """Full retained v4 recovery constraints, not a snippet-only projection."""
        return deepcopy(self._recovery_context)

    async def _read_resource(self, uri):
        result = await self._client.read_resource(uri)
        wire = result.model_dump() if hasattr(result, 'model_dump') else result
        contents = wire.get('contents') or []
        if len(contents) != 1 or not isinstance(contents[0].get('text'), str):
            raise ValueError('missing_or_ambiguous_source_resource')
        return json.loads(contents[0]['text'])

    def support(self, fact_id: str, *, evidence_id: str, quote: str) -> None:
        """Record a caller judgment only with a quote from retained evidence."""
        source = self._evidence.get(evidence_id)
        if (fact_id not in self._controller.requested_facts or not source
                or not isinstance(quote, str) or not quote.strip()
                or quote not in str(source.get('text') if self._patch else source.get('snippet') or '')):
            raise ValueError('a requested fact needs a verbatim retained citation')
        self._known[fact_id] = {'fact': self._controller.requested_facts[fact_id],
            'quote': quote, 'evidence_id': evidence_id,
            'path_or_url': source.get('path_or_url') or source.get('path'),
            'line_start': source.get('line_start'), 'line_end': source.get('line_end')}
        if self._patch:
            self._known[fact_id].update({key: deepcopy(source[key]) for key in (
                'stable_id', 'content_sha256', 'char_start', 'char_end',
                'authority', 'instruction_trust', 'scope', 'version_binding',
            ) if key in source})
        self._controller.mark_supported(fact_id)

    async def read(self, uri: str, *, missing_fact_id: str) -> dict:
        if self._controller.read_attempts + self._recovery_attempts >= 2:
            return self._stop('read_budget_exhausted')
        result = await self._controller.aread(uri, missing_fact_id=missing_fact_id)
        if result.get('status') in {'complete', 'truncated'}:
            key = f'read-{len(self._controller.results)}'
            self._evidence[key] = deepcopy(result)
        else:
            self._stopped_reason = result.get('reason_code')
        return result

    async def recover(self, search_local_source) -> dict:
        """Execute one advertised read-only search through a host-owned adapter.

        The adapter must enforce local source permissions. No arbitrary command,
        preparation, editing or network action is delegated by this session.
        Recovery shares the two-action I/O ceiling with source reads. Docs
        recovery retains its bounded representation; v4 evidence does not.
        """
        action = self._context.get('recommended_next_action') or {}
        if (self._context.get('hard_stop') or self._recovery_attempts
                or self._controller.read_attempts >= 2
                or len(self._known) == len(self._controller.requested_facts)
                or action.get('tool') != 'code_search'
                or action.get('type') != 'search_local_source'
                or action.get('requires_confirmation') is not False
                or not isinstance(action.get('query_terms'), list)):
            return self._stop('no_authorized_read_only_recovery')
        terms = action['query_terms']
        if not terms or (not self._patch and len(terms) > 8) or any(
            not isinstance(t, str) or not t.strip() or (not self._patch and len(t) > 500) for t in terms
        ):
            return self._stop('invalid_recovery_terms')
        self._recovery_attempts += 1
        try:
            result = await search_local_source(project_path=self.arguments['project_path'],
                                               query_terms=tuple(terms))
            if self._patch:
                return self._retain_patch_recovery(result)
            if not isinstance(result, dict) or docs_context_budget_tokens(result) > 600:
                return self._stop('invalid_or_oversized_recovery')
            sources = result.get('sources') or []
            if not isinstance(sources, list) or len(sources) > 3:
                return self._stop('invalid_recovery_sources')
            accepted = []
            for source in sources:
                path = source.get('path_or_url', '') if isinstance(source, dict) else ''
                if (not path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                        or ':' in path or '\\' in path or not isinstance(source.get('snippet'), str)):
                    return self._stop('invalid_recovery_source_binding')
                if source['snippet'].strip() and not any(source['snippet'] == s.get('snippet') for s in self._evidence.values()):
                    accepted.append(deepcopy(source))
            if not accepted:
                return self._stop('no_new_source_text')
            for index, source in enumerate(accepted, 1):
                self._evidence[f'recovery-{index}'] = source
            return {'status': 'context_added', 'sources': accepted}
        except Exception:
            return self._stop('read_only_recovery_failed')

    def _retain_patch_recovery(self, result) -> dict:
        """Accept a host-bound native v4 result, never a lossy snippet adapter."""
        if not isinstance(result, dict):
            return self._stop('invalid_recovery_sources')
        validate_patch_context_payload(result)
        if result['result'] == 'failure':
            self._recovery_context = deepcopy(result)
            return self._stop('recovery_evidence_unavailable')
        accepted = []
        stable_sources = {source['stable_id']: source for source in self._evidence.values()}
        for source in result.get('sources') or ():
            path = source['path']
            if (PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                    or ':' in path or '\\' in path):
                return self._stop('invalid_recovery_source_binding')
            existing = self._evidence.get(source['evidence_id'])
            stable_source = stable_sources.get(source['stable_id'])
            if ((existing is not None and existing != source)
                    or (stable_source is not None and stable_source != source)):
                return self._stop('recovery_evidence_identity_collision')
            if existing is None:
                accepted.append(deepcopy(source))
        if not accepted:
            self._recovery_context = deepcopy(result)
            return self._stop('no_new_source_text')
        for source in accepted:
            self._evidence[source['evidence_id']] = source
        self._recovery_context = deepcopy(result)
        return {'status': 'context_added', 'sources': deepcopy(accepted)}

    def finish(self) -> dict:
        """Return a grounded handoff; the host writes the user-facing answer."""
        missing = [text for key, text in self._controller.requested_facts.items() if key not in self._known]
        exhausted = self._controller.read_attempts + self._recovery_attempts >= 2
        return {'status': 'partial' if self._known and missing else
                'host_assessed_complete' if self._known else 'insufficient',
            'known': deepcopy(list(self._known.values())), 'missing': missing,
            'answer_supported': False, 'assessment_owner': 'host',
            'next_step': deepcopy(self._context.get('recommended_next_action'))
                if missing and not self._recovery_attempts and not exhausted else None,
            'stop_reason': (self._stopped_reason or ('read_budget_exhausted' if exhausted else None)) if missing else None}

    def _stop(self, reason):
        self._stopped_reason = reason
        return {'status': 'stopped', 'reason_code': reason}
