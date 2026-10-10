"""Native delivery acceptance; no case labels enter product selection."""
import pytest

from tests.docs._evidence_set_fixtures import capture_case, old_assessment
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


def assert_bounds(payload):
    assert all(payload[k] is False for k in (
        'answer_supported', 'answer_available', 'edit_ready'))


@pytest.mark.parametrize('case_id', ['mkdocs-05', 'pydantic-03'])
def test_native_required_delivery(tmp_path, case_id):
    cap = capture_case(tmp_path, case_id)
    assert_bounds(cap['public_payload'])
    assert old_assessment(case_id, cap)['context_sufficiency'] == 'sufficient'


@pytest.mark.parametrize('case_id', ['pydantic-07', 'ruff-07'])
def test_partial_known_facts_retained(tmp_path, case_id):
    cap = capture_case(tmp_path, case_id)
    assert_bounds(cap['public_payload'])
    assert old_assessment(case_id, cap)['claims']['required']['status'] == 'supported'
    assert cap['public_payload']['query_coverage'] != 'full'


def test_precedence_rule_survives_nonempty_distractor(tmp_path):
    question = ('Which page title wins when the navigation configuration '
                'and Markdown content define different titles?')
    fact = 'The title in your nav setting overrides the Markdown heading.'
    cap = capture_reference_case(tmp_path, {
        'A.md': '# Navigation\n\nNavigation and Markdown support page layout examples.\n',
        'B.md': '# Page titles\n\n' + fact + '\n',
    }, question)
    assert_bounds(cap['public_payload'])
    assert fact in visible(cap)


@pytest.mark.parametrize('shape,expected', [
    ('full', True), ('one', False), ('missing', False), ('nested_example', False),
])
def test_list_context_requires_all_top_level_items_without_awarding_proof(shape, expected):
    from docmancer.docs.application.need_context_projection import set_context_variants
    from docmancer.docs.application.need_context_disposition import classify_need_context
    from docmancer.docs.application.source_dependency_preparation import compact_dependency_record
    from tests.docs.test_evidence_set_disposition import context_case

    question = ('List four ways to enable strict mode, including field, annotation, '
                'config and validation call.')
    items = ['* Pass strict=True to the validation call.',
             '* Set strict=True on a field.', '* Use a strict type annotation.',
             '* Use strict mode config.']
    if shape == 'one':
        items = items[:1]
    elif shape == 'missing':
        items = items[:3]
    elif shape == 'nested_example':
        items = items[:3] + ['  * Example: strict mode config.']
    body = '# Strict mode\n\nStrict mode can be enabled in these ways:\n\n' + '\n'.join(items) + '\n'
    contract, args = context_case(question, body)
    candidate = {**args['candidate'], 'path': 'Guide.md', 'content': body,
                 'line_start': 1, 'line_end': len(body.splitlines()),
                 '_evidence_sets': [compact_dependency_record(b) for b in args['bundles']]}
    options = list(set_context_variants([candidate],
        query_plan={'original_question': question, 'public_query_ids': ['query-original']},
        expected_project_identity='project', max_tokens=800, diagnostics={}))
    assert bool(options) is expected
    assert classify_need_context(contract, **args).state != 'supported'


def test_list_context_rechecks_cropped_bytes_and_has_no_late_io(monkeypatch):
    from docmancer.docs.application.need_context_projection import set_context_variants
    from docmancer.docs.application.source_dependency_preparation import compact_dependency_record
    from tests.docs.test_evidence_set_disposition import context_case
    from pathlib import Path
    import socket
    import sqlite3

    question = 'List four ways to enable strict mode, including field, annotation, config and validation call.'
    body = ('# Strict mode\n\nStrict mode can be enabled in these ways:\n\n'
            '* Pass strict=True to the validation call.\n* Set strict=True on a field.\n'
            '* Use a strict type annotation.\n* Use strict mode config.\n')
    _, args = context_case(question, body)
    candidate = {**args['candidate'], 'path': 'Guide.md', 'content': body,
                 'line_start': 1, 'line_end': len(body.splitlines()),
                 '_evidence_sets': [compact_dependency_record(b) for b in args['bundles']]}
    kwargs = dict(query_plan={'original_question': question, 'public_query_ids': ['query-original']},
                  expected_project_identity='project', max_tokens=800, diagnostics={})
    def forbidden(*args, **kwargs):
        raise AssertionError('late I/O')
    for target in ('builtins.open',):
        monkeypatch.setattr(target, forbidden)
    for name in ('open', 'read_text', 'read_bytes'):
        monkeypatch.setattr(Path, name, forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    assert list(set_context_variants([candidate], **kwargs))
    cropped = dict(candidate['_reference_evidence'])
    cropped['text'] = body[:body.index('* Use strict mode config.')]
    cropped['char_end'] = len(cropped['text'])
    candidate.update(_reference_evidence=cropped, snippet=cropped['text'], content=cropped['text'])
    assert not list(set_context_variants([candidate], **kwargs))
