#!/usr/bin/env python3
"""Five compact oracle controls; synthetic DTOs are never public-runtime evidence."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from pathlib import Path

from eval.agent_developer_v1.current_retrieval_runtime import (
    RUNTIME_REQUIRED_PATHS, bytes_sha256, sha256_json, verify_runtime_manifest,
)
from eval.agent_developer_v1.paraphrase_robustness import (
    FAMILIES, load_json, load_protocol, score_observation, verify_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _control(case: dict, *, with_source: bool | None = None) -> dict:
    """Independently authored unit input, not an executed MCP response."""
    if with_source is None:
        with_source = not case["negative_control"]
    identity = "local:" + "1" * 64
    path, fact = case["candidate_source"], case["candidate_text"]
    material = {"path": path, "section": "fixture", "content": fact, "snippet": fact, "version": "unversioned"}
    source = {
        "evidence_id": "ev-unit-control", "path_or_url": path, "section": "fixture",
        "snippet": fact, "version_binding": "unversioned", "content_sha256": sha256_json(material),
        "project_identity": identity, "authority": "source_of_truth", "scope": "project",
        "line_start": 1, "line_end": len(fact.splitlines()),
    }
    state = {
        "generation": "gen-unit-control", "store_sha256": "2" * 64, "catalog_sha256": "3" * 64,
        "document_sha256": {path: hashlib.sha256(fact.encode()).hexdigest()},
    }
    return {
        "execution": "oracle_unit_control", "error": None, "project_identity": identity,
        "request": {"question": case["question"], "scope": "project", "lookup_queries": []},
        "service_requests": [{
            "question": case["question"], "scope": "project", "lookup_queries": [],
            "project_identity": identity, "prepare_project_docs": False,
            "allow_network": False, "force_refresh": False,
        }],
        "preparation": {"expected_paths": [path], "indexed_paths": [path],
                        "excluded_or_failed_paths": [], "unexpected_paths": []},
        "state_before": state, "state_after": deepcopy(state),
        "public_payload": {
            "status": "ok" if with_source else "insufficient_evidence", "kind": "docs_context",
            "context_status": "ready" if with_source else "insufficient_evidence",
            "context_available": with_source, "support_status": "retrieval_only",
            "answer_policy": "cite_only", "answer_supported": False,
            "answer_available": False, "edit_ready": False, "estimated_tokens": 6000,
            "covered_query_ids": ["query-original"] if with_source else [],
            "missing_query_ids": [] if with_source else ["query-original"],
            "sources": [source] if with_source else [],
        },
        "bindings": {"ev-unit-control": {"projected_source": deepcopy(source), "candidate_hash_material": material}} if with_source else {},
        "pipeline_diagnostics": {"observer_counts": {"retrieval_calls": 1, "validation_calls": 1}},
    }


def _score(case, observation):
    return score_observation(case, observation, expected_execution="oracle_unit_control")


def test_exact_report_and_family_separation() -> None:
    protocol = load_protocol()
    assert len(protocol["cases"]) == 14
    assert {case["family"] for case in protocol["cases"]} == set(FAMILIES)
    assert sum(case["require_discovery"] for case in protocol["cases"]) == 10
    assert sum(case["require_support"] for case in protocol["cases"]) == 5
    assert sum(case["negative_control"] for case in protocol["cases"]) == 2
    positive = protocol["cases"][0]
    unit = _control(positive)
    assert _score(positive, unit)["passed"]
    # A unit fixture cannot pass the public-runtime execution guard.
    assert not score_observation(positive, unit)["checks"]["runtime_completed"]


def test_negative_false_support_fails_closed() -> None:
    case = next(case for case in load_protocol()["cases"] if case["negative_control"])
    baseline = _control(case)
    assert _score(case, baseline)["passed"]
    for key, value in (("answer_supported", True), ("mutation_ready", True), ("answer", "invented answer")):
        changed = deepcopy(baseline)
        changed["public_payload"][key] = value
        assert not _score(case, changed)["checks"]["no_answer_or_edit_authority"], key
    wrong_fact = _control(case, with_source=True)
    assert not _score(case, wrong_fact)["checks"]["negative_source_precision"]


def test_required_discovery_and_support_fail_closed() -> None:
    case = next(case for case in load_protocol()["cases"] if case["id"] == "behavior_orders_store")
    baseline = _control(case)
    assert _score(case, baseline)["passed"]
    missing = _control(case, with_source=False)
    assert not _score(case, missing)["checks"]["required_discovery"]
    assert not _score(case, missing)["checks"]["required_complete_fact"]
    cropped = deepcopy(baseline)
    source = cropped["public_payload"]["sources"][0]
    source["snippet"] = "OrdersDraftStore stores draft orders"
    cropped["bindings"][source["evidence_id"]]["projected_source"] = deepcopy(source)
    result = _score(case, cropped)
    assert result["checks"]["source_integrity"], result["source_errors"]
    assert result["checks"]["required_discovery"]
    assert not result["checks"]["required_complete_fact"]


def test_claim_and_path_leak_fail_closed() -> None:
    case = load_protocol()["cases"][0]
    baseline = _control(case)
    assert _score(case, baseline)["passed"]
    for field, value in (("path_or_url", "/home/user/private.md"), ("line_start", 2),
                         ("project_identity", "local:" + "9" * 64), ("content_sha256", "0" * 64)):
        changed = deepcopy(baseline)
        source = changed["public_payload"]["sources"][0]
        source[field] = value
        changed["bindings"][source["evidence_id"]]["projected_source"] = deepcopy(source)
        assert not _score(case, changed)["checks"]["source_integrity"], field
    changed = deepcopy(baseline)
    changed["service_requests"][0]["question"] += " and another task"
    assert not _score(case, changed)["checks"]["request_identity"]
    changed = deepcopy(baseline)
    changed["service_requests"][0]["lookup_queries"] = ["borrowed lookup"]
    assert not _score(case, changed)["checks"]["no_lookup_or_write_injection"]
    changed = deepcopy(baseline)
    changed["public_payload"]["covered_query_ids"].append("query-lookup-1")
    assert not _score(case, changed)["checks"]["query_attribution"]
    changed = deepcopy(baseline)
    changed["state_after"]["store_sha256"] = "4" * 64
    assert not _score(case, changed)["checks"]["read_only"]


def test_proof_runtime_shard_identity_fails_closed() -> None:
    rows = [{"path": path, "sha256": bytes_sha256(REPO_ROOT / path),
             "imported_as": [path.removesuffix(".py").replace("/", ".")]}
            for path in sorted(RUNTIME_REQUIRED_PATHS)]
    manifest = {"algorithm": "same-process-source-sha256-v1", "files": rows, "sha256": sha256_json(rows)}
    # This is a manifest-validator unit control, not evidence of actual imports.
    verify_runtime_manifest(manifest, REPO_ROOT)
    changed = deepcopy(manifest)
    changed["files"][2]["sha256"] = "0" * 64
    try:
        verify_runtime_manifest(changed, REPO_ROOT)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("changed source hash did not invalidate the manifest")
    changed["sha256"] = sha256_json(changed["files"])
    try:
        verify_runtime_manifest(changed, REPO_ROOT)
    except ValueError as exc:
        assert "current checkout" in str(exc)
    else:
        raise AssertionError("resealed wrong source hash was accepted")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P1.4 source and fidelity oracle controls")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    checks = (
        test_exact_report_and_family_separation, test_negative_false_support_fails_closed,
        test_required_discovery_and_support_fail_closed, test_claim_and_path_leak_fail_closed,
        test_proof_runtime_shard_identity_fails_closed,
    )
    for check in checks:
        check()
        print(f"PASS: {check.__name__}")
    if args.report:
        # An honestly failing real run is valid evidence; the separate gate must
        # still fail it. Do not rerun all14 fixtures merely to test serialization.
        verify_report(load_json(args.report))
        print("PASS: current report integrity (quality verdict unchanged)")
    print(f"P1.4 oracle self-test: PASS ({len(checks)}/{len(checks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
