"""Search hypotheses do not own source restrictions or parent equivalence."""
from dataclasses import replace
import pytest
from docmancer.docs.domain import documentation_query_plan as planner
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases, ProjectRetrievalAlias


@pytest.mark.parametrize('question', [
    'Can the application run offline when documentation is not cached?',
    'Как работает приложение без сети, если документации нет в кэше?',
])
def test_offline_behavior_does_not_invent_testing(question):
    aliases = build_project_retrieval_aliases(question)
    assert any(a.intent_id == 'offline_usage' for a in aliases)
    assert not any('test suite' in a.text or a.text == 'DOCATLAS_OFFLINE' for a in aliases)


@pytest.mark.parametrize('question', ['How do I run the offline test suite with pytest?',
    'Explain offline runtime behavior and offline tests'])
def test_explicit_offline_tests_keep_both_requested_subjects(question):
    aliases = build_project_retrieval_aliases(question)
    assert any('offline test suite' in a.text for a in aliases)
    assert any('offline mode' in a.text for a in aliases)
    assert len(aliases) <= 4


@pytest.mark.parametrize('question', [
    'Я изменил версию зависимости. Как обновится документация?',
    'I changed a dependency version in pubspec.lock. When will docs update?',
    'I refreshed a dependency. Which documentation version is now used?',
])
def test_dependency_change_does_not_become_document_file_sync(question):
    assert not any(a.intent_id == 'project_docs_sync' for a in build_project_retrieval_aliases(question))


@pytest.mark.parametrize('question', [
    'I changed a Markdown file. When does search see the update?',
    'What happens after I delete a project documentation file?',
    'Я удалил Markdown файл. Что произойдёт с поиском?',
    'How do I sync project documentation?',
])
def test_document_file_change_retains_sync_direction(question):
    assert any(a.intent_id == 'project_docs_sync' for a in build_project_retrieval_aliases(question))


@pytest.mark.parametrize('count', [1, 3])
def test_weak_alias_cannot_restrict_original_or_exact_or_audit_it(monkeypatch, count):
    question = 'How does ns.lookup_context work offline without credentials?'
    before = planner.build_documentation_query_plan(question, explicit_path='docs/source.md')
    alias = ProjectRetrievalAlias('offline_usage', 'offline mode', True, 'en',
        ('runbook',), ('api_contract',), ('credentials',))
    monkeypatch.setattr(planner, 'build_project_retrieval_aliases',
        lambda text: tuple(replace(alias, text=f'offline mode {i}') for i in range(count)))
    after = planner.build_documentation_query_plan(question, explicit_path='docs/source.md')
    assert before.original_question == after.original_question == question
    assert before.explicit_paths == after.explicit_paths == ('docs/source.md',)
    for q in after.queries:
        if q.origin in {'original', 'exact_anchor', 'exact_path'}:
            assert not q.preferred_catalog_roles
            assert not q.forbidden_catalog_roles
            assert not q.forbidden_evidence_terms
        if q.origin == 'canonical_intent':
            assert q.relation == 'host_lookup'
            assert q.public_parent_query_id is None
            assert q.forbidden_catalog_roles == ('api_contract',)


def test_alias_does_not_restrict_unscoped_original_or_exact():
    plan = planner.build_documentation_query_plan('How does ns.lookup_context work offline?')
    for q in plan.queries:
        if q.origin in {'original', 'exact_anchor'}:
            assert not q.preferred_catalog_roles
            assert not q.forbidden_catalog_roles
            assert not q.forbidden_evidence_terms


def test_shared_topic_does_not_audit_different_conditional_questions():
    plan = planner.build_documentation_query_plan(
        'How does offline mode work if cached documents are missing?',
        lookup_queries=('How does offline mode work when the cache is complete?',))
    for q in plan.queries:
        if q.origin in {'canonical_intent', 'host_lookup'}:
            assert q.relation == 'host_lookup'
            assert q.public_parent_query_id is None


def test_host_topic_cannot_audit_away_an_extra_condition():
    plan = planner.build_documentation_query_plan('Explain the indexing pipeline',
        lookup_queries=('How does chunking work if documents contain no headings?',))
    assert not any(q.relation == 'audited_rewrite' for q in plan.queries)
