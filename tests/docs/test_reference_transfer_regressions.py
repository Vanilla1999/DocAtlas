"""Exposed external80 regressions; these are not independent validation."""
import pytest
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context
from tests.docs._reference_binding_fixtures import capture_reference_case


@pytest.mark.parametrize("case_id", ["typer-01", "httpx-07"])
def test_existing_requested_fact_is_retained_on_exposed_corpus(tmp_path, case_id):
    _, cases, manifest = load_protocol()
    case = next(case for case in cases if case["id"] == case_id)
    project = case["project_group"]
    cap = capture_reference_case(tmp_path, documents_for(project, manifest), case["question"])
    result = assess_context(case, cap["public_payload"], registry_for(project, manifest))
    assert result["claims"]["required"]["status"] == "supported", result["claims"]
    assert cap["public_payload"]["answer_supported"] is False


def test_prefit_ranking_preserves_verified_needs_after_anchor_direction():
    from tests.docs.test_project_doc_ranking import FakeChunk
    from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
    from docmancer.docs.domain.project_query_intent import classify_project_query_intent
    question = "What is RelayClient default timeout and which exception? Also identify a private deployment value."
    def candidate(name, score, traces):
        return FakeChunk("docs/client.md", name, score, "RelayClient documentation " + name,
                         metadata={"retrieval_query_matches": traces})
    anchor = candidate("example", 100, {"query-anchor-1": {"qualified": True}})
    weak = candidate("setup", 50, {"query-hint-1": {"qualified": True}})
    fact = candidate("default and exception", .1, {
        "query-need-1": {"qualified": True, "query_origin": "retrieval_need", "need_local_witness": True},
        "query-need-2": {"qualified": True, "query_origin": "retrieval_need", "need_local_witness": True}})
    ranked = rerank_project_doc_chunks([anchor, weak, fact], question=question,
        intent=classify_project_query_intent(question), limit=2)
    assert [c.heading_path for c in ranked] == [anchor.heading_path, fact.heading_path]
