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

    def pack(self, candidates, lanes, *, strict_soft_gate=False, legacy_ordering=False):
        """Rank-order whole units; optionally restore the legacy visible-match gate."""
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
        ordering_traces = []
        gate_output_sha256 = None
        ranked_inputs = []
        if strict_soft_gate:
            for index, candidate in enumerate(candidates):
                row = candidate['row']
                query = lanes[candidate['lane']]['query']
                original, _ = self.prepared[(row['stable_chunk_id'], query)]
                qualification = self.qualify(original, query)
                if not qualification.qualified:
                    continue
                query_id = requested_ids[self.queries.index(query)]
                trace = deepcopy(qualification.trace)
                ordering_traces.append(trace)
                ranked_inputs.append({**deepcopy(original),
                    'retrieval_query_matches': {query_id: trace}, '_ablation_index': index})
            import hashlib
            gate_output_sha256 = hashlib.sha256(json.dumps(ranked_inputs, sort_keys=True,
                ensure_ascii=False, default=str).encode('utf-8')).hexdigest()
        if legacy_ordering:
            if not strict_soft_gate:
                raise ValueError('legacy ordering requires the real legacy gate')
            from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates
            ranked = _facet_aware_candidates(ranked_inputs,
                query_text=dict(zip(requested_ids, self.queries)),
                required_query_ids=set(requested_ids),
                host_query_ids=set(requested_ids[1:]))
            # Reorder only. Real traces remain private; the public packet never
            # receives certification from this diagnostic preference component.
            ordered_indices = [item['_ablation_index'] for item in ranked]
            admitted = set(ordered_indices)
            candidates = [candidates[i] for i in ordered_indices] + [
                c for i, c in enumerate(candidates) if i not in admitted]

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
                else:
                    final_qualification = self.qualify(original, query)
                    accepted = (final_qualification.qualified if strict_soft_gate
                                else self.hard_pass(final_qualification))
                    if not accepted:
                        reason = ('legacy_soft_relevance_gate' if strict_soft_gate
                                  and final_qualification.reason == 'insufficient_visible_match'
                                  else 'final_hard_gate_rejected')
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
            final_qualification = self.qualify(original, query)
            accepted = (final_qualification.qualified if strict_soft_gate
                        else self.hard_pass(final_qualification))
            if not accepted:
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
                'soft_ablation': ('none; legacy visible-match gate restored' if strict_soft_gate
                                  else 'lexical_ratio_only; other rejection reasons retained'),
                'soft_relevance_mode': 'legacy' if strict_soft_gate else 'ratio_ablation',
                'qualification_traces': [dict(q.trace) for _, q in self.prepared.values()],
                'ordering_component': ('context_candidate_ranking._facet_aware_candidates'
                                       if legacy_ordering else 'rank_order'),
                'ordering_qualification_traces': ordering_traces,
                'gate_output_sha256': gate_output_sha256,
                'gate_output_count': len(ranked_inputs) if strict_soft_gate else None,
                'ordering_scope': 'single candidate ordering pass; whole-unit packer unchanged'}

    @staticmethod
    def _assembled_identity(row, start, end):
        import hashlib
        payload = f"{row['source_identity']}\0{row['parent_logical_id']}\0{start}\0{end}"
        return 'assembly-' + hashlib.sha256(payload.encode('utf-8')).hexdigest()[:40]

    @staticmethod
    def _assembled_row(row, raw, start, end):
        import hashlib
        from docmancer.core.structured_chunking import estimate_utf8_tokens
        assembled = dict(row)
        text = raw[start:end]
        assembled.update(
            stable_chunk_id=ProjectPacketPort._assembled_identity(row, start, end),
            display_text=text, text=text, retrieval_text=text,
            display_content_hash=hashlib.sha256(text.encode('utf-8')).hexdigest(),
            retrieval_content_hash=hashlib.sha256(text.encode('utf-8')).hexdigest(),
            display_token_estimate=estimate_utf8_tokens(text),
            retrieval_token_estimate=estimate_utf8_tokens(text),
            token_estimate=estimate_utf8_tokens(text),
            char_start=start, char_end=end,
            byte_start=len(raw[:start].encode('utf-8')),
            byte_end=len(raw[:end].encode('utf-8')),
            line_start=raw.count('\n', 0, start) + 1,
            line_end=raw.count('\n', 0, max(start, end - 1)) + 1,
            atom_type='structural_bundle',
        )
        return assembled

    def pack_structural(self, candidates, lanes, *, strict_soft_gate=False, legacy_ordering=False):
        """Pack the exact B ranked pool after one bounded owner-local closure.

        The closure performs no retrieval and has no access to review labels. For
        each seed it considers at most the immediately previous and next stored
        child of the same canonical parent, in source order.  A bundle remains an
        exact contiguous source slice and is capped at the existing 512-token
        child hard limit.  If the expanded unit fails the same reference/hard
        admission checks, the already-admitted seed is used unchanged.
        """
        from docmancer.core.structured_chunking import estimate_utf8_tokens

        parent_cache = {}
        assembly_reads = 0
        decisions = []
        assembled_candidates = []
        generation = self.store.active_generation_id()

        for candidate in candidates:
            seed = candidate['row']
            query = lanes[candidate['lane']]['query']
            cache_key = (seed['source'], seed['parent_logical_id'])
            if cache_key not in parent_cache:
                with self.store._connect() as conn:
                    siblings = [dict(row) for row in conn.execute(
                        'SELECT * FROM retrieval_children '
                        'WHERE generation_id = ? AND source = ? AND parent_logical_id = ? '
                        'ORDER BY char_start, char_end, stable_chunk_id',
                        (generation, seed['source'], seed['parent_logical_id']),
                    )]
                parent_cache[cache_key] = siblings
                assembly_reads += 1
            siblings = parent_cache[cache_key]
            positions = [i for i, row in enumerate(siblings)
                         if row['stable_chunk_id'] == seed['stable_chunk_id']]
            document = self.context._document(seed['source'])
            if len(positions) != 1 or not document:
                raise ValueError('assembly seed is not uniquely bound to current source')
            raw, parents, _ = document
            parent_matches = [p for p in parents if p.logical_id == seed['parent_logical_id']]
            if len(parent_matches) != 1:
                raise ValueError('assembly parent is not uniquely bound')
            parent = parent_matches[0]
            index = positions[0]
            start, end = seed['char_start'], seed['char_end']
            included = [seed['stable_chunk_id']]

            def fits(a, b):
                return (parent.char_start <= a <= b <= parent.char_end
                        and estimate_utf8_tokens(raw[a:b]) <= 512)

            if index > 0:
                previous = siblings[index - 1]
                if (previous['char_end'] <= start
                        and not raw[previous['char_end']:start].strip()
                        and fits(previous['char_start'], end)):
                    start = previous['char_start']
                    included.insert(0, previous['stable_chunk_id'])
            if index + 1 < len(siblings):
                following = siblings[index + 1]
                if (end <= following['char_start']
                        and not raw[end:following['char_start']].strip()
                        and fits(start, following['char_end'])):
                    end = following['char_end']
                    included.append(following['stable_chunk_id'])

            chosen = seed
            expanded = start != seed['char_start'] or end != seed['char_end']
            fallback_reason = None
            if expanded:
                proposal = self._assembled_row(seed, raw, start, end)
                _, reason = self.prepare(proposal, query)
                if reason is None:
                    chosen = proposal
                else:
                    fallback_reason = reason
                    start, end = seed['char_start'], seed['char_end']
                    included = [seed['stable_chunk_id']]
                    expanded = False
            selected = dict(candidate)
            selected['row'] = chosen
            selected['stable_chunk_id'] = chosen['stable_chunk_id']
            assembled_candidates.append(selected)
            decisions.append({
                'seed_stable_chunk_id': seed['stable_chunk_id'],
                'assembled_stable_chunk_id': chosen['stable_chunk_id'],
                'parent_logical_id': seed['parent_logical_id'],
                'assembled_parent_logical_id': chosen['parent_logical_id'],
                'parent_char_start': parent.char_start,
                'parent_char_end': parent.char_end,
                'assembled_char_start': start,
                'assembled_char_end': end,
                'included_child_ids': included,
                'expanded': expanded,
                'fallback_reason': fallback_reason,
            })

        if strict_soft_gate:
            paired_d_control = deepcopy(self.pack(assembled_candidates, lanes, strict_soft_gate=False))
            paired_e_g_control = deepcopy(self.pack(assembled_candidates, lanes, strict_soft_gate=True))
            result = (self.pack(assembled_candidates, lanes, strict_soft_gate=True, legacy_ordering=True)
                      if legacy_ordering else deepcopy(paired_e_g_control))
            result['paired_D_control'] = paired_d_control
            if legacy_ordering:
                result['paired_E_G_control'] = paired_e_g_control
        else:
            result = self.pack(assembled_candidates, lanes, strict_soft_gate=False)
        result.update(assembly_policy='owner_neighbors_v1', assembly_reads=assembly_reads,
                      assembly_decisions=decisions,
                      assembled_candidate_count=len(assembled_candidates))
        return result
