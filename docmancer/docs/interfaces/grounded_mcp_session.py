"""Provider-independent host session over a live MCP ClientSession.

The caller assesses semantic sufficiency. This adapter binds its judgments to
verbatim evidence and controls I/O; it never certifies the generated answer.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import PurePosixPath

from .host_context import SourceReadController, extract_tool_payload
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
        self.context = deepcopy(context)
        self._client = client
        if docs_context_budget_tokens(context) > 800:
            raise ValueError('project response exceeds the host evidence budget')
        reading_context = context if context.get('kind') == 'docs_context' else {'kind': 'docs_context', 'sources': []}
        self._controller = SourceReadController(reading_context, requested_facts=requested_facts,
                                                 read_resource=self._read_resource)
        self._evidence = {s['evidence_id']: deepcopy(s) for s in reading_context.get('sources', [])
                          if s.get('evidence_id')}
        self._known: dict[str, dict] = {}
        self._recovery_attempts = 0
        self._stopped_reason = None

    @property
    def evidence(self) -> dict:
        """Retained citation ids for host judgments; callers cannot mutate state."""
        return deepcopy(self._evidence)

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
                or quote not in str(source.get('snippet') or '')):
            raise ValueError('a requested fact needs a verbatim retained citation')
        self._known[fact_id] = {'fact': self._controller.requested_facts[fact_id],
            'quote': quote, 'evidence_id': evidence_id,
            'path_or_url': source.get('path_or_url') or source.get('path'),
            'line_start': source.get('line_start'), 'line_end': source.get('line_end')}
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
        Recovery shares the two-action/600-token ceiling with source reads.
        """
        action = self.context.get('recommended_next_action') or {}
        if (self.context.get('hard_stop') or self._recovery_attempts
                or self._controller.read_attempts >= 2
                or len(self._known) == len(self._controller.requested_facts)
                or action.get('tool') != 'code_search'
                or action.get('type') != 'search_local_source'
                or action.get('requires_confirmation') is not False
                or not isinstance(action.get('query_terms'), list)):
            return self._stop('no_authorized_read_only_recovery')
        terms = action['query_terms']
        if not 1 <= len(terms) <= 8 or any(not isinstance(t, str) or not t.strip() or len(t) > 500 for t in terms):
            return self._stop('invalid_recovery_terms')
        self._recovery_attempts += 1
        try:
            result = await search_local_source(project_path=self.arguments['project_path'],
                                               query_terms=tuple(terms))
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

    def finish(self) -> dict:
        """Return a grounded handoff; the host writes the user-facing answer."""
        missing = [text for key, text in self._controller.requested_facts.items() if key not in self._known]
        exhausted = self._controller.read_attempts + self._recovery_attempts >= 2
        return {'status': 'partial' if self._known and missing else
                'host_assessed_complete' if self._known else 'insufficient',
            'known': deepcopy(list(self._known.values())), 'missing': missing,
            'answer_supported': False, 'assessment_owner': 'host',
            'next_step': deepcopy(self.context.get('recommended_next_action'))
                if missing and not self._recovery_attempts and not exhausted else None,
            'stop_reason': (self._stopped_reason or ('read_budget_exhausted' if exhausted else None)) if missing else None}

    def _stop(self, reason):
        self._stopped_reason = reason
        return {'status': 'stopped', 'reason_code': reason}
