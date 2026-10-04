"""I.2 isolated retrieval only; no permission, public packing or rescue."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import re
from pathlib import Path
import sqlite3

from docmancer.core.structured_chunking import parse_markdown_parents


PORTS = Path(__file__).parent / 'third_party/grounded-3.2.1'


def port(name):
    spec = importlib.util.spec_from_file_location('next07_' + name, PORTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


escape_fts_query = port('fts_query').escape_fts_query
structural_spans = port('passage_splitter').structural_spans


def rank_rows(rows, question, *, limit=20):
    """Rank one current, scope-checked inventory; BM25 is not approval."""
    if not 0 < limit <= 20:
        raise ValueError('existing candidate cap exceeded')
    with sqlite3.connect(':memory:') as db:
        db.execute("CREATE VIRTUAL TABLE passages USING fts5(content,title,url,path,tokenize='porter unicode61')")
        for row in rows:
            db.execute('INSERT INTO passages(content,title,url,path) VALUES (?,?,?,?)',
                tuple(row.get(k, '') for k in ('content', 'title', 'url', 'path')))
        hits = db.execute('SELECT rowid,bm25(passages,10.0,1.0,5.0,1.0) FROM passages WHERE passages MATCH ? ORDER BY 2',
            (escape_fts_query(question),)).fetchall()
    ordered = sorted(((rows[index-1], score) for index, score in hits),
        key=lambda pair: (pair[1], pair[0]['identity'], pair[0].get('start', 0), pair[0].get('end', 0)))
    return [{**row, 'bm25_order_score': score, 'retrieval_order': i} for i, (row, score) in enumerate(ordered[:limit])]


def proposals(documents, question):
    """Documents must originate from a verified current scoped inventory."""
    rows, omissions = [], []
    for document in documents:
        raw = document['raw']
        spans, omitted = structural_spans(raw, document['identity'])
        omissions.extend({'identity': document['identity'], **o} for o in omitted)
        parents = parse_markdown_parents(raw, document['identity'])
        for start, end in spans:
            owners = [p for p in parents if p.char_start < end and start < p.char_end]
            rows.append({**document, 'start': start, 'end': end, 'content': raw[start:end],
                'canonical_path': document.get('canonical_path', document.get('path', '')),
                'path': json.dumps(list(owners[-1].heading_path)) if owners else '[]',
                'source_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'owner_spans': [[p.char_start, p.char_end] for p in owners],
                'dependency_spans': 'NOT_PREPARED until scoped source preparation in I.3; not approval',
                'byte_start': len(raw[:start].encode()), 'byte_end': len(raw[:end].encode())})
    return rank_rows(rows, question), omissions


def read_decision(candidate, *, question, expected_project_identity, lifecycle_intent='current'):
    """I.3 single read owner. Never returns proof/applicability credit."""
    from dataclasses import replace
    from docmancer.docs.domain.source_window_eligibility import source_window_eligibility, prepare_source_probe
    from docmancer.docs.domain.query_terms import query_constraint_roles, documentation_query_terms
    from docmancer.docs.domain.technical_tokens import technical_term_pattern
    from docmancer.docs.domain.evidence_set_types import ScopeKey, SourceKey
    from docmancer.docs.domain.source_dependency_graph import source_graph
    from docmancer.docs.domain.admission_grammar import parse_admission_frame, _STATES
    from docmancer.docs.domain.admission_relations import _PREFIX_CONDITION, _phrase, relation_local_witness
    from docmancer.docs.application.read_context_admission import ReadContextAdmission

    def reject(reason):
        return ReadContextAdmission(False, reason)

    eligibility = source_window_eligibility(candidate, question=question,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent)
    if not eligibility.eligible:
        return reject(eligibility.reason)
    body = candidate['snippet']
    evidence = candidate['_reference_evidence']
    raw, identity = evidence['raw_document'], evidence['source']
    start, end = candidate['char_span']
    indexed_spans, _ = structural_spans(raw, identity['document_id'])
    if (start, end) not in indexed_spans:
        return reject('not_whole_indexed_unit')
    roles = query_constraint_roles(question)
    trace, reason = prepare_source_probe({'query_text': question,
        'query_terms': list(documentation_query_terms(question)), 'exact_terms': list(roles.hard_exact),
        'bound_subjects': list(roles.bound_subjects)}, visible_text=body, evidence_text=body,
        candidate=candidate, expected_project_identity=expected_project_identity,
        lifecycle_intent=lifecycle_intent, catalog_role=str(candidate.get('catalog_role') or ''))
    if reason:
        return reject(reason)
    # Every literal identity/subject must be visible, not borrowed from hidden headings.
    for term in (*trace.get('exact_terms', ()), *trace.get('bound_subjects', ())):
        if not re.search(technical_term_pattern(term, exact=True), body, re.I):
            return reject('missing_visible_exact_or_subject')
    scope = ScopeKey(**identity['scope'])
    key = SourceKey(scope, identity['document_id'], identity['canonical_path'], identity['content_sha256'])
    graph = source_graph(raw, key)
    for edge in graph.edges:
        child, parent = edge.child, edge.parent
        if child.start < end and start < child.end and not start <= parent.start < parent.end <= end:
            return reject('hidden_structural_dependency')
    # Reuse the existing supported grammar and relation-local witness, not mixed
    # False. Only a locally witnessed opposite canonical enabled/disabled clause
    # is a mismatch; unsupported language remains unknown.
    frame = parse_admission_frame(question)
    required = {slot.role: slot for slot in frame.constraints} if frame else {}
    if {'condition_subject', 'condition_state'} <= required.keys():
        for block in re.split(r'\n\s*\n', body):
            normalized = ' '.join(block.split())
            match = _PREFIX_CONDITION.match(normalized)
            if (match and re.fullmatch(_phrase(required['condition_subject'].text), match['entity'], re.I)
                    and _STATES[match['state'].casefold()] != required['condition_state'].canonical):
                actual_constraints = tuple(replace(slot, canonical=_STATES[match['state'].casefold()])
                    if slot.role == 'condition_state' else slot for slot in frame.constraints)
                witnessed, _ = relation_local_witness(replace(frame, constraints=actual_constraints), normalized)
                if witnessed:
                    return reject('existing_local_condition_mismatch')
    # Keep the old heading-only/question-echo exclusion, without lexical floors.
    query_words = ' '.join(re.findall(r'\w+(?:[.-]\w+)*', question.casefold()))
    prose = [line for line in body.splitlines() if line.strip() and not line.lstrip().startswith(('#', '```', '~~~'))
        and not re.fullmatch(r'[=-]{3,}', line.strip())]
    substantive = [line for line in prose if '?' not in line and
        ' '.join(re.findall(r'\w+(?:[.-]\w+)*', line.casefold())) not in query_words]
    if not substantive:
        return reject('heading_or_question_echo')
    return ReadContextAdmission(True, 'source_bound_retrieval_only_unknown_applicability')
