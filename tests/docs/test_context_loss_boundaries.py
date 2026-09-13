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


@pytest.mark.parametrize('word', ['repository-wide', 'per-source', 'pre-release', 'blue-green'])
def test_plain_compounds_keep_recall_without_exact_identity(word):
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan, technical_anchors
    question = f'Explain the {word} behavior.'
    plan = build_documentation_query_plan(question).as_payload()
    assert word not in technical_anchors(question)
    lookups = [q for q in plan['queries'] if q['text'] == word]
    assert lookups and all(q['origin'] == 'lexical_topic' for q in lookups)
    assert all(q['query_id'] not in plan['public_query_ids'] for q in lookups)


def test_default_lookup_preserves_a_prose_topic_without_claiming_identity():
    from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
    rows = build_project_retrieval_aliases('Как blue-green работает по умолчанию?')
    assert any(row.text == 'blue-green default' and row.force_context_only for row in rows)
    assert not any(row.intent_id == 'default_behavior' for row in
        build_project_retrieval_aliases('Как blue-green работает?'))


def test_unadmittable_full_candidate_does_not_disable_useful_partial_evidence():
    terms = ['storage', 'compression', 'encoding', 'latency', 'formats', 'deployment', 'quotas', 'transport']
    question = 'Explain ' + ' '.join(terms)
    def source(path, body, qid, query):
        return {'source_class': 'project_doc', 'path': path, 'content': body,
            'project_identity': 'repo', 'authority': 'source_of_truth', 'doc_scope': 'project',
            'lifecycle_status': 'active', 'index_freshness': 'synchronized',
            'retrieval_query_matches': {qid: {'qualified': True, 'query_text': query}}}
    partial = 'Storage compression reduces disk usage.'
    retrieval = {'question': question, 'context_pack': [
        source('docs/large.md', '\n\n'.join(term + ' ' + 'Additional explanatory material. '*120 for term in terms),
               'query-original', question),
        source('docs/short.md', partial, 'query-hint-1', 'storage'),
    ], 'documentation_query_plan': {'original_question': question,
        'unresolved_parts': ['independent requested topics'], 'required_query_ids': ['query-original'],
        'queries': [{'query_id': 'query-original', 'text': question, 'origin': 'original'},
                    {'query_id': 'query-hint-1', 'text': 'storage', 'origin': 'retrieval_hint'}]}}
    payload, _ = project_docs_context(retrieval=retrieval, max_tokens=400)
    assert any(row['snippet'] == partial for row in payload.get('sources', []))
    assert not payload['answer_supported']


@pytest.mark.parametrize('query,body', [
    ('retried', 'retry'), ('retry', 'retried'),
    ('copied', 'copy'), ('copy', 'copied'), ('supplied', 'supply'),
    ('identities', 'identity'), ('identity', 'identities'),
    ('policies', 'policy'), ('policy', 'policies'),
    ('dependencies', 'dependency'),
])
def test_regular_inflection_preserves_visible_procedure(query, body):
    result = qualify_evidence(
        {'query_terms': ['original', 'request', query], 'exact_terms': []},
        query_id='query-original', visible_text=f'{body} the original operation.',
        evidence_text=f'{body} the original operation.',
    )
    assert result.qualified
    assert query in result.trace['body_matched_terms']


@pytest.mark.parametrize('query,body', [
    ('retried', 'retry'), ('copied', 'copy'), ('identities', 'identity'),
    ('policy', 'policies'),
])
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


def test_partial_fallback_cannot_spend_a_surviving_primary_answers_budget():
    question = 'Explain storage compression encoding latency formats deployment quotas transport'
    witness = 'Storage compression encoding latency formats deployment quotas transport are documented here.'
    def source(path, body, qid, query):
        return {'source_class': 'project_doc', 'path': path, 'content': body,
            'project_identity': 'repo', 'authority': 'source_of_truth', 'doc_scope': 'project',
            'lifecycle_status': 'active', 'index_freshness': 'synchronized',
            'retrieval_query_matches': {qid: {'qualified': True, 'query_text': query}}}
    payload, _ = project_docs_context(retrieval={'question': question, 'context_pack': [
        source('docs/complete.md', witness, 'query-original', question),
        source('docs/partial.md', 'Storage compression reduces disk usage.', 'query-hint-1', 'storage'),
    ], 'documentation_query_plan': {'original_question': question,
        'unresolved_parts': ['independent requested topics'], 'required_query_ids': ['query-original'],
        'queries': [{'query_id': 'query-original', 'text': question, 'origin': 'original'},
                    {'query_id': 'query-hint-1', 'text': 'storage', 'origin': 'retrieval_hint'}]}})
    assert any(row['snippet'] == witness for row in payload['sources'])
    assert all(row['path_or_url'] != 'docs/partial.md' for row in payload['sources'])


def test_one_host_lookup_can_retain_complementary_qualified_body_facts():
    question = 'Explain our private deployment policy.'
    lookup = 'storage compression encoding latency formats quotas'
    first = 'Storage compression encoding latency use adaptive settings.'
    second = 'Encoding latency formats quotas have explicit bounds.'
    def source(path, body):
        return {'source_class': 'project_doc', 'path': path, 'content': body,
            'project_identity': 'repo', 'authority': 'source_of_truth', 'doc_scope': 'project',
            'lifecycle_status': 'active', 'index_freshness': 'synchronized',
            'retrieval_query_matches': {'query-lookup-1': {'qualified': True, 'query_text': lookup}}}
    payload, _ = project_docs_context(retrieval={'question': question,
        'context_pack': [source('docs/first.md', first), source('docs/second.md', second)],
        'documentation_query_plan': {'original_question': question,
            'queries': [{'query_id': 'query-original', 'text': question, 'origin': 'original'},
                        {'query_id': 'query-lookup-1', 'text': lookup, 'origin': 'host_lookup'}]}})
    assert {row['snippet'] for row in payload['sources']} == {first, second}
    assert not payload['answer_supported']
    assert 'query-original' not in payload['covered_query_ids']


@pytest.mark.parametrize('facts,qualified', [
    ({}, True), ({'project_identity': 'foreign'}, False),
    ({'stale': True}, False), ({'risk_flags': ['unsafe']}, False),
    ({'project_doc_reason': 'roadmap'}, False),
])
def test_host_qualification_precedes_window_regardless_of_discovery(facts, qualified):
    from docmancer.docs.application._project_docs_service_part03 import _qualify_candidate_lookups
    from docmancer.docs.domain.documentation_query_plan import DocumentationQueryPlan
    lookup = DocumentationLookup('query-lookup-1', 'Storage compression reduces usage',
        'host_lookup', relation='host_lookup', forbidden_catalog_roles=('roadmap',))
    chunk = RetrievedChunk(source='docs/storage.md', chunk_index=0,
        text='Storage compression reduces disk usage.', score=99,
        metadata={'project_identity': 'repo', **facts,
            'retrieval_query_matches': {'query-original': {'qualified': False}},
            'retrieval_query_ids': ()})
    result = _qualify_candidate_lookups([chunk], DocumentationQueryPlan('Частный вопрос', (lookup,)),
        expected_project_identity='repo', lifecycle_intent='current')[0]
    trace = result.metadata['retrieval_query_matches']['query-lookup-1']
    assert trace['qualified'] is qualified
    assert trace['lexical_score'] == 0  # Cross-checking is not a BM25 search hit.
    assert result.metadata['retrieval_query_matches']['query-original']['qualified'] is False
    assert 'query-lookup-1' not in chunk.metadata['retrieval_query_matches']


def test_cross_lane_qualification_retains_exact_identity_and_discovery_scores():
    from docmancer.docs.application._project_docs_service_part03 import _qualify_candidate_lookups
    from docmancer.docs.domain.documentation_query_plan import DocumentationQueryPlan
    lookup = DocumentationLookup('query-lookup-1', 'Use `storage_mode` for compression', 'host_lookup')
    chunk = RetrievedChunk(source='docs/storage.md', chunk_index=0,
        text='Use storage mode for compression.', score=8, metadata={'project_identity': 'repo'})
    plan = DocumentationQueryPlan('original', (lookup,))
    result = _qualify_candidate_lookups([chunk], plan,
        expected_project_identity='repo', lifecycle_intent='current')[0]
    assert not result.metadata['retrieval_query_matches']['query-lookup-1']['qualified']
    tagged = _tag_retrieval_query([chunk], lookup.query_id, lookup.text, lookup,
        expected_project_identity='repo')[0]
    result = _qualify_candidate_lookups([tagged], plan,
        expected_project_identity='repo', lifecycle_intent='current')[0]
    assert result.metadata == tagged.metadata


@pytest.mark.parametrize('trigger,witness', [
    ('the cache expires', 'An expired cache aborts the download.'),
    ('the connection fails', 'A failed connection aborts the download.'),
    ('the worker waits', 'A worker that waited aborts the download.'),
])
def test_requested_trigger_precedes_topical_role_preference(trigger, witness):
    from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates
    lookup = f'What happens when {trigger} before a download starts?'
    def source(body, role):
        return {'path': f'docs/{role}.md', 'snippet': body, 'catalog_role': role,
            'retrieval_query_matches': {'query-lookup-1': {
                'qualified': True, 'match_ratio': 0.5,
                'preferred_catalog_roles': ['runbook']}}}
    topical = source('Before a download starts, the system checks its configuration.', 'runbook')
    expected = source(witness, 'api_contract')
    ranked = _facet_aware_candidates([topical, expected],
        query_text={'query-original': 'Опиши поведение.', 'query-lookup-1': lookup},
        required_query_ids={'query-original', 'query-lookup-1'}, host_query_ids={'query-lookup-1'})
    assert ranked[0] is expected
    assert expected['retrieval_query_matches']['query-lookup-1']['match_ratio'] == 0.5


@pytest.mark.parametrize('body', [
    '# Cache expires\n\nThe download starts normally.',
    '[Cache expires](cache.md)\n\nThe download starts normally.',
])
def test_condition_preference_never_uses_navigation(body):
    from docmancer.docs.application.context_candidate_ranking import _condition_body_priority
    assert _condition_body_priority('What happens when the cache expires?', body) == 0


@pytest.mark.parametrize('existing_qualified', [False, True])
def test_cross_lane_witness_survives_actual_query_window(tmp_path, existing_qualified):
    from types import SimpleNamespace
    from docmancer.docs.application.project_docs_service import ProjectDocsService
    original = 'Describe private deployment'
    class Agent:
        config = SimpleNamespace(query=SimpleNamespace(default_limit=1))
        def query(self, query, *, limit, budget, expand, filters):
            if query != original:
                return []
            return [RetrievedChunk(source=path, chunk_index=0, text=body, score=score,
                metadata={'project_identity': filters['project_identity'], 'token_estimate': 20})
                for path, body, score in [
                    ('docs/overview.md', 'Describe private deployment procedures.'
                     if existing_qualified else 'Unrelated navigation.', 10),
                    ('docs/storage.md', 'Storage compression reduces disk usage.', 1)]]
    class Facade:
        def _agent_instance(self):
            return Agent()
    chunks = ProjectDocsService(Facade()).query_project_docs(str(tmp_path), original,
        lookup_queries=('Storage compression reduces usage',), limit=1)
    assert [chunk.source for chunk in chunks] == [
        'docs/overview.md' if existing_qualified else 'docs/storage.md']
    assert chunks[0].metadata['retrieval_query_ids'] == (
        'query-original' if existing_qualified else 'query-lookup-1',)


@pytest.mark.parametrize('question,body', [
    ('How does request validation differ from routing requests?',
     'The dispatcher routes requests to the selected worker.'),
    ('What is the difference between selecting records and validating records?',
     'The validator validates records before storage.'),
])
def test_comparison_preserves_named_operation_over_topical_nouns(question, body):
    from docmancer.docs.application.context_candidate_ranking import _facet_aware_candidates
    def source(snippet, role):
        return {'snippet': snippet, 'catalog_role': role,
            'retrieval_query_matches': {'query-lookup-1': {
                'qualified': True, 'match_ratio': 0.5, 'preferred_catalog_roles': ['overview']}}}
    overview = source('Request validation and records are documented here.', 'overview')
    witness = source(body, 'api_contract')
    ranked = _facet_aware_candidates([overview, witness], query_text={'query-lookup-1': question},
        required_query_ids={'query-lookup-1'}, host_query_ids={'query-lookup-1'})
    assert ranked[0] is witness


@pytest.mark.parametrize('body', [
    '# Routing requests\n\nGeneric request notes.',
    '[Routing requests](routing.md)\n\nGeneric request notes.',
])
def test_comparison_operation_requires_visible_body(body):
    from docmancer.docs.application.context_candidate_ranking import _comparison_action_priority
    assert _comparison_action_priority(
        'How does request validation differ from routing requests?', body) == 0
