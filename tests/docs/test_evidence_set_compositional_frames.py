"""Original-surface composition, not answer-guided rewrites or lexical proof."""
import pytest
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references


def compile_question(question):
    return compile_need_contracts(question, resolve_references(
        question, catalog=(), scope=ScopeKey('p', '', 'g1')))


def pick(rows, predicate):
    matches = [r for r in rows if predicate(r)]
    assert len(matches) == 1, [(r.need.relation, r.requirement) for r in rows]
    return matches[0]


def text_at(question, spans):
    return [question[s.start:s.end] for s in spans]


@pytest.mark.parametrize('count,expected', [('four', 4), ('six', 6), ('4', 4), ('четыре', 4), ('шесть', 6)])
def test_explicit_count_and_each_explanation_remain_requested(count, expected):
    q = (f'Назови {count} типа timeout в Orbit и объясни, что ограничивает каждый.'
         if count in {'четыре', 'шесть'} else
         f'Name {count} types of timeout in Orbit and explain what each limits.')
    rows = compile_question(q)
    need = pick(rows, lambda n: n.requirement == 'set_with_explanations')
    assert need.expected_count == expected
    assert 'timeout' in text_at(q, need.focus_spans)
    assert 'Orbit' in need.need.query_span_text
    assert need.need.query_span_text == q


@pytest.mark.parametrize('question', [
    'How does Orbit restrict package candidates and why?',
    'Как Orbit ограничивает версии пакетов и почему?',
    'How does Orbit choose versions when preview is disabled and why?',
])
def test_how_and_why_are_bound_complementary_needs(question):
    rows = compile_question(question)
    assert {n.need.relation for n in rows} == {'mechanism', 'reason'}
    mechanism = next(n for n in rows if n.need.relation == 'mechanism')
    reason = next(n for n in rows if n.need.relation == 'reason')
    assert reason.prerequisite_need_ids == (mechanism.need.need_id,)
    assert reason.need.context == mechanism.need.query_span_text
    assert reason.constraint_spans == mechanism.constraint_spans
    assert all(question[n.need.query_span_start:n.need.query_span_end] == n.need.query_span_text for n in rows)


@pytest.mark.parametrize('owner', ['QueueTasks', '`ΣWorker`', 'AnotherDispatcher'])
def test_callable_alternative_is_not_a_required_negative_answer(owner):
    q = f'Может ли task function для {owner} быть обычной def, а не async def?'
    rows = compile_question(q)
    row = pick(rows, lambda n: n.need.relation == 'callable_form')
    assert 'для' not in row.need.hard_exact
    assert owner.strip('`').casefold() in {x.casefold() for x in row.need.hard_exact}
    assert text_at(q, row.alternative_spans) == ['обычной def', 'async def']
    assert not row.constraint_spans
    assert row.need.query_span_text == q


@pytest.mark.parametrize('question,subject,sides', [
    ('Which page title wins when the navigation configuration and Markdown content define different titles?',
     'page title', ['navigation configuration', 'Markdown content']),
    ('Which setting wins when the command line and configuration file define different values?',
     'setting', ['command line', 'configuration file']),
    ('Что имеет приоритет, когда command option и config file задают разные значения?',
     '', ['command option', 'config file']),
])
def test_conflicting_property_is_precedence_not_definition(question, subject, sides):
    row = pick(compile_question(question), lambda n: n.need.relation == 'precedence')
    assert sides == text_at(question, row.alternative_spans)
    assert row.constraint_spans and any('different' in t or 'разные' in t for t in text_at(question, row.constraint_spans))
    assert not any(n.need.relation == 'definition' for n in compile_question(question))
    if subject:
        assert subject in text_at(question, row.focus_spans)


def test_requested_categories_remain_question_categories_not_answer_values():
    q = 'Перечисли способы включить strict mode, включая field, annotation, config и validation call.'
    row = pick(compile_question(q), lambda n: n.requirement == 'set')
    assert text_at(q, row.category_spans) == ['field', 'annotation', 'config', 'validation call']
    assert row.expected_count is None
    assert 'strict mode' in text_at(q, row.focus_spans)
    assert not any(t in row.need.hard_exact for t in ['ConfigDict', 'Strict'])


@pytest.mark.parametrize('question', [
    'Name four timeout types and also identify the deployment key.',
    'Name four timeout types and remove all stored indexes.',
    'List ways to enable strict mode, including field only for admins.',
])
def test_unrecognized_tail_is_not_discarded_to_compile_complete_need(question):
    rows = compile_question(question)
    assert any(n.interpretation == 'unresolved' for n in rows)
    assert any(n.need.query_span_end == len(question) for n in rows)


def test_literal_words_do_not_create_operators_or_boundaries():
    q = 'What does function `how and why` return?'
    rows = compile_question(q)
    assert not any(n.need.relation in {'mechanism', 'reason'} for n in rows)
    assert any('how and why' in n.need.hard_exact for n in rows)


def test_alternative_condition_is_preserved_and_not_a_second_answer():
    q = 'Can a function for QueueTasks be normal def rather than async def when preview is disabled?'
    row = pick(compile_question(q), lambda n: n.need.relation == 'callable_form')
    assert text_at(q, row.alternative_spans) == ['normal def', 'async def']
    assert any('preview is disabled' in s for s in text_at(q, row.constraint_spans))


def test_reference_mismatch_cannot_certify_new_compositional_form():
    q = 'Name four types of timeout and explain what each limits.'
    refs = resolve_references('What is a timeout?', catalog=(), scope=ScopeKey('p', '', 'g1'))
    assert all(n.interpretation == 'unresolved' for n in compile_need_contracts(q, refs))


@pytest.mark.parametrize('question,relations', [
    ('How does Orbit restrict package candidates and why?', {'mechanism', 'reason'}),
    ('Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый.', {'enumeration'}),
    ('Может ли task function для BackgroundTasks быть обычной def, а не async def?', {'callable_form'}),
    ('Which page title wins when the navigation configuration and Markdown content define different titles?', {'precedence'}),
])
def test_actual_planner_preserves_composed_needs_without_parent_authority(question, relations):
    from docmancer.docs.application.evidence_requirements import build_requirements
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    reqs = build_requirements(question, profile='project_docs_answer')
    plan = build_documentation_query_plan(question, requirements=reqs)
    rows = [q for q in plan.queries if q.query_id.startswith('query-composed-')]
    assert relations <= {q.need_relation for q in rows}
    assert all(q.facet_id is None and q.public_parent_query_id is None and not q.coverage_required for q in rows)
    assert not any(q.relation == 'audited_rewrite' for q in rows)
    if 'precedence' in relations:
        assert not any(c['obligation_kind'] == 'definition' for c in plan.component_contract)
        assert any(c['relation'] == 'precedence' for c in plan.component_contract)


def test_only_tail_does_not_turn_alternative_into_an_unconditional_question():
    q = 'Can a function for QueueTasks be normal def rather than async def only in version 2.1?'
    row = pick(compile_question(q), lambda n: n.need.relation == 'callable_form')
    assert any('only in version 2.1' in t for t in text_at(q, row.constraint_spans))


def test_category_disjunction_is_not_a_required_conjunctive_set():
    q = 'List ways to enable strict mode, including field or annotation.'
    assert all(n.interpretation == 'unresolved' for n in compile_question(q))


@pytest.mark.parametrize('question', [
    'Name four types of timeout in Orbit and identify the private key.',
    'How does Orbit choose versions and how is the private registry configured and why?',
    'Which ' + 'long-property ' * 30 + 'wins when the command line and configuration file define different values?',
    'Name 99999999999999999 types of timeout and explain what each means.',
])
def test_nested_requests_and_unbounded_operands_do_not_receive_complete_interpretation(question):
    assert all(n.interpretation == 'unresolved' for n in compile_question(question))
