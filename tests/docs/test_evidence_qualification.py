import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _tag_retrieval_query
from docmancer.docs.application.docs_context_projection import project_docs_context, _requalify_visible_source
from docmancer.docs.domain.evidence_qualification import qualify_evidence


@pytest.mark.parametrize("facts,reason", [
    ({"project_identity": "other"}, "wrong_project_identity"),
    ({"project_identity": ""}, "missing_project_identity"),
    ({"freshness": "stale"}, "stale_evidence"),
    ({"index_freshness": "stale"}, "unsynchronized_index"),
    ({"risk_flags": ["unsafe"]}, "unsafe_evidence"),
    ({"lifecycle_status": "historical"}, "lifecycle_not_allowed"),
])
def test_domain_rejects_ineligible_candidate(facts, reason):
    result = qualify_evidence(
        {"query_terms": ["storage"], "qualified": True}, query_id="q",
        visible_text="Storage persists records.",
        candidate={"project_identity": "repo", **facts},
        expected_project_identity="repo",
    )
    assert not result.qualified
    assert result.reason == reason


@pytest.mark.parametrize("text", [
    "# Storage\n\n- [Storage](storage.md)",
    "Storage\n=======\n\n[Storage](storage.md)",
    "# Storage",
])
def test_navigation_is_not_evidence(text):
    assert not qualify_evidence(
        {"query_terms": ["storage"], "qualified": True},
        query_id="q", visible_text=text,
    ).qualified


@pytest.mark.parametrize("status,intent", [
    ("current", "current"), ("completed", "historical"),
    ("superseded", "historical"), ("historical", "either"),
])
def test_domain_uses_existing_lifecycle_policy(status, intent):
    assert qualify_evidence(
        {"mode": "exact_path", "query_text": "docs/storage.md"},
        query_id="q", visible_text="docs/storage.md\nStorage persists records.",
        evidence_text="Storage persists records.",
        candidate={"project_identity": "repo", "lifecycle_status": status},
        expected_project_identity="repo", lifecycle_intent=intent,
    ).qualified


def test_supplemental_without_lookup_requalifies_visible_content():
    chunk = RetrievedChunk(source="docs/storage.md", chunk_index=0,
        text="Unrelated prose.", score=1,
        metadata={"lexical_match": {"qualified": True}})
    tagged = _tag_retrieval_query([chunk], "query-supplemental-1", "storage")
    assert not tagged[0].metadata["retrieval_query_matches"]["query-supplemental-1"]["qualified"]


@pytest.mark.parametrize("status,question,expected", [
    ("current", "storage", "ok"),
    ("historical", "historical storage", "ok"),
    ("completed", "historical storage", "ok"),
    ("historical", "storage", "insufficient_evidence"),
])
def test_projection_preserves_lifecycle_facts(status, question, expected):
    projection, _ = project_docs_context(retrieval={
        "project_identity": "repo",
        "documentation_query_plan": {
            "original_question": question,
            "queries": [{"query_id": "query-original", "text": question, "origin": "original"}],
        },
        "context_pack": [{
            "source_class": "project_doc", "path": "docs/storage.md",
            "content": "Historical storage persists records.",
            "project_identity": "repo", "lifecycle_status": status,
            "retrieval_query_matches": {"query-original": {
                "qualified": True, "query_terms": ["storage"],
            }},
        }],
    })
    assert projection["status"] == expected


@pytest.mark.parametrize("facts", [
    {"project_identity": "foreign"}, {"freshness": "stale"},
    {"index_freshness": "stale"}, {"risk_flags": ["unsafe"]},
    {"lifecycle_status": "historical"},
])
def test_snippet_requalification_retains_original_candidate_facts(facts):
    source = _requalify_visible_source({
        "path_or_url": "docs/storage.md", "snippet": "Storage persists records.",
        "_qualification_candidate": {"project_identity": "repo", **facts},
        "_expected_project_identity": "repo",
        "retrieval_query_matches": {"q": {"qualified": True, "query_terms": ["storage"]}},
    }, query_text={"q": "storage"})
    assert source["retrieval_query_ids"] == []


def test_snippet_requalification_does_not_trust_full_text_match():
    source = _requalify_visible_source({
        "path_or_url": "docs/storage.md", "snippet": "Unrelated prose.",
        "_qualification_candidate": {"content": "Storage persists records."},
        "retrieval_query_matches": {"q": {"qualified": True, "query_terms": ["storage"]}},
    }, query_text={"q": "storage"})
    assert source["retrieval_query_ids"] == []


def test_supplemental_candidate_checks_request_identity():
    chunk = RetrievedChunk(source="docs/storage.md", chunk_index=0,
        text="Storage persists records.", score=1,
        metadata={"project_identity": "foreign"})
    tagged = _tag_retrieval_query(
        [chunk], "query-supplemental-1", "storage", expected_project_identity="repo",
    )
    assert tagged[0].metadata["retrieval_query_ids"] == ()


@pytest.mark.parametrize("metadata", [
    "# project architecture",
    "project architecture\n====================",
    "| project | architecture |\n| --- | --- |\n| June | Announcement |",
    "project | architecture\n:--- | ---:\nJune | Announcement",
    "- [project architecture](overview.md)",
    "- [project architecture][overview]",
    "https://example.test/project/architecture",
])
def test_metadata_terms_with_unrelated_body_do_not_qualify(metadata):
    text = f"{metadata}\n\nUnrelated release announcement."
    result = qualify_evidence(
        {"query_terms": ["project", "architecture"], "qualified": True},
        query_id="q", visible_text=text, evidence_text=text,
    )
    assert not result.qualified
    assert result.trace["matched_terms"] == []
    assert result.reason == "insufficient_visible_match"


@pytest.mark.parametrize("metadata", [
    "# WidgetClient",
    "| WidgetClient |\n| --- |",
    "- [WidgetClient](api.md)",
])
def test_metadata_cannot_supply_exact_or_parent_exact_terms(metadata):
    text = f"{metadata}\n\nIt persists records on disk."
    result = qualify_evidence(
        {"query_terms": ["persists", "WidgetClient"],
         "exact_terms": ["WidgetClient"], "parent_exact_terms": ["WidgetClient"]},
        query_id="q", visible_text=text,
    )
    assert not result.qualified
    assert result.trace["matched_terms"] == ["persists"]
    assert result.trace["missing_exact_terms"] == ["widgetclient"]
    assert result.trace["missing_parent_exact_terms"] == ["widgetclient"]


def test_heading_can_identify_subject_for_already_relevant_body():
    text = (
        "# DocAtlas Docs MCP server\n\n"
        "The public tools include get_docs_context and prepare_docs."
    )
    result = qualify_evidence(
        {
            "query_terms": ["DocAtlas", "MCP", "public", "tools"],
            "exact_terms": ["DocAtlas"],
            "parent_exact_terms": ["DocAtlas"],
        },
        query_id="q",
        visible_text=text,
    )
    assert result.qualified
    assert result.trace["body_matched_terms"] == ["public", "tools"]
    assert result.trace["heading_context_used"] is True
    assert result.trace["missing_parent_exact_terms"] == []


@pytest.mark.parametrize("text", [
    "WidgetClient reads docs/runtime.md before persisting records.",
    "`WidgetClient` reads `docs/runtime.md` before persisting records.",
    '```python\nWidgetClient.load("docs/runtime.md")\n```',
    '| API | File |\n| --- | --- |\n| WidgetClient | docs/runtime.md |',
    '```python\nvalue = """\nWidgetClient\n==============\ndocs/runtime.md\n"""\n```',
])
def test_substantive_identifiers_and_filenames_still_qualify(text):
    result = qualify_evidence(
        {"query_terms": ["WidgetClient", "docs/runtime.md"],
         "exact_terms": ["WidgetClient", "docs/runtime.md"]},
        query_id="q", visible_text=text,
    )
    assert result.qualified
    assert result.trace["missing_exact_terms"] == []


@pytest.mark.parametrize("candidate,reason", [
    (None, "missing_project_identity"),
    ({}, "missing_project_identity"),
    ({"project_identity": "foreign"}, "wrong_project_identity"),
    ({"project_identity": "repo", "risk_flags": ["unsafe"]}, "unsafe_evidence"),
])
def test_expected_identity_and_safety_do_not_require_source_class(candidate, reason):
    result = qualify_evidence(
        {"query_terms": ["storage"]}, query_id="q",
        visible_text="Storage persists records.", candidate=candidate,
        expected_project_identity="repo",
    )
    assert not result.qualified
    assert result.reason == reason
