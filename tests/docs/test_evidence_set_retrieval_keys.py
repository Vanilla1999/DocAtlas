"""Reuse existing source-owned keys; context text never becomes quoted evidence."""
from docmancer.core.structured_chunking import parse_markdown_parents
from docmancer.retrieval.contextual_indexing import build_context_prefix, embedding_input
from docmancer.docs.domain.evidence_qualification import qualify_evidence


def key(raw):
    parent = parse_markdown_parents(raw, 'source-1')[0]
    body = raw[raw.index('\n\n') + 2:]
    return build_context_prefix({}, heading_path=parent.heading_path, display_text=body), body


def test_checked_source_heading_is_search_context_not_an_invented_quote():
    raw = '# Transport coordinates\n\nA value consists of a scheme and a port.\n'
    prefix, body = key(raw)
    assert 'Transport coordinates' in prefix.text
    assert embedding_input(prefix, body).endswith(body)
    assert body == raw[raw.index('\n\n') + 2:]
    assert body not in prefix.text


def test_heading_change_invalidates_key_without_changing_body():
    first, a = key('# Transport coordinates\n\nThe same literal value.\n')
    second, b = key('# Different topic\n\nThe same literal value.\n')
    assert a == b and first.content_hash != second.content_hash


def test_context_key_cannot_discharge_an_absent_code_symbol():
    prefix, body = key('# RequestedClass\n\nOtherClass defaults to seven attempts.\n')
    result = qualify_evidence({'query_text': 'Explain `RequestedClass` defaults.',
        'query_terms': ['defaults'], 'exact_terms': ['RequestedClass']},
        query_id='query-original', visible_text=body, evidence_text=body,
        candidate={'context_prefix': prefix.text})
    assert not result.qualified


def test_significant_quoted_space_survives_retrieval_body():
    raw = '# Boolean options\n\nUse ` /--disabled` for a negative-only name.\n'
    prefix, body = key(raw)
    assert ' /--disabled' in embedding_input(prefix, body)
    assert body in raw
