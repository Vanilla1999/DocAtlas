"""Event/version vocabulary cannot select the lifecycle of a source document."""
from types import SimpleNamespace
import pytest
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.domain.lifecycle_policy import lifecycle_intent, lifecycle_filters_for_intent
from docmancer.docs.domain.project_query_intent import classify_project_query_intent


@pytest.mark.parametrize('question', [
    'I changed a package version. How do we avoid docs for the old version?',
    'I added a dependency. How can we avoid an old result?',
    'I removed a dependency. What prevents incorrect docs?',
    'How does the cache prevent reuse of previous results?',
    'Я изменил версию зависимости в lockfile. Как избежать документации старой версии?',
    'Как кэш предотвращает использование предыдущих результатов?',
    'Как реализовать кнопку для закрытой заявки?',
    'prepare_docs вернул отменённый job_id. Что делать дальше?',
])
def test_current_policy_is_not_a_history_lookup(question):
    assert classify_project_query_intent(question).name != 'release_history'
    assert lifecycle_intent(question) == 'current'
    assert 'active' in lifecycle_filters_for_intent(lifecycle_intent(question))['lifecycle_status']['in']


@pytest.mark.parametrize('question,expected', [
    ('Which superseded rollout plan approved the previous policy?', 'historical'),
    ('Which completed incident document explains the failure?', 'historical'),
    ('Какой отменённый план описывал прежнюю политику?', 'historical'),
    ('Compare the current policy with the superseded one', 'either'),
    ('Сравни текущую политику с отменённой', 'either'),
    ('What changed in release 2.0?', 'current'),
    ('What is the history of releases?', 'current'),
    ('Что изменилось в релизе 3.4?', 'current'),
])
def test_explicit_document_lifecycle_is_preserved(question, expected):
    assert lifecycle_intent(question) == expected


@pytest.mark.parametrize('question', ['What changed in release 2.0?', 'Что изменилось в релизе 3.4?'])
def test_release_question_still_finds_an_active_changelog(question):
    assert classify_project_query_intent(question).name == 'release_history'
    assert lifecycle_intent(question) == 'current'


def test_effective_service_filters_retain_current_candidate_and_project_scope(tmp_path):
    config = DocmancerConfig()
    identity = ProjectDocsService._repository_identity(tmp_path)
    calls = []
    rows = [RetrievedChunk(source=f'docs/{state}.md', chunk_index=0,
        text='The cache prevents old dependency documentation by validating the lockfile version.', score=1,
        metadata={'project_identity': identity, 'project_path': str(tmp_path),
                  'source_class': 'project_file', 'lifecycle_status': state, 'doc_scope': 'project',
                  'project_doc_path': f'docs/{state}.md'}) for state in ['active', 'superseded']]
    def query(text, **kwargs):
        calls.append((text, kwargs))
        statuses = kwargs['filters']['lifecycle_status']['in']
        return [r for r in rows if r.metadata['lifecycle_status'] in statuses]
    agent = SimpleNamespace(config=config, query=query)
    service = ProjectDocsService(SimpleNamespace(_agent_instance=lambda: agent))
    question = 'I changed a package version in lockfile. How do we avoid docs for the old version?'
    requirements = build_requirements(question, profile='project_docs_answer')
    result = service.query_project_docs(str(tmp_path), question, requirements=requirements,
        tokens=800, limit=3, scope='project')
    assert [r.source for r in result] == ['docs/active.md']
    assert calls[0][0] == question
    assert len(calls) <= 14  # existing original + authoritative + 12 supplementals
    for _, kwargs in calls:
        filters = kwargs['filters']
        assert filters['project_identity'] == identity
        assert filters['project_path'] == str(tmp_path)
        assert filters['doc_scope'] == 'project'
        assert filters['source_class'] == 'project_file'
        assert filters['lifecycle_status']['in'] == ['active', 'current']
