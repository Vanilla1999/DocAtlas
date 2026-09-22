"""Independent question parts retain real evidence without full-answer claims."""
import pytest
from tests.docs._evidence_set_fixtures import capture_case, old_assessment
from eval.evidence_quality_v2.run import load_protocol


@pytest.mark.parametrize('known,compound', [
    ('pydantic-01', 'pydantic-07'), ('ruff-01', 'ruff-07')])
def test_independent_unknown_tail_preserves_known_evidence(tmp_path, known, compound):
    _, cases, _ = load_protocol()
    question = next(c['question'] for c in cases if c['id'] == compound)
    before = capture_case(tmp_path / 'before', known)
    after = capture_case(tmp_path / 'after', known, question=question)
    assert old_assessment(known, before)['context_sufficiency'] == 'sufficient'
    assert old_assessment(known, after)['context_sufficiency'] == 'sufficient'
    assert after['public_payload']['query_coverage'] != 'full'
    assert all(after['public_payload'][k] is False for k in
               ('answer_supported', 'answer_available', 'edit_ready'))


def compile_question(question):
    from docmancer.docs.domain.need_contracts import compile_need_contracts
    from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references
    refs = resolve_references(question, catalog=(), scope=ScopeKey('p', '', 'g'))
    return compile_need_contracts(question, refs)


def test_every_independent_sentence_is_retained_including_unknown():
    q = 'What is OrbitClient default timeout? Also identify the private deployment choice.'
    rows = compile_question(q)
    assert len(rows) == 2
    assert rows[0].need.query_span_text == 'What is OrbitClient default timeout?'
    assert rows[1].interpretation == 'unresolved'
    assert 'private deployment choice' in rows[1].need.query_span_text
    for row in rows:
        n = row.need
        assert q[n.query_span_start:n.query_span_end] == n.query_span_text


@pytest.mark.parametrize('suffix', [
    'Only in version 2.1.', 'When preview is disabled.', 'Except during startup.',
    'Только при выключенном preview.', 'Using the production deployment.',
])
def test_dependent_suffix_is_not_an_independent_context_permission(suffix):
    from docmancer.docs.domain.need_composition import independent_sentence_spans
    q = 'What is OrbitClient default timeout? ' + suffix
    assert len(independent_sentence_spans(q)) <= 1


@pytest.mark.parametrize('literal', ['A? B', 'A and B', 'файл v2.1', ' /--disabled'])
def test_quoted_identity_punctuation_and_whitespace_are_preserved(literal):
    q = f'What does the function `{literal}` return? Also identify a deployment choice.'
    rows = compile_question(q)
    assert len(rows) == 2
    assert f'`{literal}`' in rows[0].need.query_span_text
    assert literal.casefold() in rows[0].need.hard_exact


def test_markdown_link_does_not_create_false_sentences():
    from docmancer.docs.domain.need_composition import independent_sentence_spans
    q = 'What does [worker? docs](https://example.invalid/v1.2?q=a) do? Also identify deployment settings.'
    spans = independent_sentence_spans(q)
    assert len(spans) == 2
    assert q[spans[0][0]:spans[0][1]].endswith('do?')


def test_mismatched_reference_plan_never_compiles_supported_need():
    from docmancer.docs.domain.need_contracts import compile_need_contracts
    from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references
    refs = resolve_references('A different question', catalog=(), scope=ScopeKey('p', '', 'g'))
    rows = compile_need_contracts('What is OrbitClient default timeout?', refs)
    assert rows and all(row.interpretation == 'unresolved' for row in rows)


def test_independent_probe_cannot_derive_whole_root_coverage():
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    p = build_documentation_query_plan('What is OrbitClient default timeout? Also identify a deployment choice.')
    parts = [q for q in p.queries if q.query_id.startswith('query-part-')]
    assert parts and all(q.public_parent_query_id is None and not q.coverage_required for q in parts)
    assert p.unresolved_parts


@pytest.mark.parametrize('body', [
    'When preview is enabled, OrbitClient default timeout is 7 seconds.',
    'OrbitClient default timeout is 7 seconds.',
])
def test_independent_default_preserves_its_local_condition_veto(body):
    from dataclasses import asdict
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    from docmancer.docs.domain.evidence_qualification import qualify_evidence
    from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
    q = 'What is OrbitClient default timeout when preview is disabled? Also identify a deployment choice.'
    part = next(x for x in build_documentation_query_plan(q).queries if x.query_id == 'query-part-1')
    probe = {**asdict(part), 'query_text': part.text, 'query_origin': part.origin,
             'query_terms': documentation_query_terms(part.text),
             'exact_terms': query_constraint_roles(part.text).hard_exact}
    result = qualify_evidence(probe, query_id=part.query_id, visible_text=body, evidence_text=body)
    assert not result.qualified


def test_independent_default_preserves_exact_identity_and_valid_condition():
    from dataclasses import asdict
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    from docmancer.docs.domain.evidence_qualification import qualify_evidence
    from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
    q = 'What is OrbitClient default timeout when preview is disabled? Also identify a deployment choice.'
    part = next(x for x in build_documentation_query_plan(q).queries if x.query_id == 'query-part-1')
    probe = {**asdict(part), 'query_text': part.text, 'query_origin': part.origin,
             'query_terms': documentation_query_terms(part.text),
             'exact_terms': query_constraint_roles(part.text).hard_exact}
    body = 'When preview is disabled, OrbitClient default timeout is 7 seconds.'
    assert qualify_evidence(probe, query_id=part.query_id, visible_text=body).qualified
    assert not qualify_evidence(probe, query_id=part.query_id,
                                 visible_text=body.replace('OrbitClient', 'OtherClient')).qualified


def test_need_contract_compilation_and_query_planning_perform_no_io(monkeypatch):
    from pathlib import Path
    import socket
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    from docmancer.docs.domain.need_composition import independent_sentence_spans
    def forbidden(*args, **kwargs):
        raise AssertionError('query composition performed I/O')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    # Deliberately unseen input to avoid a warm parser cache hiding a read.
    q = 'What is FreshClient default timeout? Also identify an undocumented choice.'
    assert len(independent_sentence_spans(q)) == 2
    assert compile_question(q)
    assert any(x.query_id == 'query-part-1' for x in build_documentation_query_plan(q).queries)
