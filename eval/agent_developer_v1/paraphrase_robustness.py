"""P1.4 original-question retrieval against frozen, independently authored facts."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from eval.agent_developer_v1.current_retrieval_runtime import (
    authority_errors, build_runtime_manifest, bytes_sha256, canonical_json,
    capture_source_read, sha256_json, source_errors, verify_runtime_manifest,
)

PROTOCOL = "paraphrase-proofability-v1"
REPORT_PROTOCOL = "paraphrase-retrieval-report-v2"
SCHEMA_VERSION = 2
REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "eval" / "agent_developer_v1"
FROZEN_PROTOCOL_SHA256 = "e1586bbd628b488faeebaf271ddf10806b6e2546c307426651bbae2021f26cf5"
FAMILIES = ("exact_identifier", "behavior", "requirements", "policy", "typo", "alias", "negative_control")
HEX64 = re.compile(r"[0-9a-f]{64}")
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _validate_protocol(protocol: dict) -> None:
    if sha256_json(protocol) != FROZEN_PROTOCOL_SHA256:
        raise ValueError("P1.4 frozen questions, facts, labels or negative controls changed")
    if protocol.get("protocol") != PROTOCOL or protocol.get("schema_version") != 1:
        raise ValueError("P1.4 historical protocol identity mismatch")
    cases = protocol["cases"]
    if len(cases) != 14 or Counter(case["family"] for case in cases) != Counter({name: 2 for name in FAMILIES}):
        raise ValueError("P1.4 frozen family inventory drift")


def expected_migration(protocol: dict) -> dict:
    _validate_protocol(protocol)
    return {
        "schema_version": 1,
        "protocol": "paraphrase-current-contract-migration-v1",
        "frozen_protocol_sha256": FROZEN_PROTOCOL_SHA256,
        "historical_report_sha256": "adb30f8a8b8e99dc1a2176cda420bbfd4af8e5d8bdaf1947d9877dfec8be6bf5",
        "current_report_protocol": REPORT_PROTOCOL,
        "scope": "project",
        "lookup_queries": [],
        "catalog": "finite_authored_source_of_truth_documents",
        "authority": "retrieval_only_never_answer_or_edit_permission",
        "cost_policy": "measure_and_minimize_without_fixed_output_ceiling",
        "crosswalk": [{
            "id": case["id"],
            "require_discovery": case["require_discovery"],
            "require_visible_complete_fact": case["require_support"],
            "require_no_visible_wrong_source": case["negative_control"],
            "historical_support_expectation_retained_as_metadata": case["require_support"],
            "current_discovery": "actual_public_source_with_verified_bytes_and_coordinates",
            "current_fact": "complete_frozen_candidate_text_in_one_visible_source",
        } for case in protocol["cases"]],
    }


def load_protocol() -> dict:
    protocol = load_json(ROOT / "paraphrase_protocol.json")
    _validate_protocol(protocol)
    if load_json(ROOT / "paraphrase_contract_migration.json") != expected_migration(protocol):
        raise ValueError("P1.4 reviewed contract migration drift")
    return protocol


def score_observation(case: dict, observation: dict, *, expected_execution="public_fixture_runtime") -> dict:
    """Pure oracle: frozen input facts, actual visible output, explicit provenance."""
    payload = observation.get("public_payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    sources = payload.get("sources")
    rows = sources if isinstance(sources, list) else []
    documents = {case["candidate_source"]: case["candidate_text"]}
    integrity = source_errors(observation, documents)
    authority = authority_errors(payload)
    discovered = any(isinstance(row, dict) and row.get("path_or_url") == case["candidate_source"] for row in rows)
    fact_visible = any(
        isinstance(row, dict) and row.get("path_or_url") == case["candidate_source"]
        and isinstance(row.get("snippet"), str) and case["candidate_text"] in row["snippet"]
        for row in rows
    )
    before, after = observation.get("state_before") or {}, observation.get("state_after") or {}
    expected_hashes = {path: hashlib.sha256(text.encode()).hexdigest() for path, text in documents.items()}
    preparation = observation.get("preparation") or {}
    calls = observation.get("service_requests") or []
    expected_request = {"question": case["question"], "scope": "project", "lookup_queries": []}
    identity = observation.get("project_identity")
    diagnostics = observation.get("pipeline_diagnostics") or {}
    counts = diagnostics.get("observer_counts") or {}
    coverage = payload.get("covered_query_ids") or []
    missing = payload.get("missing_query_ids") or []
    valid_query_ids = (
        isinstance(coverage, list) and isinstance(missing, list)
        and all(isinstance(value, str) for value in coverage + missing)
        and len(coverage) == len(set(coverage)) and len(missing) == len(set(missing))
        and not (set(coverage) & set(missing))
        and set(coverage + missing) <= {"query-original"}
    )
    status = payload.get("status")
    context_shape = (
        payload.get("kind") == "docs_context" and status in {"ok", "insufficient_evidence"}
        and (status != "ok" or (
            payload.get("context_available") is True and payload.get("context_status") == "ready"
            and payload.get("support_status") == "retrieval_only"
            and payload.get("answer_policy") == "cite_only" and bool(rows)
        ))
        and (status != "insufficient_evidence" or (not rows and payload.get("context_available") is False))
    )
    token_estimate = payload.get("estimated_tokens")
    cost = {
        "source_count": len(rows),
        "public_utf8_bytes": len(canonical_json(payload).encode()),
        "reported_estimated_tokens": token_estimate,
    }
    checks = {
        "runtime_completed": observation.get("execution") == expected_execution and observation.get("error") is None,
        "request_identity": (
            observation.get("request") == expected_request
            and isinstance(identity, str) and re.fullmatch(r"local:[0-9a-f]{64}", identity) is not None
            and len(calls) == 1 and isinstance(calls[0], dict)
            and calls[0].get("question") == case["question"]
            and calls[0].get("scope") == "project" and calls[0].get("project_identity") == identity
        ),
        "one_public_retrieval_and_validation": (
            type(counts.get("retrieval_calls")) is int and counts["retrieval_calls"] == 1
            and type(counts.get("validation_calls")) is int and counts["validation_calls"] == 1
        ),
        "no_lookup_or_write_injection": (
            len(calls) == 1 and calls[0].get("lookup_queries") == []
            and all(calls[0].get(key) is False for key in ("prepare_project_docs", "allow_network", "force_refresh"))
        ),
        "finite_preparation": (
            preparation.get("expected_paths") == sorted(documents)
            and preparation.get("indexed_paths") == sorted(documents)
            and preparation.get("excluded_or_failed_paths") == [] and preparation.get("unexpected_paths") == []
        ),
        "read_only": (
            before == after and before.get("document_sha256") == expected_hashes
            and bool(before.get("generation"))
            and all(isinstance(before.get(key), str) and HEX64.fullmatch(before[key]) is not None
                    for key in ("store_sha256", "catalog_sha256"))
        ),
        "current_context_shape": bool(context_shape),
        "no_answer_or_edit_authority": not authority,
        "source_integrity": not integrity,
        "query_attribution": bool(valid_query_ids),
        "required_discovery": not case["require_discovery"] or discovered,
        "required_complete_fact": not case["require_support"] or fact_visible,
        "negative_source_precision": not case["negative_control"] or not rows,
        "output_cost_observed": type(token_estimate) is int and token_estimate >= 0,
    }
    return {
        "candidate_discovered": discovered, "complete_fact_visible": fact_visible,
        "reported_original_query_covered": "query-original" in coverage,
        "source_errors": integrity, "authority_errors": authority, "output_cost": cost,
        "checks": checks, "failed_checks": [key for key, value in checks.items() if value is not True],
        "passed": all(value is True for value in checks.values()),
    }


def _summary(rows: list[dict]) -> dict:
    return {
        "case_count": len(rows),
        "passed_count": sum(row["assessment"]["passed"] for row in rows),
        "failed_case_ids": [row["id"] for row in rows if not row["assessment"]["passed"]],
        "required_discovery": sum(row["historical_labels"]["require_discovery"] for row in rows),
        "required_discovery_passed": sum(
            row["historical_labels"]["require_discovery"] and row["assessment"]["checks"]["required_discovery"]
            and row["assessment"]["checks"]["source_integrity"] for row in rows),
        "required_complete_fact": sum(row["historical_labels"]["require_support"] for row in rows),
        "required_complete_fact_passed": sum(
            row["historical_labels"]["require_support"] and row["assessment"]["checks"]["required_complete_fact"]
            and row["assessment"]["checks"]["source_integrity"] for row in rows),
        "negative_control_count": sum(row["historical_labels"]["negative_control"] for row in rows),
        "negative_false_context": sum(
            row["historical_labels"]["negative_control"] and not row["assessment"]["checks"]["negative_source_precision"]
            for row in rows),
        "unauthorized_answer_or_edit_count": sum(not row["assessment"]["checks"]["no_answer_or_edit_authority"] for row in rows),
        "reported_original_query_covered": sum(row["assessment"]["reported_original_query_covered"] for row in rows),
        "complete_fact_visible": sum(row["assessment"]["complete_fact_visible"] for row in rows),
        "runtime_error_count": sum(row["observation"].get("error") is not None for row in rows),
        "output_source_count": sum(row["assessment"]["output_cost"]["source_count"] for row in rows),
        "output_public_utf8_bytes": sum(row["assessment"]["output_cost"]["public_utf8_bytes"] for row in rows),
    }


def _case_row(case: dict, observation: dict) -> dict:
    return {
        "id": case["id"], "family": case["family"], "question": case["question"],
        "candidate_source": case["candidate_source"],
        "candidate_text_sha256": hashlib.sha256(case["candidate_text"].encode()).hexdigest(),
        "historical_labels": {key: case[key] for key in ("require_discovery", "require_support", "negative_control")},
        "observation": observation, "assessment": score_observation(case, observation),
    }


def derive_from_paths(*, repo_root: Path, protocol_path: Path, planner_path: Path | None = None) -> dict:
    protocol = load_json(protocol_path)
    _validate_protocol(protocol)
    if protocol != load_protocol():
        raise ValueError("P1.4 input differs from the frozen repository corpus")
    rows = []
    with TemporaryDirectory(prefix="docatlas-p14-") as temporary:
        for case in protocol["cases"]:
            try:
                observation = capture_source_read(
                    {case["candidate_source"]: case["candidate_text"]},
                    case["question"], Path(temporary) / case["id"],
                )
            except Exception as exc:
                # A failed setup is a recorded failure, never a synthetic empty
                # retrieval or an omitted case. Tracebacks remain in CI stderr.
                import traceback
                traceback.print_exc()
                observation = {
                    "execution": "public_fixture_runtime", "error": {"type": type(exc).__name__},
                    "public_payload": {}, "bindings": {},
                }
            rows.append(_case_row(case, observation))
    summary = _summary(rows)
    try:
        runtime = build_runtime_manifest(repo_root)
        runtime_error = None
    except ValueError as exc:
        runtime, runtime_error = None, str(exc)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
    report = {
        "schema_version": SCHEMA_VERSION, "protocol": REPORT_PROTOCOL, "code_commit": commit,
        "source_identities": {
            "frozen_protocol_sha256": sha256_json(protocol),
            "migration_sha256": sha256_json(load_json(ROOT / "paraphrase_contract_migration.json")),
            "runtime": runtime, "runtime_error": runtime_error,
        },
        "summary": summary,
        "families": {family: _summary([row for row in rows if row["family"] == family]) for family in FAMILIES},
        "cases": rows,
        "passed": summary["passed_count"] == 14 and runtime_error is None,
        "claim_boundary": {
            "current_public_fixture_reads": True, "frozen_questions_and_facts_changed": False,
            "answer_or_edit_permission": False, "autonomous_agent_truth_proven": False,
            "installed_client_delivery_proven": False, "historical_report_resealed": False,
            "reported_coverage_is_not_independent_answer_proof": True,
            "output_cost_policy": "measure_and_minimize_without_fixed_output_ceiling",
        },
    }
    return report


def verify_report(report: dict) -> None:
    protocol = load_protocol()
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != REPORT_PROTOCOL:
        raise ValueError("P1.4 current report identity mismatch")
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    if report.get("code_commit") != current_commit:
        raise ValueError("P1.4 commit identity differs from current checkout")
    rows = report.get("cases")
    if not isinstance(rows, list) or [row.get("id") for row in rows if isinstance(row, dict)] != [case["id"] for case in protocol["cases"]]:
        raise ValueError("P1.4 frozen case roster drift")
    for case, row in zip(protocol["cases"], rows):
        if not isinstance(row.get("observation"), dict):
            raise ValueError("P1.4 observation is malformed")
        if row != _case_row(case, row["observation"]):
            raise ValueError(f"P1.4 source/fact assessment or frozen case identity drift: {case['id']}")
        source_paths = [source.get("path_or_url") for source in (row["observation"].get("public_payload") or {}).get("sources") or () if isinstance(source, dict)]
        if ABSOLUTE_PATH_RE.search(canonical_json(source_paths)):
            raise ValueError("P1.4 report contains an absolute local source path")
    summary = _summary(rows)
    if report.get("summary") != summary or report.get("families") != {
        family: _summary([row for row in rows if row["family"] == family]) for family in FAMILIES
    }:
        raise ValueError("P1.4 report summary or family metrics drift")
    identities = report.get("source_identities") or {}
    if identities.get("frozen_protocol_sha256") != FROZEN_PROTOCOL_SHA256:
        raise ValueError("P1.4 frozen protocol binding drift")
    if identities.get("migration_sha256") != sha256_json(load_json(ROOT / "paraphrase_contract_migration.json")):
        raise ValueError("P1.4 migration binding drift")
    if identities.get("runtime_error") is None:
        verify_runtime_manifest(identities.get("runtime"), REPO_ROOT)
    elif identities.get("runtime") is not None or not isinstance(identities["runtime_error"], str):
        raise ValueError("P1.4 inconsistent runtime error")
    passed = summary["passed_count"] == 14 and identities.get("runtime_error") is None
    if report.get("passed") is not passed:
        raise ValueError("P1.4 gate decision drift")
    expected_boundary = {
        "current_public_fixture_reads": True, "frozen_questions_and_facts_changed": False,
        "answer_or_edit_permission": False, "autonomous_agent_truth_proven": False,
        "installed_client_delivery_proven": False, "historical_report_resealed": False,
        "reported_coverage_is_not_independent_answer_proof": True,
        "output_cost_policy": "measure_and_minimize_without_fixed_output_ceiling",
    }
    if report.get("claim_boundary") != expected_boundary:
        raise ValueError("P1.4 report overclaims its evidence boundary")


def render_markdown(report: dict) -> str:
    verify_report(report)
    lines = ["# P1.4 current original-question retrieval", "",
             "Frozen facts are checked in real public fixture reads; sources grant no answer or edit permission.",
             "", "| Family | Cases | Passed | Required discovery | Required complete fact |",
             "|---|---:|---:|---:|---:|"]
    for family, values in report["families"].items():
        lines.append(f"| {family} | {values['case_count']} | {values['passed_count']} | "
                     f"{values['required_discovery_passed']}/{values['required_discovery']} | "
                     f"{values['required_complete_fact_passed']}/{values['required_complete_fact']} |")
    lines += ["", f"Current fixture gate: {'PASS' if report['passed'] else 'FAIL'}.",
              "Installed-client delivery and autonomous model behavior require their separate gates.", ""]
    return "\n".join(lines)


validate_report = verify_report
