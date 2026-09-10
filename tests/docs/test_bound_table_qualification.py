"""Table schemas qualify only together with their own substantive subject row."""
import pytest

from docmancer.docs.application.docs_context_projection import _requalify_visible_source
from docmancer.docs.domain.evidence_qualification import qualify_evidence


PROBE = {
    "query_terms": ["fetch_records", "service", "default"],
    "exact_terms": ["fetch_records"],
    "parent_exact_terms": ["fetch_records"],
}
TABLE = (
    "| Tool | Default use |\n| --- | --- |\n"
    "| `fetch_records` | Read current records from the local archive. |"
)


def test_table_header_relation_is_bound_to_the_exact_subject_row():
    result = qualify_evidence(PROBE, query_id="query", visible_text=TABLE)
    assert result.qualified
    assert result.trace["body_matched_terms"] == ["fetch_records"]
    assert "default" in result.trace["matched_terms"]
    assert not result.trace["missing_exact_terms"]


@pytest.mark.parametrize("text", [
    "| Tool | Default use |\n| --- | --- |",  # no factual row
    TABLE.replace("`fetch_records`", "`write_records`"),  # wrong subject
    "| Tool | Default use |\n| --- | --- |\n| fetch_records | |",  # no value
    "| Tool | Default use |\n| --- | --- |\n| fetch_records | [Guide](guide.md) |",
    "fetch_records exists.\n\n" + TABLE.replace("`fetch_records`", "`write_records`"),
    "| Tool | Default use |\n| --- | --- |\n\nfetch_records reads records.",
    "| Tool | Default use |\n| --- | --- |\n| write_records | Changes records. |\n"
    "\n| Tool | Behavior |\n| --- | --- |\n| fetch_records | Reads records. |",
])
def test_header_cannot_supply_a_relation_without_its_own_subject_and_value(text):
    result = qualify_evidence(PROBE, query_id="query", visible_text=text)
    assert not result.qualified


def test_table_header_never_supplies_a_missing_exact_identifier():
    text = "| fetch_records | Default use |\n| --- | --- |\n| Other | Reads records. |"
    result = qualify_evidence(PROBE, query_id="query", visible_text=text)
    assert not result.qualified
    assert "fetch_records" in result.trace["missing_exact_terms"]


@pytest.mark.parametrize("visible,expected", [
    (TABLE, True),
    ("| `fetch_records` | Read current records from the local archive. |", False),
])
def test_final_visible_qualification_cannot_borrow_a_hidden_table_header(visible, expected):
    source = _requalify_visible_source({
        "path_or_url": "docs/archive.md",
        "snippet": visible,
        "retrieval_query_matches": {"query": {**PROBE, "qualified": True}},
        "_qualification_candidate": {"content": TABLE},
    }, query_text={"query": "fetch_records service default"})
    assert source["retrieval_query_matches"]["query"]["qualified"] is expected
