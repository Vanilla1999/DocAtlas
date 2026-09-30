from dataclasses import replace
import pytest
from experiments.language_aware_context.reference_core import (ScopeKey, ProseUnit, aggregate_profile, hint_for,
    classify_clean_prose, digest, make_request, mask_literals, restore_lookups,
    LiteralSpan, SourceSpan, adjacent_window)


def key():
    return ScopeKey('project:demo', 'snapshot-v1', 'generation-1', 'a' * 64)


def test_profile_keeps_unknown_and_minority_language():
    profile = aggregate_profile(key(), [ProseUnit('a', 'en', 980),
        ProseUnit('b', 'ru', 10), ProseUnit('c', 'und', 10)])
    hint = hint_for(profile, key())
    assert hint['shares'] == {'en': .98, 'ru': .01, 'und': .01}
    assert hint['query_languages'] == ['en', 'ru']
    assert 'confidence' not in hint
    assert hint['hint_only'] is True


@pytest.mark.parametrize('field,value', [
    ('scope_id', 'library:kotlin'), ('version', 'v2'),
    ('generation_id', 'generation-2'), ('catalog_sha256', 'b' * 64)])
def test_profile_is_bound_to_scope_and_snapshot(field, value):
    profile = aggregate_profile(key(), [ProseUnit('a', 'en', 100)])
    assert hint_for(profile, replace(key(), **{field: value})) is None


def test_duplicate_prose_is_not_counted_twice():
    unit = ProseUnit('a', 'en', 100)
    assert aggregate_profile(key(), [unit, unit]).counts == (100, 0, 0)
    with pytest.raises(ValueError, match='conflicting'):
        aggregate_profile(key(), [unit, ProseUnit('a', 'ru', 100)])


@pytest.mark.parametrize('units', [[], [ProseUnit('unknown', 'und', 100)]])
def test_no_usable_evidence_produces_no_hint(units):
    assert hint_for(aggregate_profile(key(), units), key()) is None


@pytest.mark.parametrize('text,expected', [
    ('The request is cancelled when the client is closed and no work remains.', 'en'),
    ('Если соединение закрыто, после этого нельзя продолжать работу, '
     'потому что запрос уже завершён.', 'ru'),
    ('Це український опис, який містить інструкції для користувача.', 'und'),
    ('Der Benutzer kann diesen Wert ohne eine Änderung der Konfiguration setzen.', 'und'),
    ('これは接続と要求についての説明です。', 'und'),
    ('CoroutineScope Dispatchers IO HTTPX AliasGenerator', 'und'),
    ('Not now.', 'und'),
    ('The request is completed and closed. Если запрос завершён, '
     'после этого нельзя продолжать.', 'und'),
])
def test_classifier_is_a_conservative_prose_hint(text, expected):
    assert classify_clean_prose(text) == expected


def test_original_question_is_not_normalized():
    question = '  Чем отличаются ` /-S` и `/-S`?\n'
    request = make_request(question, ['compare negative option names'], project_path='/repo')
    assert request['question'] == question
    assert request['lookup_queries'] == ['compare negative option names']
    assert set(request) == {'question', 'project_path', 'scope', 'lookup_queries'}


@pytest.mark.parametrize('lookups', ['single string', ['q'] * 2,
    ['a', 'b', 'c', 'd'], [''], ['x' * 241], ['root']])
def test_lookup_shape_failures_are_not_silently_repaired(lookups):
    with pytest.raises(ValueError):
        make_request('root', lookups, project_path='/repo')


def test_scope_is_not_inferred_from_language():
    with pytest.raises(ValueError):
        make_request('q', [], project_path='/repo', scope='kotlin')
    with pytest.raises(ValueError):
        make_request('q', [], project_path='/repo', scope='module')
    with pytest.raises(ValueError):
        make_request('q', [], project_path='/repo', scope='all', module_path='module')


def test_literal_roundtrip_preserves_leading_space():
    question = 'Чем отличаются ` /-S` и `/-S`?'
    a = question.index(' /-S')
    b = question.index('/-S', a + 4)
    masked, literals = mask_literals(question, [LiteralSpan(a, a+4), LiteralSpan(b, b+3)])
    assert literals == (' /-S', '/-S')
    assert restore_lookups([masked], literals) == (question,)
    restored = restore_lookups(['compare [[LIT_0]] and [[LIT_1]]'], literals)
    assert restored == ('compare  /-S and /-S',)


@pytest.mark.parametrize('queries', [['[[LIT_0]]'], ['[[LIT_0]] [[LIT_9]]'],
    ['[[LIT_0]] [[LIT_1]] [[LIT_broken']])
def test_missing_or_invented_literals_are_rejected(queries):
    with pytest.raises(ValueError):
        restore_lookups(queries, (' /-S', '/-S'))


def spans():
    text = 'The option is disabled.\n\nOnly when maintenance is active.'
    pos = text.index('Only')
    seed = SourceSpan(key(), 'docs/policy.md', 'policy', digest(text), 0, 0, pos-2, text[:pos-2])
    neighbor = replace(seed, ordinal=1, char_start=pos, char_end=len(text), text=text[pos:])
    return text, seed, neighbor


def test_neighbor_proposal_contains_exact_canonical_bytes_but_no_authority():
    text, seed, neighbor = spans()
    result = adjacent_window(seed, neighbor, source_text=text,
        source_policy_allows=lambda _: True)
    assert result is not None
    assert result.text == text
    assert not hasattr(result, 'qualified')
    assert not hasattr(result, 'covered_query_ids')
    assert not hasattr(result, 'answer_supported')


@pytest.mark.parametrize('field,value', [('source_id', 'docs/other.md'),
    ('parent_id', 'other-section'), ('snapshot_sha256', 'f' * 64), ('ordinal', 2),
    ('key', ScopeKey('project:other', 'v1', 'g1', 'c' * 64))])
def test_incompatible_neighbor_cannot_extend_seed(field, value):
    text, seed, neighbor = spans()
    assert adjacent_window(seed, replace(neighbor, **{field: value}),
        source_text=text, source_policy_allows=lambda _: True) is None


def test_policy_is_applied_to_each_span_and_combined_window():
    text, seed, neighbor = spans()
    seen = []
    def policy(span):
        seen.append(span.text)
        return span.text != text
    assert adjacent_window(seed, neighbor, source_text=text, source_policy_allows=policy) is None
    assert seen == [seed.text, neighbor.text, text]


def test_changed_snapshot_and_forged_bytes_fail_closed():
    text, seed, neighbor = spans()
    assert adjacent_window(seed, neighbor, source_text=text+'x',
        source_policy_allows=lambda _: True) is None
    assert adjacent_window(seed, replace(neighbor, text='forged'), source_text=text,
        source_policy_allows=lambda _: True) is None


def test_text_is_not_joined_over_a_hidden_clause():
    text = 'Rule.\nDo not execute.\nCondition.'
    seed = SourceSpan(key(), 'd.md', 'p', digest(text), 0, 0, 5, text[:5])
    start = text.index('Condition')
    neighbor = replace(seed, ordinal=1, char_start=start, char_end=len(text), text=text[start:])
    assert adjacent_window(seed, neighbor, source_text=text,
        source_policy_allows=lambda _: True) is None
