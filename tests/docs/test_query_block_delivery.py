"""Original unanswered questions through the real index and public handler."""
import pytest

from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol, registry_for
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context


@pytest.mark.parametrize("case_id", ["fastapi-02", "fastapi-06"])
def test_original_direct_question_delivers_required_fact(tmp_path, case_id):
    _, cases, manifest = load_protocol()
    case = next(row for row in cases if row["id"] == case_id)
    documents = documents_for(case["project_group"], manifest)
    project = tmp_path / "project"
    write_project(project, documents)
    request = {"question": case["question"], "project_path": str(project), "scope": "all"}
    with isolated_service(tmp_path / "state") as (service, config):
        inventory = index_project(service, config, project)
        assert not inventory["excluded_or_failed_paths"]
        payload, trace = observe_call(service, request)
    assert "lookup_queries" not in request
    assert audit_payload(payload, trace["snapshot"], project) == []
    assert payload["answer_supported"] is False
    assert payload["edit_ready"] is False
    assessment = assess_context(case, payload, registry_for(case["project_group"], manifest))
    assert assessment["required_supported"] == len(case["required_claims"]), {
        "case_id": case_id, "request": request, "payload": payload, "assessment": assessment,
    }
