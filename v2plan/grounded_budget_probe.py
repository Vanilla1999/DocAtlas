"""Isolated budget research; never imported by production."""
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
import argparse
import hashlib
import json
from pathlib import Path
import time

from docmancer.core.models import Chunk, Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.core.retrieval_passages import PassageProfile
from docmancer.core.structured_chunking import _atom_spans
from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.docs.domain.source_window_eligibility import source_window_eligibility
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.application.read_context_admission import read_context_admission
from docmancer.docs.domain.query_terms import query_constraint_roles
from docmancer.docs.domain.evidence_qualification import _visible_term_present
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import _snapshot_entry, _source_digest
from docmancer.docs.application.model_visible_projection_helpers import canonical_projection_bytes
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project, save_json
from eval.evidence_quality_v2.observer import observe_call


def ordered_packet(proposals, *, budget, check, build):
    if budget not in (800, 1500, 3000) or len(proposals) > 4096:
        raise ValueError('invalid_experiment_limits')
    chosen, trace, seen = [], [], set()
    check_calls = build_calls = 0
    for proposal in sorted(proposals, key=lambda p: (p['native_rank'], p['proposal_id'])):
        pid = proposal['proposal_id']
        if pid in seen:
            raise ValueError('duplicate_proposal')
        seen.add(pid)
        check_calls += 1
        reason = check(proposal)
        event = {'proposal_id': pid, 'native_rank': proposal['native_rank']}
        if reason is None and len(chosen) == 3:
            reason = 'source_row_limit'
        if reason is None and sum(p['source_identity'] == proposal['source_identity'] for p in chosen) == 2:
            reason = 'per_source_limit'
        if reason is None:
            build_calls += 1
            trial, _ = build(chosen + [proposal])
            event['dto_units'] = docs_context_budget_tokens(trial)
            reason = 'dto_budget' if event['dto_units'] > budget else 'selected'
            if reason == 'selected':
                chosen.append(proposal)
        event['reason'] = reason
        trace.append(event)
    result = {'payload': None, 'trace': trace, 'visits': len(trace),
              'check_calls': check_calls, 'build_calls': build_calls}
    for proposal in chosen:
        result['check_calls'] += 1
        if check(proposal) is not None:
            return dict(result, status='final_recheck_failed')
    if not chosen:
        return dict(result, status='no_admissible_packet')
    payload, snapshot = build(chosen)
    result['build_calls'] += 1
    errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=budget)
    if errors or docs_context_budget_tokens(payload) > budget:
        raise ValueError({'invalid_final_packet': errors})
    if payload['answer_supported'] or payload['edit_ready']:
        raise ValueError('unexpected_permission')
    return dict(result, status='completed_first_fit', payload=payload, snapshot=snapshot)


def render_packet(items, *, query_plan):
    rows = []
    for item in items:
        ref = item['_reference_evidence']
        start, end = item['char_span']
        text = ref['raw_document'][start:end]
        if text != item['snippet']:
            raise ValueError('source_window_mismatch')
        row = {'evidence_id': 'ev-' + hashlib.sha256(canonical_projection_bytes(
                   (ref['source'], item['generation_id'], start, end))).hexdigest()[:16],
               'path_or_url': ref['source']['canonical_path'],
               'section': str(item.get('heading_path') or item.get('title') or 'document'),
               'snippet': text, 'version_binding': str(item.get('resolved_version') or 'unversioned'),
               'content_sha256': _source_digest(item), 'project_identity': item['project_identity'],
               'line_start': ref['raw_document'].count('\n', 0, start) + 1,
               'line_end': ref['raw_document'].count('\n', 0, end) + (0 if text.endswith('\n') else 1),
               'authority': item['authority'], 'scope': item.get('scope') or item['doc_scope']}
        if len(row['path_or_url']) > 500 or len(row['section']) > 300 or len(row['version_binding']) > 100:
            raise ValueError('source_field_limit')
        rows.append(row)
    return _payload(rows, query_plan=query_plan), {
        row['evidence_id']: _snapshot_entry(item, row) for item, row in zip(items, rows)}


def read_reason(item, *, question, identity, relaxed=False):
    source = source_window_eligibility(item, question=question, expected_project_identity=identity)
    if not source.eligible:
        return source.reason
    roles = query_constraint_roles(question)
    if any(not _visible_term_present(term, item['snippet'], exact=True)
           for term in (*roles.hard_exact, *roles.bound_subjects)):
        return 'missing_exact_or_subject'
    decision = read_context_admission(item, question=question, expected_project_identity=identity)
    if decision.allowed or (relaxed and decision.reason == 'no_local_topic_witness'):
        return None
    return decision.reason


def inventory(store, *, question, filters, policy, retrieval, context):
    proposals, omissions, seen = [], [], set()
    used = 0
    for hit in retrieval['candidates']:
        document = context._document(hit['source'])
        if not document:
            omissions.append({'id': hit['stable_id'], 'reason': 'missing_source_snapshot'})
            continue
        raw, parents, _ = document
        start, end = hit['char_start'], hit['char_end']
        owners = [p for p in parents if p.char_start <= start and end <= p.char_end]
        if len(owners) != 1:
            omissions.append({'id': hit['stable_id'], 'reason': 'unknown_owner'})
            continue
        owner = owners[0]
        atoms = _atom_spans(raw, owner.char_start, owner.char_end)
        touched = [a for a in atoms if a.start < end and start < a.end and a.atom_type in ('code', 'list', 'table')]
        if policy == 'owner' and touched:
            start, end = owner.char_start, owner.char_end
        key = (hit['source'], start, end)
        if key in seen:
            continue
        seen.add(key)
        reason = None
        if any(not (start <= a.start and a.end <= end) for a in touched):
            reason = 'clipped_structural_atom'
        for atom in touched:
            if atom.atom_type == 'code':
                lines = raw[atom.start:atom.end].strip().splitlines()
                marker = lines[0].lstrip()[:3]
                if len(lines) < 2 or not lines[-1].lstrip().startswith(marker):
                    reason = 'unclosed_structure'
        size = len(raw[start:end].encode())
        if used + size > 12000:
            omissions.append({'id': hit['stable_id'], 'reason': 'proposal_byte_cap'})
            continue
        used += size
        with store._connect() as conn:
            metadata = json.loads(conn.execute('SELECT metadata_json FROM generation_sources WHERE generation_id=? AND source=?',
                (context.scope.snapshot_id, hit['source'])).fetchone()[0])
        metadata.update(char_span=[start, end], generation_id=context.scope.snapshot_id,
                        source_content_hash=context.sources[hit['source']].content_sha256)
        prepared = context.prepare([Chunk(source=hit['source'], text=raw[start:end], chunk_index=0, metadata=metadata)])[0]
        item = dict(prepared.metadata, source=prepared.source, path=prepared.metadata['project_doc_path'],
                    snippet=prepared.text, content=prepared.text)
        pid = hashlib.sha256(canonical_projection_bytes((policy, context.scope.snapshot_id, key))).hexdigest()
        proposals.append({'proposal_id': pid, 'native_rank': hit['native_rank'],
                          'source_identity': hit['source'], 'item': item,
                          'structural_reason': reason, 'policy': policy,
                          'expected_span': [start, end],
                          'owner_span': [owner.char_start, owner.char_end]})
    return proposals, omissions, used


def check_proposal(proposal, *, question, identity, relaxed):
    item = proposal['item']
    if item['char_span'] != proposal['expected_span']:
        return 'proposal_span_changed'
    ref = item.get('_reference_evidence')
    if not ref:
        return 'missing_source_snapshot'
    start, end = item['char_span']
    raw = ref['raw_document']
    atoms = _atom_spans(raw, *proposal['owner_span'])
    touched = [a for a in atoms if a.start < end and start < a.end and a.atom_type in ('code', 'list', 'table')]
    if proposal['policy'] == 'owner' and touched and item['char_span'] != proposal['owner_span']:
        return 'incomplete_owner'
    if any(not (start <= a.start and a.end <= end) for a in touched):
        return 'clipped_structural_atom'
    if proposal['structural_reason']:
        return proposal['structural_reason']
    return read_reason(item, question=question, identity=identity, relaxed=relaxed)


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    protocol, cases, manifest = load_protocol()
    save_json(output / 'protocol.json', protocol)
    rows = []
    for project in sorted({c['project_group'] for c in cases}):
        documents = documents_for(project, manifest)
        root = (output / project / 'corpus').resolve()
        write_project(root, documents)
        with isolated_service(output / project / 'state') as (service, config):
            ingest = index_project(service, config, root)
            save_json(output / project / 'ingest.json', ingest)
            # Copy actual ingested source metadata/content into a passage-enabled research index.
            native_store = service._agent_instance().store
            with native_store._connect() as conn:
                sources = conn.execute('SELECT source, content, metadata_json FROM generation_sources WHERE generation_id=?',
                                      (native_store.active_generation_id(),)).fetchall()
            store = SQLiteStore(output / project / 'passages.db', passage_profile=PassageProfile())
            research_documents = []
            for source in sources:
                metadata = json.loads(source['metadata_json'])
                if not metadata.get('project_docs') or not metadata.get('project_doc_path'):
                    continue
                # Catalog-backed adapter: no invented identity/authority/freshness.
                metadata.update(source_class='project_doc', project_identity=metadata['repository_identity'],
                                authority=metadata['project_doc_authority'])
                research_documents.append(Document(source=source['source'], content=source['content'], metadata=metadata))
            store.add_documents(research_documents)
            metadata = research_documents[0].metadata
            filters = {'project_identity': metadata['project_identity'], 'project_path': str(root), 'source_class': 'project_doc'}
            for case in [c for c in cases if c['project_group'] == project]:
                request = {'project_path': str(root), 'scope': 'project', 'question': case['question']}
                try:
                    baseline = observe_call(service, request)
                    save_json(output / project / (case['id'] + '-baseline.json'), baseline)
                except Exception as exc:
                    save_json(output / project / (case['id'] + '-baseline.json'), {'error': repr(exc)})
                retrieval = store.query_passages(case['question'], filters=filters)
                context = SourceReferenceContext(store, question=case['question'], filters=filters)
                plan = build_documentation_query_plan(case['question']).as_payload()
                for policy in args.policies:
                    proposals, omissions, proposal_bytes = inventory(store, question=case['question'], filters=filters,
                        policy=policy, retrieval=retrieval, context=context)
                    cells = [(b, False) for b in args.budgets]
                    if args.diagnostic_topic_replay and policy == 'owner':
                        cells.append((3000, True))
                    for budget, relaxed in cells:
                        started = time.perf_counter()
                        result = ordered_packet(proposals, budget=budget,
                            check=lambda p: check_proposal(p, question=case['question'],
                                identity=filters['project_identity'], relaxed=relaxed),
                            build=lambda pp: render_packet([p['item'] for p in pp], query_plan=plan))
                        payload = result['payload']
                        assessment = assess_context(case, payload or {'sources': []}, registry_for(project, manifest))
                        row = dict(result, case_id=case['id'], policy=policy, budget=budget,
                            diagnostic_only=policy == 'passage' or relaxed, eligible_for_rollout=False,
                            topic_relaxed=relaxed, assessment=assessment, retrieval=retrieval,
                            proposal_bytes=proposal_bytes, omissions=omissions,
                            raw_snapshot_bytes=sum(len(d[0].encode()) for d in context.documents.values() if d),
                            elapsed_seconds=time.perf_counter()-started,
                            dto_units=docs_context_budget_tokens(payload) if payload else 0)
                        row.pop('snapshot', None)
                        rows.append(row)
                        save_json(output / project / f"{case['id']}-{policy}-{budget}-{'relaxed' if relaxed else 'strict'}.json", row)
    save_json(output / 'results.json', rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--budgets', nargs='+', type=int, choices=(800, 1500, 3000), default=[800, 1500, 3000])
    parser.add_argument('--policies', nargs='+', choices=('passage', 'owner'), default=['passage', 'owner'])
    parser.add_argument('--diagnostic-topic-replay', action='store_true')
    run(parser.parse_args())
