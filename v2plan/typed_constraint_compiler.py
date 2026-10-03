"""Research-only constraints from fully parsed frames; never imported by runtime."""
from dataclasses import replace
from docmancer.docs.domain.admission_grammar import parse_admission_frame
from docmancer.docs.domain.need_composition import compositional_parts
from docmancer.docs.domain.need_contracts import QuerySpan
from docmancer.docs.domain.need_contracts import compile_need_contracts as native_compile


def compile_typed_constraints(question, references):
    contracts = native_compile(question, references)
    if references.question != question:
        return contracts
    rows = []
    for contract in contracts:
        need = contract.need
        text = need.query_span_text
        # Composed boundaries and prerequisites remain owned by the existing compiler.
        if ':part-' in need.need_id or contract.prerequisite_need_ids or compositional_parts(text):
            rows.append(contract)
            continue
        frame = parse_admission_frame(text)
        if frame is None:
            rows.append(contract)
            continue
        start, end = need.query_span_start, need.query_span_end
        if question[start:end] != text:
            raise ValueError('query_span_mismatch')
        constraints = tuple(QuerySpan(start + slot.start, start + slot.end) for slot in frame.constraints)
        if any(not start <= span.start < span.end <= end for span in constraints):
            raise ValueError('typed_constraint_span_mismatch')
        rows.append(replace(contract, constraint_spans=constraints))
    return tuple(rows)
