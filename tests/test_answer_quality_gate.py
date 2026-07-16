from __future__ import annotations

import copy
import math

from eval.answer_quality_gate import (
    canonical_bytes,
    compare_pareto_candidate,
    evaluate_projection_contract,
    load_case_contracts,
    load_protocol,
    protocol_manifest,
    validate_protocol,
)


def _fit_estimate(payload):
    payload["estimated_tokens"] = 0
    for _ in range(10):
        actual = max(1, math.ceil(len(canonical_bytes(payload)) / 4))
        if payload["estimated_tokens"] == actual:
            return payload
        payload["estimated_tokens"] = actual
    raise AssertionError("synthetic projection token estimate did not converge")


def _docs_contract():
    return {
        "contract_id": "synthetic-docs",
        "source_ref": "synthetic:docs",
        "taxonomy": "exact_api",
        "result_kind": "docs_answer",
        "expected_status": "ok",
        "required_answer_facts": ["Client.open"],
        "acceptable_evidence": ["docs/api.md"],
        "forbidden_claims": ["Client.openLegacy"],
        "forbidden_versions": ["1.0"],
        "exact_identifiers": ["Client.open"],
        "required_patch_fields": {},
        "required_public_commands": [],
        "maximum_visible_tokens": 800,
    }


def _docs_projection():
    source = {
        "evidence_id": "ev-docs",
        "path_or_url": "docs/api.md",
        "section": "Open",
        "snippet": "Call Client.open(config).",
        "version_binding": "2.0",
        "content_sha256": "a" * 64,
    }
    projection = _fit_estimate({
        "status": "ok",
        "kind": "docs_answer",
        "answer": "Call Client.open(config).",
        "answer_evidence_ids": ["ev-docs"],
        "sources": [source],
    })
    return projection, {"ev-docs": dict(source)}


def _patch_contract():
    return {
        "contract_id": "synthetic-patch",
        "source_ref": "synthetic:patch",
        "taxonomy": "patch_contract",
        "result_kind": "patch_context",
        "expected_status": "ok",
        "required_answer_facts": [],
        "acceptable_evidence": ["AGENTS.md", "src/worker.py"],
        "forbidden_claims": ["disable isolation"],
        "forbidden_versions": [],
        "exact_identifiers": ["Worker.run"],
        "required_patch_fields": {
            "objective": ["Update Worker.run"],
            "targets": ["src/worker.py"],
            "invariants": ["preserve isolation"],
            "checks": ["pytest tests/test_worker.py"],
        },
        "required_public_commands": ["pytest tests/test_worker.py"],
        "maximum_visible_tokens": 1500,
    }


def _patch_projection():
    policy = {
        "evidence_id": "ev-policy",
        "path_or_url": "AGENTS.md",
        "section": "Rules",
        "snippet": "Preserve isolation. Run pytest tests/test_worker.py.",
        "version_binding": "repository",
        "content_sha256": "b" * 64,
    }
    target = {
        "evidence_id": "ev-target",
        "path_or_url": "src/worker.py",
        "section": "Worker.run",
        "snippet": "def run(): pass",
        "version_binding": "repository",
        "content_sha256": "c" * 64,
    }
    projection = _fit_estimate({
        "status": "ok",
        "kind": "patch_context",
        "objective": "Update Worker.run",
        "sources": [policy, target],
        "targets": {"likely_files": ["src/worker.py"], "symbols": ["Worker.run"]},
        "invariants": [{"claim": "Preserve isolation", "evidence_ids": ["ev-policy"]}],
        "forbidden_changes": [],
        "implementation_guidance": [],
        "checks": {
            "tests": [{
                "command": "pytest tests/test_worker.py",
                "evidence_ids": ["ev-policy"],
            }]
        },
        "uncertainties": [],
    })
    return projection, {
        "ev-policy": dict(policy),
        "ev-target": dict(target),
    }


def test_task43_protocol_is_frozen_complete_and_does_not_execute_real_cases():
    protocol = load_protocol()
    contracts = load_case_contracts()

    assert validate_protocol(protocol) == []
    assert len(contracts) == 29
    assert len({row["source_ref"] for row in contracts}) == 29
    assert protocol["case_counts"] == {"task39": 16, "task42": 13, "total": 29}
    assert protocol["execution_policy"]["real_case_execution"] == (
        "forbidden_until_protocol_merge"
    )


def test_task43_protocol_manifest_is_deterministic_and_digest_bound():
    first = protocol_manifest()
    second = protocol_manifest()

    assert canonical_bytes(first) == canonical_bytes(second)
    assert len(first["protocol_sha256"]) == 64
    assert len(first["case_contract_digest"]) == 64
    assert first["case_count"] == 29


def test_task43_protocol_rejects_binding_and_gate_mutation():
    protocol = copy.deepcopy(load_protocol())
    protocol["file_bindings"]["eval/retrieval_quality/development.json"] = "0" * 64
    protocol["quality_gates"]["unsupported_claim_violations_max"] = 1

    errors = validate_protocol(protocol)

    assert "binding:digest_mismatch:eval/retrieval_quality/development.json" in errors
    assert "protocol:quality_gates_changed" in errors


def test_docs_contract_accepts_grounded_answer_and_rejects_unsupported_claim():
    projection, snapshot = _docs_projection()

    assert evaluate_projection_contract(
        projection, snapshot, _docs_contract()
    )["passed"] is True

    projection["answer"] += " Client.openLegacy is also safe."
    _fit_estimate(projection)
    result = evaluate_projection_contract(projection, snapshot, _docs_contract())

    assert result["passed"] is False
    assert "claim:forbidden:Client.openLegacy" in result["errors"]
    assert "answer:unsupported_claim" in result["errors"]


def test_docs_contract_rejects_unknown_or_tampered_citation():
    projection, snapshot = _docs_projection()
    projection["sources"][0]["content_sha256"] = "0" * 64
    projection["answer_evidence_ids"] = ["ev-missing"]
    _fit_estimate(projection)

    result = evaluate_projection_contract(projection, snapshot, _docs_contract())

    assert "citation:content_hash_mismatch" in result["errors"]
    assert "answer:evidence_ids_invalid" in result["errors"]


def test_patch_contract_requires_targets_invariants_commands_and_evidence_ids():
    projection, snapshot = _patch_projection()

    assert evaluate_projection_contract(
        projection, snapshot, _patch_contract()
    )["passed"] is True

    projection["targets"] = {"likely_files": [], "symbols": []}
    projection["invariants"][0]["evidence_ids"] = ["ev-missing"]
    projection["checks"] = {"tests": []}
    _fit_estimate(projection)
    result = evaluate_projection_contract(projection, snapshot, _patch_contract())

    assert result["passed"] is False
    assert any(
        error.startswith("patch:targets:required_fact_missing")
        for error in result["errors"]
    )
    assert any(
        error.startswith("patch:invariants:evidence_ids_invalid")
        for error in result["errors"]
    )
    assert any(error.startswith("patch:required_command_missing") for error in result["errors"])


def test_insufficient_evidence_cannot_authorize_edits():
    contract = _docs_contract()
    contract["expected_status"] = "insufficient_evidence"
    contract["required_answer_facts"] = []
    contract["acceptable_evidence"] = []
    projection = _fit_estimate({
        "status": "insufficient_evidence",
        "kind": "docs_answer",
        "missing": ["Canonical evidence is unavailable."],
    })

    assert evaluate_projection_contract(projection, {}, contract)["passed"] is True

    projection["implementation_guidance"] = ["Edit src/auth.py"]
    _fit_estimate(projection)
    result = evaluate_projection_contract(projection, {}, contract)

    assert "projection:insufficient_authorizes_success" in result["errors"]


def test_pareto_rule_is_non_compensating_and_per_case():
    group = {
        "required_fact_rate": 1.0,
        "answer_fact_coverage": 1.0,
        "forbidden_source_violations": 0,
        "forbidden_version_violations": 0,
        "unsupported_claim_violations": 0,
        "citation_validity_rate": 1.0,
        "insufficient_false_success_rate": 0.0,
        "median_visible_tokens": 200.0,
        "retrieval_projection_p95_ms": 4.0,
    }
    baseline = {
        "groups": {"docs_answer": dict(group), "patch_context": dict(group)},
        "holdout": {"recall@5": 1.0, "answer_fact_coverage": 1.0},
        "case_gates": {"protected": {"passed": True}},
    }
    candidate = copy.deepcopy(baseline)
    candidate["groups"]["docs_answer"]["median_visible_tokens"] = 100.0
    candidate["case_gates"]["protected"]["passed"] = False

    errors = compare_pareto_candidate(candidate, baseline)

    assert "protected:protected_case_regressed" in errors
