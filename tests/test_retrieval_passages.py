from docmancer.core.retrieval_passages import PassageProfile, build_retrieval_passages
from docmancer.core.structured_chunking import chunk_markdown_parent_child


def build(text, source='project:docs/guide.md', snapshot='generation-1', profile=PassageProfile()):
    return build_retrieval_passages(text, source, snapshot_id=snapshot, profile=profile)


def test_adjacent_topic_and_rule_share_a_bounded_passage():
    text = '# Page titles\n\nNavigation defines the page title.\n\nOtherwise the Markdown heading is used.\n'
    passages, deferred = build(text)
    assert len(passages) == 1
    assert not deferred
    assert passages[0].text == text
    assert 'Navigation defines' in passages[0].text
    assert 'Otherwise' in passages[0].text


def test_passage_does_not_cross_owner_source_or_snapshot():
    text = '# QueueTasks\n\nTasks run in order.\n\n## OtherTasks\n\nLater tasks continue.\n'
    passages, _ = build(text)
    assert len(passages) == 2
    assert all(not ('Tasks run' in p.text and 'Later tasks' in p.text) for p in passages)
    other, _ = build(text, source='other:docs/guide.md')
    changed, _ = build(text, snapshot='generation-2')
    assert {p.stable_id for p in passages}.isdisjoint(p.stable_id for p in other)
    assert {p.stable_id for p in passages}.isdisjoint(p.stable_id for p in changed)


def test_exact_unicode_spans_and_display_children_are_unchanged():
    text = '# Правила\n\nПервый абзац.\n\nВторой абзац.\n'
    before = chunk_markdown_parent_child(text, 'docs/guide.md')
    passages, _ = build(text)
    assert passages
    for p in passages:
        assert text[p.char_start:p.char_end] == p.text
        assert text.encode()[p.byte_start:p.byte_end].decode() == p.text
        assert p.line_start >= 1 and p.line_end >= p.line_start
        assert p.byte_end - p.byte_start <= 2048
    assert build(text)[0] == passages
    assert chunk_markdown_parent_child(text, 'docs/guide.md') == before


def test_repeat_offsets_and_profile_have_distinct_identity():
    text = 'Repeated paragraph.\n\nRepeated paragraph.\n'
    passages, _ = build(text, profile=PassageProfile(6, 6))
    assert len(passages) == 2
    assert len({p.stable_id for p in passages}) == 2
    changed, _ = build(text, profile=PassageProfile(7, 7))
    assert {p.stable_id for p in passages}.isdisjoint(p.stable_id for p in changed)


def test_oversized_atom_is_deferred_not_clipped_or_bridged():
    text = 'Before.\n\n- ' + 'restriction ' * 250 + '\n\nAfter.\n'
    passages, deferred = build(text)
    assert len(deferred) == 1
    assert deferred[0].reason == 'oversized_atom'
    assert text[deferred[0].char_start:deferred[0].char_end].lstrip().startswith('- ')
    assert all('restriction' not in p.text for p in passages)
    assert all(not ('Before.' in p.text and 'After.' in p.text) for p in passages)
    for atom in (
        'Restrictions:\n\n- ' + 'restriction ' * 250 + '\n',
        '| key | value |\n| --- | --- |\n| item | ' + 'restriction ' * 250 + ' |\n',
        '```python\n' + 'restriction ' * 250 + '\n```\n',
    ):
        kept, omitted = build(atom)
        assert not kept
        assert len(omitted) == 1 and omitted[0].reason == 'oversized_atom'
        assert atom[omitted[0].char_start:omitted[0].char_end] == atom
    kept, omitted = build('x' * 2048)
    assert len(kept) == 1 and not omitted
    kept, omitted = build('x' * 2049)
    assert not kept and omitted[0].reason == 'oversized_atom'


def test_atom_work_limit_is_explicit_and_profile_is_validated():
    import pytest
    with pytest.raises(ValueError):
        PassageProfile(513, 512)
    passages, deferred = build('One.\n\nTwo.\n', profile=PassageProfile(max_atoms=1))
    assert not passages
    assert deferred and deferred[0].reason == 'atom_work_limited'
