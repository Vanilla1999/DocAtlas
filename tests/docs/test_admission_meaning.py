"""Live guards for unsupported source spans and reference-plan integrity."""
from docmancer.docs.domain.admission_meaning import compile_admission_demands, same_supported_meaning
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references


def demands(question):
    refs = resolve_references(question, catalog=(), scope=ScopeKey('p', '', 'g1'))
    return compile_admission_demands(question, refs)


def demand(question):
    result = demands(question)
    assert len(result) == 1 and not result[0].unsupported_spans
    return result[0]


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
