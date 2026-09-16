"""Optional lookup hygiene must reach the actual application lookups."""
from types import SimpleNamespace
import pytest
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


@pytest.mark.parametrize('junk', ['I a in so', 'в от', 'по'])
def test_service_word_residue_does_not_take_a_lookup_slot(junk):
    requirements = SimpleNamespace(concept_queries=(junk,), retrieval_hints=('cache freshness',))
    plan = build_documentation_query_plan('Explain cache freshness', requirements=requirements)
    assert not any(q.text == junk for q in plan.queries[1:])
    assert any(q.text == 'cache freshness' for q in plan.queries)


def test_subject_group_uses_dependency_and_lockfile_within_existing_slots():
    question = 'I changed a dependency version in pubspec.lock. How do we avoid docs for the old version?'
    requirements = build_requirements(question, profile='project_docs_answer')
    plan = build_documentation_query_plan(question, requirements=requirements)
    optional = [q.text for q in plan.queries if q.origin in {'concept_alias', 'retrieval_hint', 'component_rewrite'}]
    assert len(optional) <= 4
    assert any(all(term in text for term in ['dependency', 'version', 'pubspec.lock']) for text in optional)
    assert not any(text == 'I a in do we' for text in optional)
    assert plan.original_question == question
    assert plan == build_documentation_query_plan(question, requirements=requirements)


@pytest.mark.parametrize('anchor', ['pubspec.lock', 'ns.lookup_context', '--no-cache', '--if', 'src/config.yaml', '2.0.1'])
def test_exact_technical_anchors_survive_optional_hygiene(anchor):
    question = f'Explain {anchor} only if not offline and without discarding cached data'
    plan = build_documentation_query_plan(question, requirements=build_requirements(question, profile='project_docs_answer'))
    assert plan.original_question == question
    assert any(q.text == anchor for q in plan.queries if q.origin == 'exact_anchor')
    assert len([q for q in plan.queries if q.origin in {'concept_alias', 'retrieval_hint', 'component_rewrite'}]) <= 4


def test_same_namespace_not_collapsed_and_exact_hint_is_not_duplicated():
    question = 'Compare ns.lookup_context and other.lookup_context'
    requirements = SimpleNamespace(concept_queries=(), retrieval_hints=('ns.lookup_context', 'other.lookup_context'))
    plan = build_documentation_query_plan(question, requirements=requirements)
    texts = [q.text for q in plan.queries]
    assert texts.count('ns.lookup_context') == texts.count('other.lookup_context') == 1


@pytest.mark.parametrize('junk', ['I a in so', 'в от', 'по'])
def test_application_does_not_reintroduce_rejected_residue(tmp_path, junk):
    calls = []
    agent = SimpleNamespace(config=DocmancerConfig(), query=lambda text, **kw: calls.append((text, kw)) or [])
    service = ProjectDocsService(SimpleNamespace(_agent_instance=lambda: agent))
    # Same real requirements owner as production; no fabricated component coverage.
    requirements = build_requirements('Explain cached documentation', profile='project_docs_answer')
    from dataclasses import replace
    requirements = replace(requirements, concept_queries=(junk,), retrieval_hints=('cache freshness',))
    service.query_project_docs(str(tmp_path), 'Explain cached documentation', requirements=requirements, tokens=800, limit=3)
    texts = [text for text, _ in calls]
    assert junk not in texts
    assert 'cache freshness' in texts
    assert len(calls) <= 14
    assert texts[:2] == ['Explain cached documentation'] * 2


def test_comparison_uses_subject_bearing_side_probes_before_single_word_hints():
    question = (
        "How do project documentation and dependency/library documentation differ "
        "in retrieval scope and provenance?"
    )
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    optional = [
        q for q in plan.queries
        if q.origin in {"canonical_intent", "concept_alias", "retrieval_hint", "component_rewrite"}
        and q.query_id.startswith(("query-relation-", "query-concept-", "query-hint-", "query-component-"))
    ]
    relation = [q.text.casefold() for q in optional if q.query_id.startswith("query-relation-")]

    assert len(optional) <= 4
    assert "project documentation dependency documentation" in relation
    assert "project documentation library documentation" in relation
    assert "project documentation retrieval scope provenance" in relation
    assert "dependency library documentation retrieval scope provenance" in relation
    assert not any(q.text.casefold() == "differ" for q in optional)


def test_conditional_relation_keeps_subject_and_negative_states_in_existing_slots():
    question = (
        "What happens in offline mode when the documentation needed for a question "
        "has not been prefetched or indexed yet?"
    )
    requirements = build_requirements(question, profile="project_docs_answer")
    plan = build_documentation_query_plan(question, requirements=requirements)
    relation = [
        q.text.casefold() for q in plan.queries if q.query_id.startswith("query-relation-")
    ]

    assert "documentation needed question not prefetched" in relation
    assert "documentation needed question not indexed" in relation
    assert not any(q.text.casefold() == "happens" for q in plan.queries)
    assert len([
        q for q in plan.queries
        if q.query_id.startswith(("query-relation-", "query-concept-", "query-hint-", "query-component-"))
    ]) <= 4
