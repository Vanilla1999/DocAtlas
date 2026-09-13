"""Counterexamples for information lost before and after candidate admission."""
import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.retrieval.dispatch import RetrievalDispatcher
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.context_query_probes import independent_query_probes
from docmancer.docs.application._project_docs_service_part03 import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup


@pytest.mark.parametrize('query,body', [
    ('retried', 'retry'), ('retry', 'retried'),
    ('copied', 'copy'), ('copy', 'copied'), ('supplied', 'supply'),
])
def test_regular_inflection_preserves_visible_procedure(query, body):
    result = qualify_evidence(
        {'query_terms': ['original', 'request', query], 'exact_terms': []},
        query_id='query-original', visible_text=f'{body} the original operation.',
        evidence_text=f'{body} the original operation.',
    )
    assert result.qualified
    assert query in result.trace['body_matched_terms']


@pytest.mark.parametrize('query,body', [('retried', 'retry'), ('copied', 'copy')])
def test_inflection_never_changes_an_explicit_identifier(query, body):
    result = qualify_evidence(
        {'query_terms': [query], 'exact_terms': [query]},
        query_id='query-original', visible_text=body, evidence_text=body,
    )
    assert not result.qualified


def test_source_quota_preserves_body_witness_over_repeated_heading_hits():
    config = DocmancerConfig()
    config.retrieval.max_sections_per_source = 2
    dispatcher = RetrievalDispatcher(store=object(), config=config)
    def chunk(index, text, source='docs/guide.md'):
        return RetrievedChunk(source=source, chunk_index=index, text=text, score=10-index,
            metadata={'source_class': 'project_file', 'parent_logical_id': f'parent-{index}',
                      'title': 'Storage retention configuration'})
    intro = chunk(0, 'Storage is configured by the operator.')
    other = chunk(1, 'Storage retention is documented here.', 'docs/other.md')
    overview = chunk(2, 'Configuration examples follow.')
    witness = chunk(3, '| Setting | Meaning |\n|---|---|\n| retention | Storage retention configuration in days. |')
    ranked = dispatcher._rerank_intent_matches('storage retention configuration', [intro, other, overview, witness])
    # Preserve source diversity and the quota; choose the better body within it.
    assert [row.source for row in ranked] == [intro.source, other.source, overview.source, witness.source]
    selected = dispatcher._limit_sections_per_source(ranked, limit=3)
    assert witness in selected
    assert other in selected
    assert len(selected) == 3


def test_host_lookup_does_not_displace_the_requested_procedure():
    question = 'Explain polling and retry after preparation.'
    lookup = 'When should the original request be retried?'
    def source(path, body, authority):
        return dict(source_class='project_doc', path=path, content=body,
                    project_identity='repo', authority=authority, doc_scope='project',
                    lifecycle_status='active', index_freshness='synchronized',
                    retrieval_query_ids=['query-lookup-1'], retrieval_query_matches={
                        'query-lookup-1': {'qualified': True, 'query_text': lookup,
                            'query_terms': ['original', 'request', 'retried']}})
    procedure = 'After preparation, finish polling and retry the original request.'
    payload, _ = project_docs_context(retrieval={
        'question': question,
        'context_pack': [
            source('docs/authoring.md', 'Create a document before the original request is retried.', 'source_of_truth'),
            source('docs/lifecycle.md', procedure, 'supporting'),
        ],
        'documentation_query_plan': {'original_question': question,
            'queries': [{'query_id': 'query-original', 'text': question, 'origin': 'original'},
                        {'query_id': 'query-lookup-1', 'text': lookup, 'origin': 'host_lookup'}]},
    })
    assert any(procedure == row['snippet'] for row in payload.get('sources', []))
    assert payload['answer_supported'] is False


def test_independent_lookup_cannot_drop_a_required_acronym():
    question = 'Which task ID does enqueue_task return?'
    body = 'The enqueue_task function returns a task for subsequent processing.'
    lookup = DocumentationLookup('query-lookup-1', question, 'host_lookup', False, relation='host_lookup')
    chunk = RetrievedChunk(source='docs/tasks.md', chunk_index=0, text=body, score=1)
    direct = _tag_retrieval_query([chunk], lookup.query_id, question, lookup)[0]
    assert not direct.metadata['retrieval_query_matches'][lookup.query_id]['qualified']
    independent = independent_query_probes({'snippet': body}, {'queries': [{
        'query_id': lookup.query_id, 'text': question, 'origin': 'host_lookup', 'relation': 'host_lookup',
    }]})
    assert not independent.get(lookup.query_id, {}).get('qualified')


@pytest.mark.parametrize('boundary', ['dominated', 'other_source', 'different_public_direction', 'incomparable'])
def test_heading_boost_cannot_replace_strictly_richer_same_source_body(boundary):
    from dataclasses import dataclass, field
    from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
    from docmancer.docs.domain.project_query_intent import classify_project_query_intent

    @dataclass
    class Chunk:
        content: str
        heading_path: str
        score: float
        metadata: dict = field(default_factory=dict)
        path: str = 'docs/storage.md'

    question = 'How does storage retention remove expired records?'
    def candidate(body, heading, score):
        trace = qualify_evidence({'query_terms': ['storage', 'retention', 'remove', 'expired', 'records'],
            'exact_terms': []}, query_id='query-original', visible_text=body, evidence_text=body).trace
        return Chunk(body, heading, score, {'retrieval_query_matches': {'query-original': trace}})
    overview = candidate('Storage retention keeps records.', 'Storage retention records', 10)
    witness = candidate('Storage retention will remove expired records.', 'Operation', 1)
    if boundary == 'other_source':
        witness.path = 'docs/other.md'
    elif boundary == 'different_public_direction':
        overview.metadata['retrieval_query_matches']['query-lookup-1'] = {'qualified': True}
    elif boundary == 'incomparable':
        witness = candidate('Retention will remove expired records.', 'Operation', 1)
    result = rerank_project_doc_chunks([overview, witness], question=question,
        intent=classify_project_query_intent(question), limit=1)
    assert result[0].content == (witness if boundary == 'dominated' else overview).content


def test_partial_body_support_does_not_depend_on_original_discovery_route():
    question = 'Explain storage compression and identify our private deployment configuration.'
    body = 'Storage compression reduces disk usage.'
    retrieval = {'question': question, 'context_pack': [{
        'source_class': 'project_doc', 'path': 'docs/storage.md', 'content': body,
        'project_identity': 'repo', 'authority': 'source_of_truth', 'doc_scope': 'project',
        'lifecycle_status': 'active', 'index_freshness': 'synchronized',
        'retrieval_query_matches': {'query-hint-1': {
            'qualified': True, 'query_text': 'storage', 'query_terms': ['storage']}},
    }], 'documentation_query_plan': {'original_question': question,
        'unresolved_parts': ['private deployment configuration'],
        'queries': [{'query_id': 'query-original', 'text': question, 'origin': 'original'},
                    {'query_id': 'query-hint-1', 'text': 'storage', 'origin': 'retrieval_hint'}]}}
    payload, _ = project_docs_context(retrieval=retrieval)
    assert any(row['snippet'] == body for row in payload.get('sources', []))
    assert payload['answer_supported'] is False
    assert 'query-original' not in payload['covered_query_ids']


def test_partial_projection_preserves_distinguishing_body_within_budget():
    question = 'Which signal distinguishes cancelling a job from a normal finish? Also describe our private deployment.'
    witness = 'Cancelling a job emits the STOPPED signal; a normal finish is silent.'
    def source(body, heading):
        return {'source_class': 'project_doc', 'path': 'docs/jobs.md', 'content': body,
            'heading_path': heading, 'project_identity': 'repo', 'authority': 'source_of_truth',
            'doc_scope': 'project', 'lifecycle_status': 'active', 'index_freshness': 'synchronized',
            'retrieval_query_matches': {'query-hint-1': {
                'qualified': True, 'query_text': 'finish', 'query_terms': ['finish']}}}
    payload, _ = project_docs_context(max_tokens=400, retrieval={
        'question': question, 'context_pack': [
            source('A normal finish closes the job.', question),
            source(witness, 'Cancellation'),
        ], 'documentation_query_plan': {'original_question': question,
            'unresolved_parts': ['private deployment'], 'queries': [
                {'query_id': 'query-original', 'text': question, 'origin': 'original'},
                {'query_id': 'query-hint-1', 'text': 'finish', 'origin': 'retrieval_hint'}]}})
    assert any('STOPPED' in row['snippet'] for row in payload.get('sources', []))
    assert not payload['answer_supported']
