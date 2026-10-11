"""Exposed external80 regressions; these are not independent validation."""
import pytest
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context
from tests.docs._reference_binding_fixtures import capture_reference_case


@pytest.mark.parametrize("case_id", ["typer-01"])
def test_existing_requested_fact_is_retained_on_exposed_corpus(tmp_path, case_id):
    _, cases, manifest = load_protocol()
    case = next(case for case in cases if case["id"] == case_id)
    project = case["project_group"]
    cap = capture_reference_case(tmp_path, documents_for(project, manifest), case["question"])
    result = assess_context(case, cap["public_payload"], registry_for(project, manifest))
    assert result["claims"]["required"]["status"] == "supported", result["claims"]
    assert cap["public_payload"]["answer_supported"] is False

