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

