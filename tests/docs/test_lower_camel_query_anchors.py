"""Unquoted lowerCamel API fields retain the same bounded identity lane."""
import pytest
from docmancer.docs.domain.query_terms import documentation_technical_anchors
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan


@pytest.mark.parametrize('token', ['structuredContent', 'connectionTimeout', 'userId', 'readNext', 'httpStatusCode'])
def test_lower_camel_field_is_an_exact_anchor(token):
    assert token in documentation_technical_anchors(f'Почему клиент не видит {token}?')


@pytest.mark.parametrize('text', ['ordinary prose does not create identifiers', 'обычный текст не содержит идентификаторов'])
def test_plain_prose_creates_no_lower_camel_anchor(text):
    assert documentation_technical_anchors(text) == ()


def test_filename_identity_is_not_split_into_camel_substrings():
    anchors = documentation_technical_anchors('Explain docs/structuredContent.md and readNext.')
    assert 'docs/structuredContent.md' in anchors
    assert 'structuredContent' not in anchors
    assert 'readNext' in anchors


def test_anchor_bound_and_original_question_are_preserved():
    question = 'Do not change structuredContent or userId; explain what they mean.'
    plan = build_documentation_query_plan(question).as_payload()
    assert plan['original_question'] == question
    assert any(q['origin'] == 'exact_anchor' and q['text'] == 'structuredContent' for q in plan['queries'])
    assert len(documentation_technical_anchors(' '.join(f'fieldName{i}' for i in range(50)))) <= 12
