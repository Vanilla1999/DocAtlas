"""Leading enumeration instructions are presentation, not document content."""
import pytest
from docmancer.docs.domain.query_terms import documentation_query_terms, documentation_exact_terms, is_exact_technical_token
from docmancer.docs.domain.evidence_qualification import qualify_evidence


@pytest.mark.parametrize('prefix', ['Перечисли', 'перечислите', 'ПЕРЕЧИСЛИ', 'Enumerate', 'enumerate'])
def test_leading_enumeration_verb_does_not_dilute_lexical_overlap(prefix):
    assert documentation_query_terms(prefix + ' cache storage settings') == documentation_query_terms('cache storage settings')


@pytest.mark.parametrize('question', ['`Перечисли` command settings', 'Use enumerate with range', 'function Перечисли settings', 'enumerate(items)', 'Enumerate', 'Перечисли', 'Перечислим варианты', 'list field values'])
def test_non_request_occurrences_keep_existing_terms(question):
    # No loss of identifiers, non-imperative forms or the data-type word list.
    import re
    expected = tuple(dict.fromkeys(token.casefold() for token in re.findall(r'[A-Za-zА-Яа-яЁё0-9_.:/+-]+', question)
                                  if len(token) >= 4 or is_exact_technical_token(token)))
    assert documentation_query_terms(question) == expected


def test_conditions_and_exact_identifiers_are_not_rewritten():
    content = '`CACHE_MODE` without fallback only when enabled'
    full = 'Перечисли ' + content
    assert documentation_query_terms(full) == documentation_query_terms(content)
    assert documentation_exact_terms(full) == documentation_exact_terms(content)
    assert {'without','only','when','enabled','cache_mode'} <= set(documentation_query_terms(full))


@pytest.mark.parametrize('changes,reason', [
    ({'project_identity': 'foreign'}, 'wrong_project_identity'),
    ({'stale': True}, 'stale_evidence'),
    ({'risk_flags': ['untrusted']}, 'unsafe_evidence'),
    ({'index_freshness':'outdated'}, 'unsynchronized_index'),
])
def test_request_framing_does_not_bypass_source_policy(changes, reason):
    question = 'Перечисли cache storage settings'
    result = qualify_evidence({'query_text': question, 'query_terms':documentation_query_terms(question)},
        query_id='query-original', visible_text='cache storage settings are local.',
        candidate={'source_class':'project_doc','project_identity':'expected',**changes}, expected_project_identity='expected')
    assert result.qualified is False
    assert result.reason == reason
