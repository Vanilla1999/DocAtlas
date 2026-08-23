from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


PROTOCOL = "p1-agent-truth-closure-v1"
SCHEMA_VERSION = 1
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)",
)
REQUIRED_INSTALLED_TRANSPORT_PATHS = (
    ".github/workflows/installed-mcp-agent-benchmark.yml",
    "eval/agent_developer_v1/installed_mcp_benchmark.py",
    "eval/agent_developer_v1/installed_mcp_contract.py",
    "eval/agent_developer_v1/installed_mcp_report.py",
    "scripts/installed_mcp_contract_self_test.py",
    "scripts/run_installed_mcp_agent_benchmark.py",
    "scripts/verify_installed_mcp_agent_report.py",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def git_blob_sha(path: Path, *, repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "hash-object", str(path)],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"unable to hash {path}: {completed.stderr.strip()[:200]}")
    value = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"invalid Git blob identity: {value!r}")
    return value


def _installed_reports(repo_root: Path) -> list[dict[str, Any]]:
    results = repo_root / "eval" / "agent_developer_v1" / "results"
    reports: list[dict[str, Any]] = []
    if not results.is_dir():
        return reports
    for path in sorted(results.glob("*.json")):
        try:
            payload = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        protocol = str(payload.get("protocol") or "").casefold()
        if "installed" in protocol and "mcp" in protocol:
            reports.append(payload)
    return reports


def _is_replay_green(report: dict[str, Any]) -> bool:
    artifact = report.get("artifact")
    artifact = artifact if isinstance(artifact, dict) else {}
    planner = report.get("planner")
    planner = planner if isinstance(planner, dict) else {}
    mode = str(
        report.get("planner_mode")
        or planner.get("mode")
        or report.get("provider_id")
        or ""
    ).casefold()
    return (
        int(report.get("task_count") or 0) == 11
        and int(report.get("executed_task_count") or report.get("task_count") or 0) == 11
        and int(report.get("passed_tasks") or 0) == 11
        and artifact.get("editable_install") is not True
        and any(token in mode for token in ("replay", "reviewer", "scripted"))
    )


def _is_complete_autonomous_run(report: dict[str, Any]) -> bool:
    provider = report.get("provider")
    provider = provider if isinstance(provider, dict) else {}
    planner = report.get("planner")
    planner = planner if isinstance(planner, dict) else {}
    mode = str(
        report.get("planner_mode")
        or planner.get("mode")
        or report.get("provider_id")
        or ""
    ).casefold()
    real_model = bool(
        report.get("real_model")
        or provider.get("real_model")
        or provider.get("request_ids")
    )
    return (
        "autonomous" in mode
        and real_model
        and int(report.get("task_count") or 0) == 11
        and int(report.get("executed_task_count") or 0) == 11
        and not report.get("infrastructure_errors")
    )


def _assert_input_evidence(
    p12: dict[str, Any],
    p13: dict[str, Any],
    p14: dict[str, Any],
    p15: dict[str, Any],
    p16: dict[str, Any],
) -> None:
    if p12.get("protocol") != "agent-developer-first-divergence-v1":
        raise ValueError("P1.2 evidence protocol mismatch")
    p12_summary = p12.get("summary")
    if not isinstance(p12_summary, dict) or p12_summary.get("task_count") != 11:
        raise ValueError("P1.2 evidence must cover exactly eleven tasks")
    if p12_summary.get("false_supported") != 0 or p12_summary.get("forbidden_source_contamination") != 0:
        raise ValueError("P1.2 safety evidence is not clean")

    if p13.get("protocol") != "agent-contract-v2-ablation-v1":
        raise ValueError("P1.3 evidence protocol mismatch")
    p13_decision = p13.get("decision")
    if not isinstance(p13_decision, dict):
        raise ValueError("P1.3 evidence omitted decision")
    if p13_decision.get("accepted_public_contract_changes") != []:
        raise ValueError("P1.3 accepted an unproven public contract change")
    if p13_decision.get("public_agent_contract_v2") != "no_change":
        raise ValueError("P1.3 public contract decision drifted")

    if p14.get("protocol") != "paraphrase-proofability-report-v1":
        raise ValueError("P1.4 evidence protocol mismatch")
    p14_summary = p14.get("summary")
    p14_decision = p14.get("decision")
    if not isinstance(p14_summary, dict) or not isinstance(p14_decision, dict):
        raise ValueError("P1.4 evidence is incomplete")
    if p14_summary.get("false_supported_negative_controls") != 0:
        raise ValueError("P1.4 contains false support")
    if p14_decision.get("core_exact_proofability") not in {"accepted", "rejected"}:
        raise ValueError("P1.4 decision is invalid")

    if p15.get("protocol") != "mixed-evidence-provenance-report-v1":
        raise ValueError("P1.5 evidence protocol mismatch")
    p15_summary = p15.get("summary")
    p15_decision = p15.get("decision")
    if not isinstance(p15_summary, dict) or not isinstance(p15_decision, dict):
        raise ValueError("P1.5 evidence is incomplete")
    if p15_summary.get("mismatches") != [] or p15_summary.get("advisory_assignments") != []:
        raise ValueError("P1.5 claim-local provenance is not clean")
    if p15_decision.get("claim_local_provenance") != "accepted":
        raise ValueError("P1.5 provenance decision is not accepted")

    if p16.get("protocol") != "evidence-is-data-report-v1":
        raise ValueError("P1.6 evidence protocol mismatch")
    p16_summary = p16.get("summary")
    p16_decision = p16.get("decision")
    if not isinstance(p16_summary, dict) or not isinstance(p16_decision, dict):
        raise ValueError("P1.6 evidence is incomplete")
    if p16_summary.get("mismatches") != [] or p16_summary.get("content_control_failures") != []:
        raise ValueError("P1.6 hostile-content boundary is not clean")
    if p16_decision.get("evidence_is_data_boundary") != "accepted":
        raise ValueError("P1.6 evidence-is-data boundary is not accepted")


def derive_closure(
    *,
    repo_root: Path,
    p12: dict[str, Any],
    p13: dict[str, Any],
    p14: dict[str, Any],
    p15: dict[str, Any],
    p16: dict[str, Any],
    source_paths: dict[str, Path],
) -> dict[str, Any]:
    _assert_input_evidence(p12, p13, p14, p15, p16)
    required_paths = [repo_root / value for value in REQUIRED_INSTALLED_TRANSPORT_PATHS]
    if not all(path.is_file() for path in required_paths):
        raise ValueError("P1.1 installed-MCP transport contract is missing")

    reports = _installed_reports(repo_root)
    replay_green = any(_is_replay_green(report) for report in reports)
    autonomous_complete = any(_is_complete_autonomous_run(report) for report in reports)
    source_identities = {
        key: {
            "path": path.relative_to(repo_root).as_posix(),
            "git_blob_sha1": git_blob_sha(path, repo_root=repo_root),
        }
        for key, path in sorted(source_paths.items())
    }
    installed_identities = [
        {
            "path": path.relative_to(repo_root).as_posix(),
            "git_blob_sha1": git_blob_sha(path, repo_root=repo_root),
        }
        for path in required_paths
    ]

    p12_summary = p12["summary"]
    p13_decision = p13["decision"]
    p14_summary = p14["summary"]
    p14_decision = p14["decision"]
    p15_summary = p15["summary"]
    p15_decision = p15["decision"]
    p16_summary = p16["summary"]

    scorecard = [
        {
            "id": "P1.1",
            "title": "Installed-MCP live benchmark harness",
            "execution_status": "closed",
            "evidence_status": "green_transport_autonomy_unproven",
            "facts": {
                "installed_transport_file_count": len(installed_identities),
                "installed_transport_contract_green": True,
                "reviewer_replay_11_of_11_committed": replay_green,
                "complete_fresh_autonomous_run": autonomous_complete,
            },
            "decision": (
                "The installed wheel/CLI/MCP stdio, schema-repair, attribution and privacy "
                "measurement boundary is proven. No committed complete fresh same-model "
                "autonomous 11-task result is present."
            ),
        },
        {
            "id": "P1.2",
            "title": "0/11 first-divergence atlas",
            "execution_status": "closed",
            "evidence_status": "green_historical_diagnosis",
            "facts": {
                "task_count": p12_summary["task_count"],
                "failure_class_counts": p12_summary["failure_class_counts"],
                "false_supported": p12_summary["false_supported"],
                "forbidden_source_contamination": p12_summary["forbidden_source_contamination"],
            },
            "decision": "Three first-divergence classes are frozen; API changes remain gated by ablation evidence.",
        },
        {
            "id": "P1.3",
            "title": "Agent Contract v2 ablation",
            "execution_status": "closed",
            "evidence_status": "green_decision_no_runtime_change",
            "facts": {
                "accepted_public_contract_changes": p13_decision["accepted_public_contract_changes"],
                "accepted_for_next_live_ablation": p13_decision["accepted_for_next_live_ablation"],
                "public_agent_contract_v2": p13_decision["public_agent_contract_v2"],
            },
            "decision": "working_path duplication and continuation token are rejected; host normalization remains only a future live ablation.",
        },
        {
            "id": "P1.4",
            "title": "Paraphrase/proofability robustness",
            "execution_status": "closed",
            "evidence_status": "provider_free_measured_" + str(p14_decision["core_exact_proofability"]),
            "facts": p14_summary,
            "decision": (
                "Candidate discovery is measured separately from support; "
                "core_exact_proofability=" + str(p14_decision["core_exact_proofability"])
                + "; negative false support remains zero."
            ),
        },
        {
            "id": "P1.5",
            "title": "Mixed-evidence provenance",
            "execution_status": "closed",
            "evidence_status": "provider_free_measured_" + str(p15_decision["claim_local_provenance"]),
            "facts": p15_summary,
            "decision": "Protected claims retain allowed-role provenance; auxiliary generic assignments remain separately audited.",
        },
        {
            "id": "P1.6",
            "title": "Evidence-is-data adversarial boundary",
            "execution_status": "closed",
            "evidence_status": "green_provider_free_and_production_gates",
            "facts": p16_summary,
            "decision": "Hostile document content cannot control tools, lifecycle, authority, credentials or support state.",
        },
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "phase": "P1_AGENT_TRUTH",
        "execution_status": "CLOSED",
        "outcome": "AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN",
        "product_maturity": "Beta",
        "claim_boundary": {
            "p1_work_items_complete": True,
            "autonomous_agent_truth_proven": False,
            "real_coding_outcome_improvement_proven": False,
            "public_release_truth_closed": False,
            "stable_claim_allowed": False,
        },
        "source_identities": source_identities,
        "p1_1_installed_evidence_identities": installed_identities,
        "scorecard": scorecard,
        "decision": {
            "accepted_production_changes": [],
            "deferred_hypothesis": "host_selector_normalization_live_ablation",
            "public_api_freeze": True,
            "p2_allowed_scope": (
                "methodology, positive controls and real-outcome measurement only; "
                "P1 is not positive proof of autonomous agent efficacy"
            ),
            "next_step": "P2.1 repair Task 23 methodology",
        },
    }


def verify_closure(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1 closure identity mismatch")
    if report.get("execution_status") != "CLOSED":
        raise ValueError("P1 work-item execution is not closed")
    if report.get("outcome") != "AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN":
        raise ValueError("P1 closure falsifies the autonomous Agent Truth outcome")
    if report.get("product_maturity") != "Beta":
        raise ValueError("P1 closure improperly promotes product maturity")
    rows = report.get("scorecard")
    if not isinstance(rows, list) or [row.get("id") for row in rows] != [
        "P1.1", "P1.2", "P1.3", "P1.4", "P1.5", "P1.6"
    ]:
        raise ValueError("P1 closure scorecard is incomplete or reordered")
    if any(row.get("execution_status") != "closed" for row in rows):
        raise ValueError("P1 closure contains an open work item")
    p11 = rows[0].get("facts")
    if not isinstance(p11, dict) or p11.get("installed_transport_contract_green") is not True:
        raise ValueError("P1.1 installed transport proof is missing")
    if p11.get("installed_transport_file_count") != len(REQUIRED_INSTALLED_TRANSPORT_PATHS):
        raise ValueError("P1.1 installed transport identity set is incomplete")
    if p11.get("complete_fresh_autonomous_run") is not False:
        raise ValueError("P1 closure hides or invents the fresh autonomous-run boundary")
    if p11.get("reviewer_replay_11_of_11_committed") not in {True, False}:
        raise ValueError("P1 closure omitted the committed replay-evidence boundary")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict) or boundary.get("p1_work_items_complete") is not True:
        raise ValueError("P1 closure omitted or did not finish the worklist")
    for key in (
        "autonomous_agent_truth_proven",
        "real_coding_outcome_improvement_proven",
        "public_release_truth_closed",
        "stable_claim_allowed",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"P1 closure overclaims {key}")
    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("P1 closure omitted decision")
    if decision.get("accepted_production_changes") != []:
        raise ValueError("P1 closure accepted an unproven production change")
    if decision.get("public_api_freeze") is not True:
        raise ValueError("P1 closure lost the public API freeze")
    identities = report.get("p1_1_installed_evidence_identities")
    if not isinstance(identities, list) or [row.get("path") for row in identities] != list(REQUIRED_INSTALLED_TRANSPORT_PATHS):
        raise ValueError("P1 closure installed evidence identities are incomplete or reordered")
    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("P1 closure contains an absolute local path")


def derive_from_paths(*, repo_root: Path, root: Path) -> dict[str, Any]:
    paths = {
        "p1_2": root / "results" / "first-divergence-atlas.json",
        "p1_3": root / "results" / "contract-v2-ablation.json",
        "p1_4": root / "results" / "paraphrase-proofability.json",
        "p1_5": root / "results" / "mixed-evidence-provenance.json",
        "p1_6": root / "results" / "evidence-is-data.json",
    }
    return derive_closure(
        repo_root=repo_root,
        p12=load_json(paths["p1_2"]),
        p13=load_json(paths["p1_3"]),
        p14=load_json(paths["p1_4"]),
        p15=load_json(paths["p1_5"]),
        p16=load_json(paths["p1_6"]),
        source_paths=paths,
    )
