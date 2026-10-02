"""Paired diagnostic arms; frozen requests and budgets are never modified.

Section-first is an experimental ordering of existing source-local indexed
children, not an extra source read or a replacement production chunk index.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for, stage_assessment
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.query_terms import documentation_query_terms, documentation_exact_terms
from docmancer.docs.domain.evidence_qualification import _visible_term_present
from docmancer.retrieval.dispatch import RetrievalDispatcher


def fine_key(query, chunk):
    terms = documentation_query_terms(query)
    exact = {t.normalized_value for t in documentation_exact_terms(query)}
    body = chunk.text.casefold()
    return (sum(_visible_term_present(t, body, exact=True) for t in exact),
            sum(_visible_term_present(t, body, exact=t in exact) for t in terms))


def source_key(chunk):
    return str((chunk.metadata or {}).get('canonical_url') or chunk.source)


def plain_rank(query, chunks):
    groups = {}
    for chunk in chunks:
        groups.setdefault(source_key(chunk), []).append(chunk)
    queues = {key: iter(sorted(group, key=lambda c: fine_key(query, c), reverse=True))
              for key, group in groups.items()}
    return [next(queues[source_key(c)]) for c in chunks]


def section_rank(query, chunks):
    """Coarse bounded section score, then fine child ordering, unchanged bytes.

    Only indexed children already in this retrieval call participate. Section
    membership is a preference, never permission or proof. No gold/case label.
    """
    groups = {}
    for chunk in chunks:
        groups.setdefault(source_key(chunk), []).append(chunk)
    queues = {}
    for source, group in groups.items():
        sections = {}
        for index, chunk in enumerate(group):
            parent = (chunk.metadata or {}).get('parent_logical_id')
            sections.setdefault(parent or ('unbound', index), []).append(chunk)
        def coarse(children):
            # Read at most 5000 existing chars per group for ranking only.
            ordered = sorted(children, key=lambda c: c.chunk_index)
            text = '\n'.join(c.text for c in ordered)[:5000].casefold()
            terms = documentation_query_terms(query)
            exact = {t.normalized_value for t in documentation_exact_terms(query)}
            return (sum(_visible_term_present(t, text, exact=True) for t in exact),
                    sum(_visible_term_present(t, text, exact=t in exact) for t in terms))
        ordered_sections = sorted(sections.values(), key=coarse, reverse=True)
        queues[source] = iter([c for children in ordered_sections
                               for c in sorted(children, key=lambda c: fine_key(query, c), reverse=True)])
    return [next(queues[source_key(c)]) for c in chunks]


def tied_diversity_rank(query, chunks):
    """Parent novelty breaks equal lexical keys only, never stronger relevance."""
    groups = {}
    for chunk in chunks:
        groups.setdefault(source_key(chunk), []).append(chunk)
    queues = {}
    for source, group in groups.items():
        bands = {}
        for chunk in sorted(group, key=lambda c: fine_key(query, c), reverse=True):
            bands.setdefault(fine_key(query, chunk), []).append(chunk)
        ordered, seen = [], set()
        for band in bands.values():
            first, repeats = [], []
            for chunk in band:
                parent = (chunk.metadata or {}).get('parent_logical_id')
                if parent and parent not in seen:
                    first.append(chunk)
                    seen.add(parent)
                else:
                    repeats.append(chunk)
            ordered.extend(first + repeats)
        queues[source] = iter(ordered)
    return [next(queues[source_key(c)]) for c in chunks]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arms', nargs='+', default=['native', 'plain', 'section'],
                        choices=['native', 'plain', 'section', 'tied', 'no-boosts'])
    parser.add_argument('--coarse-index', action='store_true',
                        help='Experimental 768/1280-token index profile; final packet remains 800')
    parser.add_argument('--fixture-root', type=Path,
                        help='Reuse one immutable physical corpus path across baseline and candidate')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Runtime state must be outside checkout')
    output.mkdir(parents=True, exist_ok=False)
    protocol, cases, manifest = load_protocol()
    rows = []
    rankings = {'plain': plain_rank, 'section': section_rank, 'tied': tied_diversity_rank}
    for project in sorted({c['project_group'] for c in cases}):
        docs = documents_for(project, manifest)
        root = (args.fixture_root.resolve() if args.fixture_root else output / 'corpus') / project
        if args.fixture_root:
            for path, text in docs.items():
                if (root / path).read_text() != text:
                    raise ValueError('Shared frozen corpus mismatch: ' + path)
        else:
            write_project(root, docs)
        with isolated_service(output / 'state' / project) as (service, config):
            if args.coarse_index:
                from docmancer.core.sqlite_store import SQLiteStore
                from docmancer.core.models import Document
                schema_document = SQLiteStore._current_schema_document
                def coarse_document(doc):
                    current = schema_document(doc)
                    metadata = {**current.metadata, 'child_target_tokens': 768, 'child_hard_max_tokens': 1280}
                    return Document(source=current.source, content=current.content, metadata=metadata)
                with patch.object(SQLiteStore, '_current_schema_document', staticmethod(coarse_document)):
                    ingest = index_project(service, config, root)
            else:
                ingest = index_project(service, config, root)
            save(output / 'ingest' / (project + '.json'), ingest)
            for case in (c for c in cases if c['project_group'] == project):
                for arm in args.arms:
                    manager = (patch.object(RetrievalDispatcher, '_rank_project_bodies_within_source',
                                            staticmethod(rankings[arm])) if arm in rankings else nullcontext())
                    if arm == 'no-boosts':
                        from docmancer.docs.domain import project_doc_ranking
                        manager = patch.object(project_doc_ranking, 'source_requirement_boost',
                                               lambda path, question, intent: 1.0)
                    request = {'question': case['question'], 'project_path': str(root), 'scope': 'project'}
                    started = time.perf_counter()
                    try:
                        with manager:
                            payload, trace = observe_call(service, request)
                        validation = validate_model_visible_projection(
                            payload, snapshot=trace.get('snapshot', {}), max_tokens=800)
                        assessment = assess_context(case, payload, registry_for(project, manifest))
                        stages = stage_assessment(case, payload, trace, ingest,
                                                  registry_for(project, manifest))
                        save(output / 'payloads' / arm / (case['id'] + '.json'), payload)
                        save(output / 'traces' / arm / (case['id'] + '.json'), trace)
                        row = {'id': case['id'], 'project': project, 'arm': arm,
                               'answerability': case['answerability'], 'assessment': assessment,
                               'admission_tokens': docs_context_budget_tokens(payload),
                               'source_count': len(payload.get('sources', [])),
                               'answer_supported': payload.get('answer_supported'),
                               'edit_ready': payload.get('edit_ready'),
                               'validation_errors': validation,
                               'stage_assessment': stages,
                               'seconds': time.perf_counter() - started}
                    except Exception as exc:
                        row = {'id': case['id'], 'project': project, 'arm': arm,
                               'answerability': case['answerability'], 'error': repr(exc)}
                    rows.append(row)
                    save(output / 'rows.json', rows)
    summary = {'python': sys.version, 'protocol': protocol, 'coarse_index': args.coarse_index, 'arms': {}}
    for arm in args.arms:
        selected = [r for r in rows if r['arm'] == arm]
        valid = [r for r in selected if 'error' not in r]
        positives = [r for r in valid if r['answerability'] == 'within_budget']
        summary['arms'][arm] = {
            'cases': len(selected), 'errors': [r for r in selected if 'error' in r],
            'positive_cases': len(positives),
            'positive_sufficient': sum(r['assessment']['context_sufficiency'] == 'sufficient' for r in positives),
            'budget_violations': [r['id'] for r in valid if r['admission_tokens'] > 800 or r['source_count'] > 3],
            'validation_errors': [r['id'] for r in valid if r['validation_errors']],
            'required_supported': sum(r['assessment']['required_supported'] for r in valid),
            'required_count': sum(r['assessment']['required_count'] for r in valid),
        }
    save(output / 'summary.json', summary)
    print(json.dumps(summary['arms'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
