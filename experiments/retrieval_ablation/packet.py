"""Project-only whole-child PacketPort using the actual reference/gate/DTO code.

This does not certify answers. Only the existing lexical-ratio rejection may be
bypassed; missing exact identities, source references and all other rejections
remain fail-closed. No synthetic qualified trace is installed in the renderer.
Versioned/library scopes remain unsupported rather than silently unversioned.
"""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe


class ProjectPacketPort:
    def __init__(self, store, *, filters, queries):
        self.store = store
        self.filters = deepcopy(filters)
        self.queries = tuple(queries)
        self.context = SourceReferenceContext(store, question=queries[0],
            queries=[SimpleNamespace(text=q) for q in queries], filters=filters)
        if not self.context.complete or not self.context.scope.snapshot_id:
            raise ValueError('complete active project reference catalog required')
        self.rejections = []
        self.prepared = {}
        self.admission_scan_rows = 0
        self.admission_scan_bytes = 0

    @staticmethod
    def supported(filters):
        return (isinstance(filters.get('project_path'), str) and bool(filters['project_path'])
                and filters.get('source_class') in ('project_doc', 'project_file')
                and filters.get('doc_scope') == 'project'
                and not any(filters.get(k) for k in ('resolved_version', 'library_id', 'version_family')))

    def prepare(self, row, query):
        """Materialize real current-child metadata, never trust incoming approval."""
        self.admission_scan_rows += 1
        self.admission_scan_bytes += len(row['display_text'].encode('utf-8'))
        metadata = json.loads(row['metadata_json'])
        for key in ('project_identity', 'project_path', 'source_class', 'doc_scope',
                    'authority', 'source_path', 'stable_chunk_id'):
            metadata[key] = row[key]
        # SourceReferenceContext's project catalog has an unversioned ScopeKey.
        # A nonempty version must not be erased to make its validation pass.
        if row.get('resolved_version'):
            return None, 'versioned_project_packet_not_supported'
        metadata.update(char_span=[row['char_start'], row['char_end']])
        chunk = RetrievedChunk(source=row['source'], chunk_index=row['chunk_index'],
                               text=row['display_text'], score=0.0, metadata=metadata)
        chunks = self.context.prepare([chunk], query)
        if len(chunks) != 1 or not chunks[0].metadata.get('_reference_evidence'):
            return None, 'missing_current_source_reference'
        chunk = chunks[0]
        original = dict(chunk.metadata)
        reference = original['_reference_evidence']
        document = self.context._document(row['source'])
        owner = reference.get('owner') or {}
        parents = [p for p in document[1] if p.logical_id == owner.get('logical_id')]
        if len(parents) != 1:
            return None, 'missing_verified_subject_owner'
        parent = parents[0]
        if (tuple(original.get('heading_path') or ()) != parent.heading_path
                or row['title'] != parent.title
                or row['parent_logical_id'] != parent.logical_id):
            return None, 'inconsistent_source_heading'
        a, b = original['char_span']
        line_a, line_b = original['line_span']
        original.update(path=original['source_path'], content=chunk.text,
            display_text=chunk.text, snippet=chunk.text, char_start=a, char_end=b,
            line_start=line_a, line_end=line_b, title=row['title'],
            heading_path=' > '.join(original['heading_path']),
            resolved_version='', doc_scope='project')
        probe = {'query_text': query}
        _, reason = prepare_reference_probe(probe, candidate=original, evidence_text=chunk.text)
        if reason:
            return None, reason
        qualification = self.qualify(original, query)
        if not self.hard_pass(qualification):
            return None, qualification.reason
        # Keep the real (possibly rejected) trace private. It is not an approval.
        self.prepared[(row['stable_chunk_id'], query)] = (original, qualification)
        return original, None

    def qualify(self, original, query):
        query_index = self.queries.index(query)
        query_id = 'query-original' if query_index == 0 else f'query-host-{query_index}'
        return qualify_evidence({'query_text': query}, query_id=query_id,
            visible_text=original['snippet'], evidence_text=original['snippet'],
            candidate=original, expected_project_identity=self.filters['project_identity'])

    @staticmethod
    def hard_pass(qualification):
        if qualification.qualified:
            return True
        trace = qualification.trace
        return (qualification.reason == 'insufficient_visible_match'
                and trace.get('missing_exact_terms') == []
                and trace.get('missing_parent_exact_terms') == []
                and type(trace.get('match_ratio')) in (int, float)
                and trace.get('qualification_reason') == 'insufficient_visible_match'
                and trace.get('qualified') is False)

    def allowed_ids(self, rows, query):
        allowed = []
        for key, row in rows.items():
            _, reason = self.prepare(row, query)
            if reason:
                self.rejections.append({'query': query, 'stable_chunk_id': row['stable_chunk_id'],
                                        'reason': reason})
            else:
                allowed.append(key)
        return allowed

    def pack(self, candidates, lanes):
        """No selection heuristics: rank order, whole children, skip oversized."""
        from docmancer.docs.application._docs_context_payload import _payload
        from docmancer.docs.application.context_selection import context_selection_decision
        from docmancer.docs.application.model_visible_projection import (
            _docs_source, _snapshot_entry, docs_context_budget_tokens,
            project_insufficient, validate_model_visible_projection)

        sources, snapshot, originals = [], {}, []
        omissions = []
        seen = set()
        counts = {}
        requested_ids = ['query-original', *[f'query-host-{i}' for i in range(1, len(self.queries))]]

        def render(rows):
            return _payload(rows, decision=context_selection_decision(rows, requested_ids))

        for candidate in candidates:
            row = candidate['row']
            query = lanes[candidate['lane']]['query']
            original, qualification = self.prepared[(row['stable_chunk_id'], query)]
            original = deepcopy(original)
            public = _docs_source(original)
            reason = None
            if public is None:
                reason = 'whole_child_exceeds_renderer_limits'
            else:
                public.update(project_identity=original['project_identity'],
                    line_start=original['line_start'], line_end=original['line_end'],
                    authority=original['authority'], scope=original['doc_scope'])
                key = (public['path_or_url'], public['line_start'], public['line_end'], public['snippet'])
                if key in seen or public['evidence_id'] in snapshot:
                    reason = 'duplicate'
                elif len(sources) >= 3 or counts.get(public['path_or_url'], 0) >= 2:
                    reason = 'source_entry_or_section_cap'
                elif not self.hard_pass(self.qualify(original, query)):
                    reason = 'final_hard_gate_rejected'
                elif docs_context_budget_tokens(render([*sources, public])) > 800:
                    reason = 'whole_child_exceeds_dto_budget'
            if reason:
                omissions.append({'stable_chunk_id': row['stable_chunk_id'], 'reason': reason})
                continue
            seen.add(key)
            sources.append(public)
            originals.append((original, query))
            counts[public['path_or_url']] = counts.get(public['path_or_url'], 0) + 1
            snapshot[public['evidence_id']] = _snapshot_entry(original, public)

        packet = render(sources) if sources else project_insufficient(kind='docs_context',
            missing=['No admissible whole source unit fits the frozen packet limits.'],
            recommended_next_action=None, max_tokens=800)
        # Revalidate the entire final visible set, not only each proposed append.
        for original, query in originals:
            if not self.hard_pass(self.qualify(original, query)):
                raise ValueError('final whole-packet source/reference validation failed')
        errors = validate_model_visible_projection(packet, snapshot=snapshot, max_tokens=800)
        if errors:
            raise ValueError('invalid canonical packet: ' + '; '.join(errors))
        return {'model_visible_packet': packet, 'packet_snapshot': snapshot,
                'packet_status': 'VALIDATED_PROJECT_PACKET', 'packet_audit_errors': errors,
                'packet_budget_tokens': docs_context_budget_tokens(packet),
                'packet_omissions': omissions, 'admission_rejections': self.rejections,
                'admission_scan_rows': self.admission_scan_rows,
                'admission_scan_display_bytes': self.admission_scan_bytes,
                'soft_ablation': 'lexical_ratio_only; other rejection reasons retained',
                'qualification_traces': [dict(q.trace) for _, q in self.prepared.values()]}
