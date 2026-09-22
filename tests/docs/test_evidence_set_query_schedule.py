"""Search words propose raw candidates; they do not become answer obligations."""
from dataclasses import replace
import pytest

from docmancer.docs.application.need_query_schedule import schedule_need_queries
from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.domain.documentation_query_plan import (
    DocumentationLookup, DocumentationQueryPlan, build_documentation_query_plan)
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references


def schedule(question, *, optional_limit=12, plan=None):
    refs = resolve_references(question, catalog=(), scope=ScopeKey('p', '', 'g'))
    return schedule_need_queries(plan or build_documentation_query_plan(question, requirements=build_requirements(question, profile="project_docs_answer")),
        compile_need_contracts(question, refs), optional_limit=optional_limit)


@pytest.mark.parametrize('question,focus', [
    ('Из каких компонентов состоит origin в CORS?', 'origin'),
    ('Из каких частей состоит endpoint в TransportHub?', 'endpoint'),
    ('What components constitute origin in CorsHub?', 'origin'),
    ('Name four types of timeout in Orbit and explain what each limits.', 'timeout'),
    ('Назови четыре типа timeout в Orbit и объясни, что ограничивает каждый.', 'timeout'),
    ('Как записать отрицательное имя boolean option: важен ли пробел перед /?', 'boolean option'),
])
def test_question_focus_is_searched_not_just_its_namespace(question, focus):
    rows = schedule(question)
    assert any(row.text == focus for row in rows), [(r.origin, r.text) for r in rows]
    assert len(rows) <= 12


def test_focal_probes_are_private_search_proposals_not_new_requirements():
    rows = schedule('Из каких компонентов состоит origin в CORS?')
    focal = next(row for row in rows if row.text == 'origin')
    assert focal.origin == 'retrieval_hint'
    assert focal.facet_id is None and not focal.coverage_required
    assert focal.public_parent_query_id is None and focal.relation == 'host_lookup'
    assert focal.need_relation is None


def test_one_query_per_need_precedes_a_second_redundant_direction():
    question = ' '.join(f'What is Courier{i} default timeout?' for i in range(20))
    root = DocumentationLookup('query-original', question, 'original')
    # Existing budget, deliberately full of competing duplicates for the first need.
    extras = tuple(DocumentationLookup(f'query-hint-{i}', f'Courier0 timeout detail{i}',
        'retrieval_hint', False, relation='host_lookup') for i in range(12))
    rows = schedule(question, optional_limit=4, plan=DocumentationQueryPlan(question, (root, *extras)))
    assert len(rows) == 4
    for i, row in enumerate(rows):
        assert f'Courier{i}' in row.text


def test_explicit_source_and_user_lookups_keep_priority():
    q = 'Из каких компонентов состоит origin в CORS?'
    plan = build_documentation_query_plan(q, explicit_path='Guide.md', lookup_queries=('cross-site calls',))
    rows = schedule(q, optional_limit=3, plan=plan)
    assert [r.origin for r in rows[:2]] == ['exact_path', 'host_lookup']
    assert rows[2].text == 'origin'


def test_identical_search_text_is_deduplicated_but_code_case_is_not():
    q = 'Explain client dispatch.'
    root = DocumentationLookup('query-original', q, 'original')
    values = ('Foo.run', 'Foo.run', 'foo.run', q)
    extra = tuple(DocumentationLookup(f'query-lookup-{i}', x, 'host_lookup', False,
        relation='host_lookup') for i,x in enumerate(values))
    rows = schedule(q, plan=DocumentationQueryPlan(q, (root,*extra)))
    assert [r.text for r in rows] == ['Foo.run', 'foo.run']


def test_quoted_space_and_punctuation_are_not_normalized():
    question = 'Explain the function ` /--disabled`.'
    rows = schedule(question)
    assert any(' /--disabled' in r.text for r in rows)
    assert all(r.public_parent_query_id is None for r in rows if r.query_id.startswith('query-focus-'))


@pytest.mark.parametrize('limit', [-1, 13, 100])
def test_explicit_budget_cannot_exceed_twelve_or_be_negative(limit):
    with pytest.raises(ValueError):
        schedule('What is QueueDriver default timeout?', optional_limit=limit)


def test_zero_optional_slots_means_no_hidden_request():
    assert schedule('Из каких компонентов состоит origin в CORS?', optional_limit=0) == ()


def test_search_proposal_cannot_read_evaluation_answers(monkeypatch):
    from pathlib import Path
    q = 'Из каких компонентов состоит origin в CORS?'
    def forbidden(*args, **kwargs):
        raise AssertionError('query scheduler attempted I/O')
    with monkeypatch.context() as m:
        m.setattr(Path, 'read_text', forbidden)
        m.setattr('builtins.open', forbidden)
        rows = schedule(q)
    assert all('8080' not in r.text and 'scheme-a' not in r.text for r in rows)


def test_no_baseline_optional_work_cannot_turn_into_a_larger_arm():
    q = 'Name four types of timeout and explain what each limits.'
    root_only = DocumentationQueryPlan(q, (DocumentationLookup('query-original', q, 'original'),))
    assert schedule(q, plan=root_only) == ()


def test_reapplying_scheduler_does_not_multiply_slots_or_change_question():
    from docmancer.docs.application.need_query_schedule import scheduled_plan
    q = 'Из каких компонентов состоит origin в CORS?'
    plan = build_documentation_query_plan(q, requirements=build_requirements(q, profile='project_docs_answer'))
    first, rows = scheduled_plan(plan)
    second, again = scheduled_plan(first)
    assert second == first and again == rows
    assert first.original_question == plan.original_question
    assert first.component_contract == plan.component_contract
    assert first.unresolved_parts == plan.unresolved_parts
    assert [x for x in first.queries if x in plan.queries] == list(plan.queries)


def test_no_query_slice_is_minted_from_a_forged_focus_span():
    from docmancer.docs.domain.need_contracts import QuerySpan
    q = 'Name four timeout types in CourierHub and explain what each limits.'
    refs = resolve_references(q, catalog=(), scope=ScopeKey('p', '', 'g'))
    contract = compile_need_contracts(q, refs)[0]
    forged = replace(contract, focus_spans=(QuerySpan(-5, 900),))
    plan = build_documentation_query_plan(q, requirements=build_requirements(q, profile='project_docs_answer'))
    rows = schedule_need_queries(plan, (forged,))
    assert not any(r.query_id.startswith('query-focus-') for r in rows)

@pytest.mark.parametrize('question,topic', [
    ('Перечисли способы включить strict mode, включая field, annotation, config и validation call.', 'strict mode'),
    ('List ways to enable compression policy, including field, annotation, config and validation call.', 'compression policy'),
])
def test_requested_categories_are_searchable_only_with_their_original_topic(question, topic):
    plan = build_documentation_query_plan(question,
        lookup_queries=tuple(f'detail channel {i}' for i in range(8)))
    # Supply the same legacy allowance without priority host proposals filling it.
    extras = tuple(replace(row, origin='retrieval_hint') for row in plan.queries
                   if row.origin == 'host_lookup')
    plan = replace(plan, queries=tuple(row for row in plan.queries if row.origin != 'host_lookup') + extras)
    rows = schedule(question, plan=plan)
    focal = [r.text for r in rows if r.query_id.startswith('query-focus-')]
    assert f'{topic} config' in focal
    assert f'{topic} field' in focal
    assert not {'config', 'field', 'annotation', 'validation call'} & set(focal)
    assert len(rows) <= 12
