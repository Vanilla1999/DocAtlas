"""Report-only acceptance tests; no model inference or mocked semantic judge."""
from copy import deepcopy

import pytest

from eval.tdd_context_sufficiency import summarize_assessment

CHECKS = {"transport_ok": True, "citation_integrity": True, "budget_ok": True}


def assessment(*states):
    return {
        "case_id": "install-and-verify",
        "claims": {
            key: {"status": state, "unreviewed_evidence_ids": []}
            for key, state in zip(("install", "verify"), states, strict=True)
        },
        "optional_claims": {},
        "review_queue": [],
        "unreviewed_sources": [],
        "rejected_sources": [],
    }


def summarize(data, **checks):
    return summarize_assessment(
        data, required_ids=("install", "verify"), **{**CHECKS, **checks}
    )


def test_real_citations_do_not_compensate_for_missing_required_fact():
    result = summarize(assessment("supported", "missing"))
    assert result["verdict"] == "FAIL"
    assert result["required_claim_coverage"] == 0.5
    assert result["required_supported"] == 1
    assert result["required_count"] == 2
    assert result["full_required_coverage"] is False
    assert result["citation_integrity"] is True


def test_all_verified_required_facts_pass_without_authorizing_runtime():
    result = summarize(assessment("supported", "supported"))
    assert result["verdict"] == "PASS"
    assert result["full_required_coverage"] is True
    assert result["final_answer_quality"] == "NOT_MEASURED"
    assert result["report_only"] is True
    assert {"answer_supported", "edit_ready"}.isdisjoint(result)


@pytest.mark.parametrize("field", tuple(CHECKS))
def test_failed_external_check_cannot_be_averaged_away(field):
    result = summarize(assessment("supported", "supported"), **{field: False})
    assert result["verdict"] == "FAIL"
    assert result["required_claim_coverage"] == 1.0
    assert result[field] is False


@pytest.mark.parametrize("field", tuple(CHECKS))
def test_unmeasured_external_check_never_passes(field):
    result = summarize(assessment("supported", "supported"), **{field: None})
    assert result["verdict"] == "NOT_EVALUATED"
    assert field in result["unmeasured_checks"]


@pytest.mark.parametrize("value", [0, 1, "false", [], {}])
@pytest.mark.parametrize("field", tuple(CHECKS))
def test_boolean_checks_reject_truthiness_coercion(field, value):
    with pytest.raises(ValueError):
        summarize(assessment("supported", "supported"), **{field: value})


def test_needs_review_is_neither_pass_nor_false_answer():
    result = summarize(assessment("supported", "needs_review"))
    assert result["verdict"] == "REVIEW_REQUIRED"
    assert result["review_required"] is True
    assert result["required_claim_coverage"] == 0.5


@pytest.mark.parametrize("field", ["review_queue", "unreviewed_sources"])
def test_review_queue_survives_even_with_full_required_coverage(field):
    data = assessment("supported", "supported")
    data[field] = [{"evidence_id": "ev-unknown"}]
    result = summarize(data)
    assert result["verdict"] == "REVIEW_REQUIRED"
    assert result["full_required_coverage"] is True
    assert result["review_complete"] is False


def test_unreviewed_claim_ids_cannot_be_hidden_by_empty_queue():
    data = assessment("supported", "supported")
    data["claims"]["verify"]["unreviewed_evidence_ids"] = ["ev-unknown"]
    result = summarize(data)
    assert result["verdict"] == "REVIEW_REQUIRED"


def test_confirmed_missing_fact_dominates_review_but_does_not_erase_it():
    result = summarize(assessment("missing", "needs_review"))
    assert result["verdict"] == "FAIL"
    assert result["review_required"] is True


def test_contradiction_dominates_review_and_valid_citations():
    result = summarize(assessment("contradicted", "needs_review"))
    assert result["verdict"] == "FAIL"
    assert result["claim_ids_by_status"]["contradicted"] == ["install"]
    assert result["review_required"] is True


@pytest.mark.parametrize("state,verdict", [("missing", "PASS"), ("supported", "PASS"), ("needs_review", "REVIEW_REQUIRED"), ("contradicted", "FAIL")])
def test_optional_claims_never_change_required_denominator(state, verdict):
    data = assessment("supported", "supported")
    data["optional_claims"]["bonus"] = {"status": state, "unreviewed_evidence_ids": []}
    result = summarize(data)
    assert result["verdict"] == verdict
    assert result["required_count"] == 2
    assert result["required_supported"] == 2


def test_policy_rejected_source_blocks_acceptance_even_with_all_facts():
    data = assessment("supported", "supported")
    data["rejected_sources"] = [{"evidence_id": "ev-other", "reason": "policy_mismatch:scope"}]
    result = summarize(data)
    assert result["verdict"] == "FAIL"
    assert "source_policy_rejected" in result["reasons"]


@pytest.mark.parametrize("ids", [(), ("install", "install"), ("", "verify"), (" ", "verify"), "install", (17, "verify")])
def test_empty_or_invalid_required_inventory_is_not_a_perfect_score(ids):
    with pytest.raises(ValueError):
        summarize_assessment(assessment("supported", "supported"), required_ids=ids, **CHECKS)


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_required_inventory_is_bound_to_caller_not_report_denominator(change):
    data = assessment("supported", "supported")
    if change == "missing":
        del data["claims"]["verify"]
    else:
        data["claims"]["extra"] = {"status": "supported", "unreviewed_evidence_ids": []}
    with pytest.raises(ValueError):
        summarize(data)


@pytest.mark.parametrize("state", [None, "true", "unverified", 1])
def test_invalid_claim_status_fails_as_evaluator_error(state):
    with pytest.raises(ValueError):
        summarize(assessment("supported", state))


@pytest.mark.parametrize("field", ["review_queue", "unreviewed_sources", "rejected_sources"])
@pytest.mark.parametrize("value", [None, {}, False])
def test_missing_or_malformed_review_inventory_is_not_silently_empty(field, value):
    data = assessment("supported", "supported")
    data[field] = value
    with pytest.raises(ValueError):
        summarize(data)
    del data[field]
    with pytest.raises(ValueError):
        summarize(data)


def test_input_is_not_mutated_and_output_is_deterministic():
    data = assessment("supported", "supported")
    original = deepcopy(data)
    first = summarize(data)
    assert first["verdict"] == "PASS"
    assert first == summarize(data)
    assert data == original


def test_existing_evaluator_preserves_pending_review_after_recognized_support():
    from eval.evidence_quality_v2.semantic import assess_context

    case = {
        "id": "frozen-one-fact", "project_group": "fixture",
        "required_claims": [{"id": "install", "witness_sets": [{
            "parts": [{"path": "guide.md", "text": "Install with alpha."}]
        }]}],
    }
    payload = {"sources": [
        {"evidence_id": "ev-known", "path_or_url": "guide.md", "snippet": "Install with alpha."},
        {"evidence_id": "ev-unknown", "path_or_url": "guide.md", "snippet": "An unreviewed alternative statement."},
    ]}
    before = deepcopy(payload)
    raw = assess_context(case, payload, {"guide.md": {"project_group": "fixture"}})
    assert raw["context_sufficiency"] == "sufficient"
    assert raw["review_queue"]
    result = summarize_assessment(raw, required_ids=("install",), **CHECKS)
    assert result["verdict"] == "REVIEW_REQUIRED"
    assert result["full_required_coverage"] is True
    assert result["final_answer_quality"] == "NOT_MEASURED"
    assert payload == before


def test_existing_evaluator_missing_second_fact_is_not_full_support():
    from eval.evidence_quality_v2.semantic import assess_context

    case = {
        "id": "frozen-two-facts", "project_group": "fixture",
        "required_claims": [
            {"id": "install", "witness_sets": [{"parts": [{"text": "Install with alpha."}]}]},
            {"id": "verify", "witness_sets": [{"parts": [{"text": "Verify with beta."}]}],
             "known_insufficient": ["Install with alpha."]},
        ],
    }
    payload = {"sources": [{"evidence_id": "ev-one", "path_or_url": "guide.md", "snippet": "Install with alpha."}]}
    raw = assess_context(case, payload, {"guide.md": {"project_group": "fixture"}})
    assert raw["claims"]["verify"]["status"] == "missing"
    result = summarize(raw)
    assert result["verdict"] == "FAIL"
    assert result["required_claim_coverage"] == 0.5
