"""Original mixed-language query remains unchanged; only inspection is enabled."""
import json

from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from docmancer.mcp.docs_server import read_docs_resource


def test_literal_mixed_script_phrase_is_optional_not_original_proof():
    question = "Как работает resource cache, сохраняя ограничения?"
    plan = build_documentation_query_plan(question)
    runs = [q for q in plan.queries if q.text == "resource cache"]
    assert len(runs) == 1
    assert runs[0].text in question
    assert runs[0].origin == "retrieval_hint"
    assert runs[0].coverage_required is False
    assert runs[0].public_parent_query_id is None
    assert plan.original_question == question
    assert plan.queries[0].text == question


def test_original_negative_option_question_is_recoverable_without_host_hints(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c["id"] == "typer-05")
    docs = documents_for("typer", manifest)
    root = tmp_path / "project"
    write_project(root, docs)
    fact = case["required_claims"][0]["witness_sets"][0]["parts"][0]["text"]
    request = {"question": case["question"], "project_path": str(root), "scope": "all"}
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        payload, trace = observe_call(service, request)
        assert audit_payload(payload, trace["snapshot"], root) == []
        text = [s["snippet"] for s in payload.get("sources", [])]
        if not any(fact in s for s in text):
            assert len(payload.get("read_next", [])) == 1, payload
            target = payload["read_next"][0]
            read = json.loads(read_docs_resource(target["source_uri"], service)["text"])
            assert read["status"] in {"complete", "truncated"}
            assert read["content_sha256"] == target["snapshot_sha256"]
            assert docs_context_budget_tokens(read) <= 600
            assert read["snippet"] in "\n".join(docs[target["path"]].splitlines()[read["line_start"]-1:read["line_end"]])
            text.append(read["snippet"])
        assert any(fact in s for s in text), {"payload": payload, "read_text": text}
    assert "lookup_queries" not in request
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False
    assert "query-original" not in payload.get("covered_query_ids", [])
