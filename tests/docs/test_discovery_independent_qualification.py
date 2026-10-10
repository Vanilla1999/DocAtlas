from copy import deepcopy

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _qualify_candidate_lookups
from docmancer.docs.application.context_selection import attributable_query_ids
from docmancer.docs.application.reference_query_tagging import _record_query_discovery
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


def test_later_lookup_preserves_each_actual_discovery_without_minting_parent_credit():
    original = _plan().queries[0]
    lookups = (
        DocumentationLookup("query-lookup-1", "compression reduces record size", "host_lookup", relation="host_lookup"),
        DocumentationLookup("query-lookup-2", "journal recovers committed state", "host_lookup", relation="host_lookup"),
    )
    chunk = _chunk().model_copy(update={"text": (
        "Storage persists records on disk. Compression reduces record size. Journal recovers committed state."
    )})
    receipts = {}
    _record_query_discovery(receipts, [chunk], original)
    for lookup in lookups:
        _record_query_discovery(receipts, [chunk], lookup)
    before = deepcopy(chunk)
    expected = {original.query_id, *(lookup.query_id for lookup in lookups)}
    for order in (lookups, tuple(reversed(lookups))):
        plan = DocumentationQueryPlan(original.text, (original, *order))
        result = _qualify_candidate_lookups([chunk], plan, expected_project_identity="repo",
                                          lifecycle_intent="current", discovery_records=receipts)[0]
        assert attributable_query_ids([result.metadata]) == expected, "original_discovery_not_erased_by_lookup"
        assert all(not trace.get("public_parent_query_id") and not trace.get("derived_from_query_ids")
                   for trace in result.metadata["retrieval_query_matches"].values())
        assert result.metadata["retrieval_query_matches"]["query-original"]["lexical_score"] == chunk.score
        assert chunk == before


def test_metadata_and_other_source_windows_cannot_forge_original_discovery():
    original = _plan().queries[0]
    lookup = DocumentationLookup("query-lookup-1", "records on disk", "host_lookup", relation="host_lookup")
    plan = DocumentationQueryPlan(original.text, (original, lookup))
    chunk = _chunk()
    root_receipts = {}
    _record_query_discovery(root_receipts, [chunk], original)
    variants = [
        ("no_original_acquisition", chunk, {}),
        ("different_path", chunk.model_copy(update={"source": "docs/other.md"}), root_receipts),
        ("different_window", chunk.model_copy(update={"chunk_index": 1}), root_receipts),
        ("changed_body", chunk.model_copy(update={"text": "Storage persists records on disk in a changed window."}), root_receipts),
        ("different_scope", chunk.model_copy(update={"metadata": {**chunk.metadata, "doc_scope": "module", "module_path": "other"}}), root_receipts),
        ("different_generation", chunk.model_copy(update={"metadata": {**chunk.metadata, "generation_id": "other"}}), root_receipts),
    ]
    for name, candidate, receipts in variants:
        candidate = candidate.model_copy(update={"metadata": {
            **candidate.metadata,
            "retrieval_query_matches": {"query-original": {
                "query_text": original.text, "qualified": True, "admission_only": False,
                "query_origin": "original", "relation": "direct", "lexical_score": 999,
            }},
        }})
        result = _qualify_candidate_lookups([candidate], plan, expected_project_identity="repo",
                                          lifecycle_intent="current", discovery_records=receipts)[0]
        trace = result.metadata["retrieval_query_matches"]["query-original"]
        assert trace["qualified"] is True, name  # Relevance alone is not a discovery receipt.
        assert trace["admission_only"] is True, "forged_original_discovery:" + name
        assert attributable_query_ids([result.metadata]) == {"query-lookup-1"}, name
        assert trace["lexical_score"] == 0.0
