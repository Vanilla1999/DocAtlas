"""Research read-repair checks; no replacement for authenticated I.3 or final C."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from docmancer.core.structured_chunking import parse_markdown_parents
from docmancer.docs.domain.admission_grammar import parse_admission_frame
from v2plan.next07_grounded_candidate import (
    _hidden_structural_dependency,
    _source_state_witness,
)


@pytest.mark.parametrize('subject', ['OrbitClient', 'RelayClient', 'ΣClient'])
@pytest.mark.parametrize('requested,observed,canonical', [
    ('disabled', 'enabled', 'enabled'),
    ('enabled', 'disabled', 'disabled'),
    ('enabled', 'not enabled', 'disabled'),
])
def test_default_dispatch_preserves_request(subject, requested, observed, canonical):
    question = f'What is {subject} default timeout when preview is {requested}?'
    frame = parse_admission_frame(question)
    assert frame is not None
    original = frame
    body = f'When preview is {observed}, {subject} default timeout is 7 seconds.'
    calls = []

    def default(query, text):
        calls.append((query, text))
        return True, ((0, len(text)),)

    def relation(*_):
        pytest.fail('default must not use the unsupported relation matcher')

    verdict, spans = _source_state_witness(
        frame, question, observed, canonical, body,
        default_witness=default, relation_witness=relation,
    )
    assert verdict is True and spans == ((0, len(body)),)
    query, passed_body = calls[0]
    assert query['text'] == f'What is {subject} default timeout when preview is {observed}?'
    assert query['need_subject'] == subject
    assert passed_body == body
    assert frame == original
    assert question.endswith(f'{requested}?')


@pytest.mark.parametrize('result', [None, False])
def test_unknown_default_witness_does_not_become_mismatch(result):
    question = 'What is RelayClient default timeout when preview is disabled?'
    frame = parse_admission_frame(question)
    verdict, spans = _source_state_witness(
        frame, question, 'enabled', 'enabled', 'unrecognized source clause',
        default_witness=lambda *_: (result, ()),
        relation_witness=lambda *_: pytest.fail('wrong matcher'),
    )
    assert verdict is result and spans == ()


def test_default_dispatch_rejects_invalid_state_offsets():
    question = 'What is RelayClient default timeout when preview is disabled?'
    frame = parse_admission_frame(question)
    state = next(s for s in frame.constraints if s.role == 'condition_state')
    broken = replace(frame, constraints=tuple(
        replace(s, start=s.start - 1) if s is state else s for s in frame.constraints
    ))
    assert _source_state_witness(
        broken, question, 'enabled', 'enabled', 'text',
        default_witness=lambda *_: pytest.fail('invalid binding must not invoke matcher'),
        relation_witness=lambda *_: pytest.fail('wrong matcher'),
    ) == (None, ())


def test_other_relation_dispatch_keeps_existing_matcher():
    question = 'What happens to RelayClient when preview is disabled?'
    frame = parse_admission_frame(question)
    original = frame
    seen = []

    def relation(actual, body):
        seen.append((actual, body))
        return True, ((0, len(body)),)

    verdict, _ = _source_state_witness(
        frame, question, 'enabled', 'enabled', 'body',
        default_witness=lambda *_: pytest.fail('behavior must retain its matcher'),
        relation_witness=relation,
    )
    assert verdict is True and frame == original
    assert next(s.canonical for s in seen[0][0].constraints if s.role == 'condition_state') == 'enabled'


@pytest.mark.parametrize('value,error', [(17, 'LeaseExpired'), (29, 'WaitExpired')])
def test_whole_short_fact_owners_remain_visible(value, error):
    for raw in (
        f'# LeaseClient\n\nThe default timeout is {value} seconds.\n',
        f'# LeaseClient\n\nAn expired operation raises `{error}`.\n',
    ):
        parents = parse_markdown_parents(raw, 'source')
        assert parents
        assert not _hidden_structural_dependency(parents, (), 0, len(raw))


@pytest.mark.parametrize('filler', ['Documentation. ' * 330, 'Объяснение. ' * 330, '😀 ' * 2500])
def test_tail_of_same_owner_cannot_disappear(filler):
    prefix = '# LeaseClient\n\nLeaseClient raises `LeaseExpired`.\n\n'
    raw = prefix + filler + '\n\nOnly when an operation expires.\n'
    parents = parse_markdown_parents(raw, 'source')
    assert _hidden_structural_dependency(parents, (), 0, len(prefix))
    assert not _hidden_structural_dependency(parents, (), 0, len(raw))


def test_visible_section_does_not_require_unrelated_sibling_section():
    first = '# First\n\nA complete documented statement.\n\n'
    raw = first + '# Second\n\nAnother documented statement.\n'
    parents = parse_markdown_parents(raw, 'source')
    assert not _hidden_structural_dependency(parents, (), 0, len(first))
    assert not _hidden_structural_dependency(parents, (), len(first), len(raw))
    assert _hidden_structural_dependency(parents, (), 0, len(first) + 4)


def test_fake_heading_in_fence_does_not_close_owner():
    prefix = '# Owner\n\nA documented statement.\n\n```text\n'
    raw = prefix + '# Not an owner\n```\n\nOnly in a documented state.\n'
    parents = parse_markdown_parents(raw, 'source')
    assert len(parents) == 1
    assert _hidden_structural_dependency(parents, (), 0, len(prefix))


def test_headingless_owner_requires_whole_text():
    prefix = 'A documented statement.\n\n'
    raw = prefix + 'Only in a documented state.\n'
    parents = parse_markdown_parents(raw, 'source')
    assert _hidden_structural_dependency(parents, (), 0, len(prefix))
    assert not _hidden_structural_dependency(parents, (), 0, len(raw))


def test_declared_dependency_is_not_lost_when_owners_are_complete():
    owner = SimpleNamespace(char_start=10, char_end=30)
    edge = SimpleNamespace(child=SimpleNamespace(start=15, end=25),
                           parent=SimpleNamespace(start=0, end=8))
    assert _hidden_structural_dependency([owner], [edge], 10, 30)
    assert not _hidden_structural_dependency([owner], [edge], 0, 30)


@pytest.mark.parametrize('requested,observed,canonical', [
    ('disabled', 'enabled', 'enabled'),
    ('enabled', 'disabled', 'disabled'),
    ('enabled', 'not enabled', 'disabled'),
])
def test_native_default_witness_establishes_opposite_state(requested, observed, canonical):
    # Execute with the project's real matcher; never substitute this with the
    # dispatch spies above when reporting integration or I.3 acceptance.
    from docmancer.docs.domain.admission_local_binding import default_local_witness
    from docmancer.docs.domain.admission_relations import relation_local_witness

    question = f'What is RelayClient default timeout when preview is {requested}?'
    frame = parse_admission_frame(question)
    body = f'When preview is {observed}, RelayClient default timeout is 7 seconds.'
    witnessed, spans = _source_state_witness(
        frame, question, observed, canonical, body,
        default_witness=default_local_witness, relation_witness=relation_local_witness,
    )
    assert witnessed is True and spans
    assert all(0 <= start < end <= len(body) for start, end in spans)


@pytest.mark.parametrize('body', [
    'When preview is enabled, OtherClient default timeout is 7 seconds.',
    'When preview is enabled, RelayClient default retries is 7.',
    'When preview is enabled, RelayClient default timeout is unknown.',
    'When preview is enabled, RelayClient default timeout is not 7 seconds.',
])
def test_native_default_witness_cannot_borrow_subject_property_or_value(body):
    from docmancer.docs.domain.admission_local_binding import default_local_witness
    from docmancer.docs.domain.admission_relations import relation_local_witness

    question = 'What is RelayClient default timeout when preview is disabled?'
    frame = parse_admission_frame(question)
    witnessed, _ = _source_state_witness(
        frame, question, 'enabled', 'enabled', body,
        default_witness=default_local_witness, relation_witness=relation_local_witness,
    )
    assert witnessed is not True
