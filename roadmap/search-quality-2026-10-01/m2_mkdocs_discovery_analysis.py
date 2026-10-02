"""Native discovery observation, with an explicitly labelled ranking ablation.

Run with PYTHONPATH=.; --no-parent-diversity changes only diagnostic run ordering.
"""
import hashlib
import json
import tempfile
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context
from tests.docs._reference_binding_fixtures import capture_reference_case
from docmancer.retrieval.dispatch import RetrievalDispatcher
from docmancer.core.models import RetrievedChunk
from docmancer.docs.domain.query_terms import documentation_query_terms, documentation_exact_terms
from docmancer.docs.domain.evidence_qualification import _visible_term_present
import docmancer.docs.application.reference_query_tagging as tagging
import docmancer.docs.application.read_context_admission as read_admission
import docmancer.docs.application.need_context_projection as need_projection


def main():
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'mkdocs-05')
    question = case['question']
    documents = documents_for(case['project_group'], manifest)
    witness = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
    terms = documentation_query_terms(question)
    exact = {term.normalized_value for term in documentation_exact_terms(question)}
    stages, store_queries, qualifications, offline_selections = [], [], [], []
    context_checks = []
    no_parent_diversity = '--no-parent-diversity' in sys.argv[1:]
    rank = RetrievalDispatcher._rank_project_bodies_within_source
    cap = RetrievalDispatcher._limit_sections_per_source
    append = RetrievalDispatcher._append_api_term_matches
    qualify = tagging.qualify_evidence
    read_check = read_admission.read_context_admission
    need_check = need_projection.classify_need_context

    def contains(body):
        return ' '.join(witness.split()) in ' '.join(body.split())

    def rows(chunks):
        result = []
        for position, chunk in enumerate(chunks, 1):
            metadata = chunk.metadata or {}
            matched = [term for term in terms if _visible_term_present(term, chunk.text.casefold(), exact=term in exact)]
            exact_matched = [term for term in sorted(exact) if _visible_term_present(term, chunk.text.casefold(), exact=True)]
            result.append({'rank': position, 'section_id': metadata.get('section_id'),
                'source': chunk.source, 'chunk_index': chunk.chunk_index,
                'parent_logical_id': metadata.get('parent_logical_id'),
                'title': metadata.get('title'), 'heading_path': metadata.get('heading_path'),
                'line_start': metadata.get('line_start'), 'line_end': metadata.get('line_end'),
                'source_class': metadata.get('source_class'), 'score': chunk.score,
                'body_matched_terms': matched, 'exact_matched_terms': exact_matched,
                'ranking_key': [len(exact_matched), len(matched)],
                'ranking': metadata.get('ranking'),
                'lexical_match': metadata.get('lexical_match'),
                'witness': contains(chunk.text), 'text': chunk.text})
        return result

    def observe_rank(query, chunks):
        before = rows(chunks)
        selected = rank(query, chunks)
        if no_parent_diversity:
            # Diagnostic ablation only: preserve source positions and the native
            # body/exact key, omit parent uniqueness promotion. No witness label
            # participates in ordering; every downstream guard remains native.
            grouped = {}
            for c in chunks:
                source = str(c.metadata.get('canonical_url') or c.source)
                grouped.setdefault(source, []).append(c)
            queues = {source: iter(sorted(group, key=lambda c: (
                sum(_visible_term_present(t, c.text.casefold(), exact=True) for t in exact),
                sum(_visible_term_present(t, c.text.casefold(), exact=t in exact) for t in terms)), reverse=True))
                for source, group in grouped.items()}
            selected = [next(queues[str(c.metadata.get('canonical_url') or c.source)]) for c in chunks]
        stages.append({'stage': 'project_body_rank', 'query': query,
                       'before': before, 'after': rows(selected)})
        return selected

    def observe_cap(self, chunks, **kwargs):
        selected = cap(self, chunks, **kwargs)
        prior = next(s for s in reversed(stages) if s['stage'] == 'project_body_rank')
        by_id = {c.metadata['section_id']: c for c in chunks}
        native_order = [by_id[r['section_id']] for r in prior['before']]
        lexical_order = sorted(native_order, key=lambda c: (
            sum(_visible_term_present(t, c.text.casefold(), exact=True) for t in exact),
            sum(_visible_term_present(t, c.text.casefold(), exact=t in exact) for t in terms)), reverse=True)
        for name, order in [('sqlite_order', native_order), ('body_terms_without_parent_diversity', lexical_order)]:
            shadow = cap(self, order, **kwargs)
            offline_selections.append({'policy': name,
                'witness_rank': next((i for i, c in enumerate(order, 1) if contains(c.text)), None),
                'selected': rows(shadow)})
        stages.append({'stage': 'source_quota', 'kwargs': kwargs,
            'max_sections_per_source': self.config.retrieval.max_sections_per_source,
            'before': rows(chunks), 'after': rows(selected)})
        return selected

    def observe_append(self, query, chunks, **kwargs):
        # Record store output as well as supplemental calls; every native result
        # is returned unchanged. No labels or alternative ranking enter runtime.
        store_type = type(self.store)
        store_query = store_type.query

        def observe_store(store, text, **query_kwargs):
            result = store_query(store, text, **query_kwargs)
            store_queries.append({'query': text, 'kwargs': query_kwargs, 'rows': rows(result)})
            return result

        before = rows(chunks)
        with patch.object(store_type, 'query', observe_store):
            selected = append(self, query, chunks, **kwargs)
        stages.append({'stage': 'exact_supplement', 'query': query,
                       'before': before, 'after': rows(selected)})
        return selected

    def observe_qualification(probe, **kwargs):
        result = qualify(probe, **kwargs)
        qualifications.append({'query_id': kwargs['query_id'],
            'witness': contains(kwargs.get('evidence_text', '')),
            'reason': result.reason, 'trace': dict(result.trace)})
        return result

    def observe_read_check(candidate, **kwargs):
        result = read_check(candidate, **kwargs)
        context_checks.append({'route': 'original_read_context',
            'witness': contains(str(candidate.get('snippet') or '')),
            'allowed': result.allowed, 'reason': result.reason})
        return result

    def observe_need_check(contract, **kwargs):
        result = need_check(contract, **kwargs)
        context_checks.append({'route': 'typed_need_context',
            'witness': contains(str(kwargs['candidate'].get('snippet') or '')),
            'state': result.state, 'reason': result.reason,
            'need_subject': contract.need.subject, 'need_relation': contract.need.relation,
            'hard_exact': list(contract.need.hard_exact)})
        return result

    with tempfile.TemporaryDirectory(dir='/tmp/opencode') as directory:
        with patch.object(RetrievalDispatcher, '_rank_project_bodies_within_source', staticmethod(observe_rank)), \
             patch.object(RetrievalDispatcher, '_limit_sections_per_source', observe_cap), \
             patch.object(RetrievalDispatcher, '_append_api_term_matches', observe_append), \
             patch.object(tagging, 'qualify_evidence', observe_qualification), \
             patch.object(read_admission, 'read_context_admission', observe_read_check), \
             patch.object(need_projection, 'classify_need_context', observe_need_check):
            capture = capture_reference_case(Path(directory), documents, question)
    payload = capture['public_payload']
    # Independent selection-only control: no MkDocs words or fixture labels
    # participate in ranking. This does not exercise delivery/source admission.
    synthetic_query = 'storage retention timeout'
    synthetic = [RetrievedChunk(source='docs/guide.md', chunk_index=i, text=body, score=1.0,
        metadata={'parent_logical_id': parent, 'source_class': 'project_file'})
        for i, (parent, body) in enumerate([
            ('A', 'storage retention timeout first passage.'),
            ('A', 'storage retention timeout second passage.'),
            ('A', 'storage retention lasts for the documented interval.'),
            ('B', 'storage inventory information.'),
        ])]
    synthetic_dispatch = RetrievalDispatcher(store=None,
        config=SimpleNamespace(retrieval=SimpleNamespace(max_sections_per_source=2)))
    synthetic_diverse = rank(synthetic_query, synthetic)
    synthetic_cap = cap(synthetic_dispatch, synthetic_diverse, limit=20, expand='none')
    synthetic_plain = cap(synthetic_dispatch, synthetic, limit=20, expand='none')
    synthetic_control = {'query': synthetic_query,
        'input': [{'id': c.chunk_index, 'parent': c.metadata['parent_logical_id'], 'text': c.text} for c in synthetic],
        'after_parent_diversity': [c.chunk_index for c in synthetic_diverse],
        'selected_diversity': [c.chunk_index for c in synthetic_cap],
        'selected_no_diversity': [c.chunk_index for c in synthetic_plain]}
    summary = []
    for stage in stages:
        summary.append({'stage': stage['stage'], 'before_count': len(stage['before']),
            'after_count': len(stage['after']),
            'witness_ranks_before': [r['rank'] for r in stage['before'] if r['witness']],
            'witness_ranks_after': [r['rank'] for r in stage['after'] if r['witness']]})
    output = {'case_id': case['id'], 'question': question,
        'diagnostic_mode': 'no_parent_diversity_ablation' if no_parent_diversity else 'native_observation',
        'corpus_hash': hashlib.sha256(json.dumps(documents, sort_keys=True).encode()).hexdigest(),
        'query_terms': list(terms), 'exact_terms': sorted(exact), 'summary': summary,
        'stages': stages, 'supplement_store_queries': store_queries,
        'offline_same_quota_selections': offline_selections,
        'synthetic_selection_control': synthetic_control,
        'qualifications': qualifications,
        'context_checks': context_checks,
        'projection_candidate_counts': [len(a['before_projection'].get('context_pack', []))
                                       for a in capture['projection_attempts']],
        'qualification_reasons': dict(Counter(q['reason'] for q in qualifications)),
        'claims': assess_context(case, payload, registry_for(case['project_group'], manifest))['claims'],
        'visible_sources': len(payload.get('sources', [])),
        'answer_supported': payload['answer_supported'], 'edit_ready': payload['edit_ready']}
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
