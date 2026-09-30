"""Tests the actual extraction/aggregation code, not semantic retrieval quality."""
from dataclasses import replace
import pytest
from experiments.language_aware_context.reference_core import ScopeKey, hint_for
from experiments.language_aware_context.source_profile import (
    catalog_digest, extract_prose, profile_sources, profile_hint,
)

EN = 'The client should wait when the request is active and stop only after the response.'
RU = 'Это описание для клиента, который должен ждать, когда запрос ещё выполняется.'


def scope(docs):
    return ScopeKey('project:alpha', 'v1', 'g1', catalog_digest(docs))


def profile(text):
    docs = {'docs/topic.md': text}
    return profile_sources(docs, scope(docs))


def test_english_and_russian_paragraphs_are_counted_separately():
    value = profile(EN + '\n\n' + RU)
    hint = hint_for(value.profile, value.profile.key)
    assert set(hint['query_languages']) == {'en', 'ru'}
    assert value.profile.counts[0] > 0 and value.profile.counts[1] > 0


@pytest.mark.parametrize('fence', ['```', '~~~~'])
def test_large_code_block_does_not_turn_russian_prose_english(fence):
    raw = RU + '\n\n' + fence + 'kotlin\n' + (EN + '\n') * 50 + fence + '\n'
    assert profile(raw).profile.counts == profile(RU).profile.counts


def test_mismatched_inner_fence_does_not_end_a_code_block():
    raw = RU + '\n\n~~~~\n```\n' + EN + '\n```\n~~~~\n'
    assert profile(raw).profile.counts == profile(RU).profile.counts


def test_unclosed_fence_excludes_the_remaining_code():
    assert profile(RU + '\n\n```python\n' + EN).profile.counts == profile(RU).profile.counts


def test_inline_identifiers_and_destinations_do_not_count_as_prose():
    raw = RU + '\n\n`' + EN + '` [ссылка](https://example.test/the/and/with) '
    clean = '\n'.join(s.text for s in extract_prose(raw))
    assert EN not in clean and 'https' not in clean and 'example.test' not in clean
    assert 'ссылка' in clean


def test_multiline_inline_code_is_not_prose():
    raw = RU + '\n\n``' + EN + '\n' + EN + '``\n'
    assert profile(raw).profile.counts == profile(RU).profile.counts


def test_frontmatter_comments_and_html_code_do_not_count():
    raw = ('---\ntitle: ' + EN + '\n---\n' + RU + '\n\n<!-- ' + EN + ' -->\n'
           + '<pre>' + EN + '</pre>\n<script>' + EN + '</script>')
    assert profile(raw).profile.counts == profile(RU).profile.counts


def test_unclosed_frontmatter_is_not_confident_english():
    assert hint_for(profile('---\ntitle: ' + EN).profile,
                    profile('---\ntitle: ' + EN).profile.key) is None


def test_indented_code_and_reference_definitions_do_not_count():
    raw = RU + '\n\n    ' + EN + '\n\n[ref]: https://example.test "' + EN + '"\n'
    assert profile(raw).profile.counts == profile(RU).profile.counts


def test_only_code_returns_no_language_hint():
    value = profile('```python\n' + EN + '\n```')
    assert value.profile.counts == (0, 0, 0)
    assert hint_for(value.profile, value.profile.key) is None


@pytest.mark.parametrize('text', [
    'Це опис для клієнта, який повинен чекати, коли запит ще виконується.',
    'Dies ist eine Beschreibung und keine englische Dokumentation.',
    'To jest opis polskiego dokumentu dotyczącego konfiguracji klienta.',
    'CoroutineScope Dispatchers.IO HTTPX TestClient',
])
def test_unsupported_or_identifier_only_text_does_not_claim_en_or_ru(text):
    value = profile(text)
    assert value.profile.counts[:2] == (0, 0)


def test_unknown_prose_stays_in_the_denominator():
    value = profile(EN + '\n\nDies ist keine englische Dokumentation.')
    hint = hint_for(value.profile, value.profile.key)
    assert hint['shares']['und'] > 0
    assert sum(hint['shares'].values()) == pytest.approx(1)


def test_source_ranges_are_exact_nonoverlapping_with_crlf():
    raw = '# Title\r\n\r\n' + EN + '\r\n\r\n' + RU + '\r\n'
    spans = extract_prose(raw)
    assert spans
    for i, span in enumerate(spans):
        assert raw[span.start:span.end] == span.raw
        if i:
            assert spans[i-1].end <= span.start


def test_profile_is_deterministic_independent_of_source_order():
    a = {'a.md': EN, 'b.md': RU}
    b = dict(reversed(list(a.items())))
    assert profile_sources(a, scope(a)) == profile_sources(b, scope(b))


def test_catalog_binding_rejects_source_mutation():
    docs = {'a.md': EN}
    key = scope(docs)
    with pytest.raises(ValueError, match='catalog'):
        profile_sources({'a.md': EN + ' changed'}, key)


def test_profile_cannot_be_reused_in_another_scope():
    built = profile(EN)
    assert hint_for(built.profile, replace(built.profile.key, scope_id='library:kotlin')) is None


def test_new_snapshot_cannot_reuse_the_hint():
    built = profile(EN)
    assert hint_for(built.profile, replace(built.profile.key, generation_id='g2')) is None


def test_profile_has_no_authority_or_answer_fields():
    built = profile(EN)
    hint = hint_for(built.profile, built.profile.key)
    assert not {'answer_supported', 'edit_ready', 'covered_query_ids', 'confidence'} & set(hint)


def test_minority_language_is_not_filtered_out():
    docs = {'english.md': (EN + '\n\n') * 150, 'russian.md': RU}
    value = profile_sources(docs, scope(docs))
    hint = hint_for(value.profile, value.profile.key)
    assert 0 < hint['shares']['ru'] < .02
    assert 'ru' in hint['query_languages']


@pytest.mark.parametrize('path', ['../secret.md', '/root/a.md', 'a/../b.md', 'a\\b.md', 'labels.json'])
def test_invalid_source_keys_are_rejected(path):
    with pytest.raises(ValueError):
        catalog_digest({path: EN})


def test_source_size_is_bounded():
    with pytest.raises(ValueError, match='large'):
        extract_prose('a' * 2_000_001)


def test_new_extractor_invalidates_an_old_hint():
    value = profile(EN)
    assert profile_hint(replace(value, extractor_revision='older'), value.profile.key) is None
    assert profile_hint(value, value.profile.key)['extraction_method'] == value.extractor_revision


def test_nested_list_fence_is_not_counted_as_english():
    raw = RU + '\n\n- ```python\n' + EN + '\n  ```\n'
    assert profile(raw).profile.counts == profile(RU).profile.counts
