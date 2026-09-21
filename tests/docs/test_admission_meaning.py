"""Bounded interpretation preserves source slots, not just code-token overlap."""
import pytest
from docmancer.docs.domain.admission_meaning import compile_admission_demands, same_supported_meaning
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references


def demands(question):
    refs = resolve_references(question, catalog=(), scope=ScopeKey('p', '', 'g1'))
    return compile_admission_demands(question, refs)


def demand(question):
    result = demands(question)
    assert len(result) == 1 and not result[0].unsupported_spans
    return result[0]


@pytest.mark.parametrize('left,right,operator', [
    ('What is the default timeout?', 'Please explain precisely what the documented default timeout is.', 'default'),
    ('What is RelayClient default timeout?', 'Какой таймаут по умолчанию у RelayClient?', 'default'),
    ('Which takes precedence: nav title or page title?', 'Что имеет приоритет: nav title или page title?', 'precedence'),
    ('When do QueueTasks run relative to response delivery?', 'Когда выполняется QueueTasks относительно response delivery?', 'temporal_order'),
    ('Can a handler for QueueHub be synchronous?', 'Может ли handler для QueueHub быть синхронной?', 'callable_form'),
    ('Which ways enable strict mode?', 'Какие способы включают strict mode?', 'enumeration'),
    ('How do transport keys map to protocols?', 'Как transport keys сопоставляются с protocols?', 'mapping'),
    ('What happens to audit-mode when preview is disabled?', 'Что происходит с audit-mode, когда preview выключен?', 'behavior'),
])
def test_supported_ru_en_frames_preserve_roles(left, right, operator):
    a, b = demand(left), demand(right)
    assert a.operator == b.operator == operator
    assert same_supported_meaning(a, b)
    for q, compiled in ((left, a), (right, b)):
        for slot in (*compiled.arguments, *compiled.constraints):
            assert q[slot.start:slot.end] == slot.text


@pytest.mark.parametrize('left,right', [
    ('What happens to audit-mode when preview is disabled?', 'What happens to audit-mode when preview is enabled?'),
    ('Can a handler for QueueHub be synchronous?', 'Can a handler for OtherHub be synchronous?'),
    ('Which takes precedence: nav title or page title?', 'Which takes precedence: nav title or file title?'),
    ('When do QueueTasks run relative to response delivery?', 'When do QueueTasks run relative to request acceptance?'),
    ('How do transport keys map to protocols?', 'How do protocols map to transport keys?'),
    ('Which ways enable strict mode?', 'Which ways disable strict mode?'),
    ('Can a handler for QueueHub be synchronous?', 'Can a handler for QueueHub be asynchronous?'),
    ('Which ways enable strict mode?', 'Which ways enable strict mode only for admins?'),
    ('Which ways enable strict mode?', 'Which ways enable strict mode and delete private files?'),
    ('Can a handler for `QueueHub` be synchronous?', 'Can a handler for `queuehub` be synchronous?'),
])
def test_changed_arguments_conditions_and_unparsed_tails_are_not_audited(left, right):
    a = demand(left)
    other = demands(right)
    assert other, 'unsupported meaning must be retained, not silently deleted'
    assert not (len(other) == 1 and same_supported_meaning(a, other[0]))


@pytest.mark.parametrize('literal', ['worker.run', 'for', 'для', '--fast-mode', 'ΣClient', 'name?literal'])
def test_quoted_literals_and_original_offsets_are_preserved(literal):
    q = f'Can a handler for `{literal}` be synchronous?'
    row = demand(q)
    owner = next(slot for slot in row.arguments if slot.role == 'owner')
    assert literal in owner.text and literal in owner.canonical
    assert q[owner.start:owner.end] == owner.text


def test_unknown_question_does_not_disappear():
    question = 'Explain the undocumented zygomatic activation of OrbitHub.'
    row = demands(question)
    assert row and row[0].unsupported_spans
    start, end = row[0].unsupported_spans[0]
    assert question[start:end].strip()


def test_question_with_an_unsupported_second_clause_is_not_fully_supported():
    question = 'Which ways enable strict mode? Also identify the private deployment secret.'
    rows = demands(question)
    assert rows and any(row.unsupported_spans for row in rows)


def test_arguments_with_and_or_are_not_made_equivalent():
    left = demands('Which ways enable `A and B`?')
    right = demands('Which ways enable `A or B`?')
    assert left and right and not same_supported_meaning(left[0], right[0])


def test_mismatched_reference_plan_cannot_verify_a_rewrite():
    refs = resolve_references('Which ways enable strict mode?', catalog=(), scope=ScopeKey('p', '', 'g1'))
    rows = compile_admission_demands('Which ways disable strict mode?', refs)
    assert rows and all(row.unsupported_spans for row in rows)


@pytest.mark.parametrize('question,operator', [
    ('Which takes precedence: nav title or page title?', 'precedence'),
    ('When do QueueTasks run relative to response delivery?', 'temporal_order'),
    ('Can a handler for QueueHub be synchronous?', 'callable_form'),
    ('Which ways enable strict mode?', 'enumeration'),
    ('How do transport keys map to protocols?', 'mapping'),
])
def test_actual_query_planner_emits_original_derived_need(question, operator):
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    plan = build_documentation_query_plan(question)
    rows = [q for q in plan.queries if q.origin == 'retrieval_need' and q.need_relation == operator]
    assert len(rows) == 1 and rows[0].text == question


def test_only_fully_verified_reformulation_can_derive_original():
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    original = 'Which takes precedence: nav title or page title?'
    good = 'Что имеет приоритет: nav title или page title?'
    changed = 'Что имеет приоритет: nav title или page title только для admins?'
    plan = build_documentation_query_plan(original, lookup_queries=(good, changed))
    lookups = [q for q in plan.queries if q.origin == 'host_lookup']
    assert lookups[0].relation == 'audited_rewrite'
    assert lookups[0].public_parent_query_id == 'query-original'
    assert lookups[1].relation == 'host_lookup'
    assert lookups[1].public_parent_query_id is None
