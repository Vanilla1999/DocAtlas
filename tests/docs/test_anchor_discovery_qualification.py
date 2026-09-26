"""An exact anchor's body match must not depend on the lane that found it."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application._project_docs_service_part03 import _qualify_candidate_lookups
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.application.reference_query_tagging import _tag_retrieval_query
from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan

QUESTION = "Объясни существенные свойства неизвестного протокола."


def _anchor(text="--zone"):
    return DocumentationLookup(
        "query-anchor-1", text, "exact_anchor", relation="exact_anchor",
        public_parent_query_id="query-original", forbidden_catalog_roles=("roadmap",),
    )


def _plan(anchor):
    return DocumentationQueryPlan(QUESTION, (
        DocumentationLookup("query-original", QUESTION, "original"), anchor,
    ))


def _chunk(body="Use --zone global to preserve the configuration.", **metadata):
    return RetrievedChunk(source="docs/storage.md", chunk_index=0, text=body, score=91,
        metadata={"project_identity": "repo", "source_class": "project_doc",
            "retrieval_query_ids": (),
            "retrieval_query_matches": {"query-original": {"qualified": False}},
            **metadata})


def _qualify(chunk, anchor):
    return _qualify_candidate_lookups([chunk], _plan(anchor),
        expected_project_identity="repo", lifecycle_intent="current")[0]


@pytest.mark.parametrize("token", ["--zone", "clear-index", "StorageMode"])
def test_original_lane_candidate_gets_independent_exact_anchor_check(token):
    anchor = _anchor(token)
    candidate = _chunk(f"Use {token} to preserve the configuration.")
    before = deepcopy(candidate.metadata)
    result = _qualify(candidate, anchor)
    matches = result.metadata["retrieval_query_matches"]
    assert anchor.query_id in matches, "A planned exact anchor was not checked across lanes"
    trace = matches[anchor.query_id]
    assert trace["qualified"] is True
    assert trace["qualification_route"] == "cross_lane_body"
    assert trace["lexical_score"] == 0.0
    assert "bm25_cost" not in trace
    assert result.score == candidate.score
    assert result.metadata["retrieval_query_ids"] == (anchor.query_id,)
    assert matches["query-original"] == before["retrieval_query_matches"]["query-original"]
    assert "derived_from_query_id" not in matches["query-original"]
    assert candidate.metadata == before


@pytest.mark.parametrize("changes", [
    {"project_identity": "foreign"}, {"stale": True},
    {"index_freshness": "stale"}, {"risk_flags": ["unsafe"]},
    {"lifecycle_status": "deprecated"}, {"project_doc_reason": "roadmap"},
])
def test_cross_lane_anchor_does_not_bypass_evidence_policy(changes):
    anchor = _anchor()
    result = _qualify(_chunk(**changes), anchor)
    trace = result.metadata["retrieval_query_matches"].get(anchor.query_id)
    assert trace is not None, "The actual existing qualifier must evaluate the candidate"
    assert trace["qualified"] is False
    assert anchor.query_id not in result.metadata["retrieval_query_ids"]


@pytest.mark.parametrize("body", [
    "Use --zones global to preserve the configuration.",
    "# --zone\n\nThis paragraph discusses unrelated settings.",
    "[--zone](reference.md)", "Nothing here names that flag.",
])
def test_anchor_needs_exact_substantive_body_not_hidden_or_heading_match(body):
    anchor = _anchor()
    result = _qualify(_chunk(body, title="--zone", heading_path="--zone",
        retrieval_text="Use --zone global to preserve the configuration."), anchor)
    trace = result.metadata["retrieval_query_matches"].get(anchor.query_id)
    assert trace is not None
    assert trace["qualified"] is False


@pytest.mark.parametrize("body", [
    "Use --zone global to preserve the configuration.", "Unrelated content.",
])
def test_existing_anchor_discovery_trace_is_not_overwritten(body):
    anchor = _anchor()
    tagged = _tag_retrieval_query([_chunk(body)], anchor.query_id, anchor.text, anchor,
        expected_project_identity="repo")[0]
    before = deepcopy(tagged.metadata)
    result = _qualify(tagged, anchor)
    assert result.metadata == before
    assert tagged.metadata == before


def test_an_audited_child_is_not_treated_as_an_independent_exact_anchor():
    child = DocumentationLookup("query-child-1", "--zone", "canonical_intent",
        relation="audited_rewrite", public_parent_query_id="query-original")
    result = _qualify(_chunk(), child)
    assert child.query_id not in result.metadata["retrieval_query_matches"]
    assert result.metadata["retrieval_query_matches"]["query-original"]["qualified"] is False


def test_exact_body_survives_real_query_window_without_an_anchor_lane_hit(tmp_path):
    calls = []
    anchor = _anchor()
    class Agent:
        config = SimpleNamespace(query=SimpleNamespace(default_limit=1))
        def query(self, text, *, limit, budget, expand, filters):
            calls.append((text, dict(filters)))
            if text != QUESTION:
                return []
            return [RetrievedChunk(source=path, chunk_index=0, text=body, score=score,
                metadata={"project_identity": filters["project_identity"], "token_estimate": 20})
                for path, body, score in [
                    ("docs/topical.md", "Unrelated navigation.", 10),
                    ("docs/flag.md", "Use --zone global to preserve the configuration.", 1),
                ]]
    class Facade:
        def _agent_instance(self):
            return Agent()
    chunks = ProjectDocsService(Facade()).query_project_docs(str(tmp_path), QUESTION,
        documentation_query_plan=_plan(anchor), limit=1, scope="project")
    assert [chunk.source for chunk in chunks] == ["docs/flag.md"]
    assert chunks[0].metadata["retrieval_query_ids"] == (anchor.query_id,)
    assert len(calls) == 3, "Cross-checking must not add retrieval calls"
    assert all(filters["doc_scope"] == "project" for _, filters in calls)
