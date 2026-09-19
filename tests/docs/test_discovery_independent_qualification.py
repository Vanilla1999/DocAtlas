from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _qualify_candidate_lookups
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan


def _plan() -> DocumentationQueryPlan:
    return DocumentationQueryPlan(
        "storage persists records",
        (DocumentationLookup("query-original", "storage persists records", "original"),),
    )


def _chunk(project_identity: str = "repo") -> RetrievedChunk:
    return RetrievedChunk(
        source="docs/storage.md",
        chunk_index=0,
        score=1,
        text="Storage persists records on disk.",
        metadata={
            "source_class": "project_doc",
            "project_identity": project_identity,
            "retrieval_query_matches": {
                "query-hint-1": {"query_text": "storage", "qualified": True},
            },
        },
    )


def test_hint_discovery_does_not_hide_an_independent_root_match():
    result = _qualify_candidate_lookups(
        [_chunk()], _plan(), expected_project_identity="repo", lifecycle_intent="current",
    )[0]
    trace = result.metadata["retrieval_query_matches"].get("query-original")
    assert trace is not None
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "cross_lane_body"
    assert trace["lexical_score"] == 0.0


def test_independent_root_check_keeps_project_identity_guard():
    result = _qualify_candidate_lookups(
        [_chunk("foreign")], _plan(), expected_project_identity="repo", lifecycle_intent="current",
    )[0]
    trace = result.metadata["retrieval_query_matches"].get("query-original")
    assert trace is not None
    assert trace["qualified"] is False
