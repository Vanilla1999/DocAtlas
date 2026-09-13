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
