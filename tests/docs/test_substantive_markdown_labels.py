import pytest

from docmancer.docs.domain.evidence_qualification import qualify_evidence


@pytest.mark.parametrize("label", ["validation", "annotation", "configuration"])
def test_link_label_inside_a_statement_is_visible_evidence(label):
    text = f"Enable strict mode using [{label}](guide.md)."
    result = qualify_evidence(
        {"query_terms": [label], "exact_terms": []},
        query_id="q", visible_text=text, evidence_text=text,
    )
    assert result.qualified
    assert label in result.trace["body_matched_terms"]


@pytest.mark.parametrize("text", [
    "[validation](guide.md)",
    "- [validation](guide.md)",
    "![validation](image.png)",
    "https://example.test/validation",
    "[Guide](https://example.test/validation)",
    "[validation]: guide.md",
])
def test_navigation_and_destination_do_not_become_a_claim(text):
    assert not qualify_evidence(
        {"query_terms": ["validation"]}, query_id="q", visible_text=text,
    ).qualified


def test_link_label_survives_negation_in_substantive_statement():
    text = "Do not enable [validation](guide.md) for archived snapshots."
    result = qualify_evidence(
        {"query_terms": ["validation", "archived"], "exact_terms": []},
        query_id="q", visible_text=text, evidence_text=text,
    )
    assert result.qualified
    assert set(result.trace["body_matched_terms"]) == {"validation", "archived"}


def test_markdown_like_text_inside_inline_code_is_not_reparsed_as_link():
    text = "Use `[validation](guide.md)` literally in the fixture."
    result = qualify_evidence(
        {"query_terms": ["validation"]}, query_id="q", visible_text=text, evidence_text=text,
    )
    assert result.qualified
