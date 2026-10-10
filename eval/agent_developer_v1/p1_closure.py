from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from eval.agent_developer_v1.evidence_is_data import current_code_commit


PROTOCOL = "p1-agent-truth-current-closure-v2"
SCHEMA_VERSION = 2
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


ROOT = Path(__file__).resolve().parents[2]
CURRENT_IDS = ("p1_4", "p1_5", "p1_6")
REQUIRED_GATES = (
    "dependencies", "first_divergence", "contract_ablation",
    "p14_quality", "p14_oracle", "p15_quality", "p15_oracle",
    "p16_quality", "p16_oracle", "adversarial", "adversarial_mutation", "syntax",
)
BOUNDARY = {
    "current_fixture_closure_only": True,
    "p1_work_items_complete": False,
    "autonomous_agent_truth_proven": False,
    "real_coding_outcome_improvement_proven": False,
    "public_release_truth_closed": False,
    "installed_client_delivery_proven": False,
    "stable_claim_allowed": False,
    "historical_reports_are_current_runtime_proof": False,
}
DECISION = {
    "accepted_production_changes": [],
    "deferred_hypothesis": "host_selector_normalization_live_ablation",
    "public_api_freeze": True,
    "required_external_acceptance": "required CI and installed/client gates on the final SHA",
    "next_step": "Resolve every current quality or gate failure before final acceptance.",
}


def _error(exc: Exception, *, stage: str) -> dict:
    # Child runners retain detailed diagnostics. This aggregate stores no raw
    # document text, credential markers, or private filesystem paths.
    return {"stage": stage, "type": type(exc).__name__,
            "message_sha256": hashlib.sha256(str(exc).encode("utf-8")).hexdigest()}


def _history(repo_root: Path, root: Path) -> dict:
    paths = {
        "p1_2": root / "results/first-divergence-atlas.json",
        "p1_3": root / "results/contract-v2-ablation.json",
        "p1_4": root / "results/paraphrase-proofability.json",
        "p1_5": root / "results/mixed-evidence-provenance.json",
        "p1_6": root / "results/evidence-is-data.json",
    }
    reports, identities, errors = {}, {}, []
    for name, path in paths.items():
        try:
            reports[name] = load_json(path)
            identities[name] = {
                "path": path.relative_to(repo_root).as_posix(),
                "git_blob_sha1": git_blob_sha(path, repo_root=repo_root),
            }
        except Exception as exc:
            errors.append(_error(exc, stage="historical_" + name))
    try:
        _assert_input_evidence(*(reports[name] for name in paths))
    except Exception as exc:
        errors.append(_error(exc, stage="historical_contract"))
    installed = []
    installed_errors = []
    for relative in REQUIRED_INSTALLED_TRANSPORT_PATHS:
        try:
            blob = git_blob_sha(repo_root / relative, repo_root=repo_root)
        except Exception as exc:
            blob = None
            installed_errors.append(_error(exc, stage="installed_harness_identity"))
        installed.append({"path": relative, "git_blob_sha1": blob})
    try:
        installed_reports = _installed_reports(repo_root)
        replay_green = any(_is_replay_green(report) for report in installed_reports)
        autonomous_complete = any(_is_complete_autonomous_run(report) for report in installed_reports)
        if autonomous_complete:
            # Preserve the previous negative-boundary guard; new autonomous
            # evidence requires separate review, never automatic promotion.
            raise ValueError("unreviewed autonomous-run evidence changes the historical boundary")
    except Exception as exc:
        errors.append(_error(exc, stage="historical_installed_boundary"))
        replay_green, autonomous_complete = None, None
    return {
        "archive_guards_valid": not errors,
        "installed_harness_available": not installed_errors,
        "source_identities": identities, "installed_source_identities": installed,
        "errors": errors + installed_errors,
        "reviewer_replay_11_of_11_committed": replay_green,
        "complete_fresh_autonomous_run": autonomous_complete,
        "summaries": {name: deepcopy(report.get("summary")) for name, report in reports.items()},
        "decisions": {name: deepcopy(report.get("decision")) for name, report in reports.items()},
    }


def _current_slice(name: str, path: Path | None, repo_root: Path, commit: str) -> tuple[dict, dict | None]:
    row = {
        "id": name.replace("p1_", "P1."), "execution_status": "FAIL",
        "report_sha256": None, "code_commit": None, "protocol": None,
        "integrity_valid": False, "quality_passed": False,
        "summary": None, "families": None, "case_checks": [],
        "runtime_manifest_sha256": None, "error": None,
    }
    try:
        if path is None:
            raise ValueError("required current report is missing")
        report = load_json(path)
        row["report_sha256"] = sha256_json(report)
        if report.get("code_commit") != commit:
            raise ValueError("current evidence uses a different or missing checkout commit")
        if name == "p1_4":
            from eval.agent_developer_v1.paraphrase_robustness import verify_report
            verify_report(report)
        elif name == "p1_5":
            from eval.agent_developer_v1.mixed_provenance import verify_report
            verify_report(report)
        elif name == "p1_6":
            from eval.agent_developer_v1.evidence_is_data import verify_report
            verify_report(report, repo_root=repo_root, require_quality=False)
        else:
            raise ValueError("unexpected current report slot")
        # The child verifiers recompute every original case and summary before
        # these body-free results are copied; honest quality failures are valid.
        result_key = "result" if name == "p1_6" else "assessment"
        row["case_checks"] = [
            {"id": case["id"], "passed": case[result_key]["passed"],
             "checks": deepcopy(case[result_key]["checks"])}
            for case in report["cases"]
        ]
        quality = (report["summary"]["passed_cases"] == 6
                   and report["summary"]["runtime_errors"] == 0
                   if name == "p1_6" else report["passed"] is True)
        if name == "p1_6" and quality:
            verify_report(report, repo_root=repo_root, require_quality=True)
        identities = report["source_identities"]
        runtime = identities.get("public_delivery_runtime" if name == "p1_6" else "runtime")
        row.update({
            "execution_status": "PASS" if quality else "FAIL",
            "code_commit": report["code_commit"], "protocol": report["protocol"],
            "integrity_valid": True, "quality_passed": quality,
            "summary": deepcopy(report["summary"]),
            "families": deepcopy(report.get("families")),
            "runtime_manifest_sha256": runtime.get("sha256") if isinstance(runtime, dict) else None,
        })
        return row, runtime
    except Exception as exc:
        row["error"] = _error(exc, stage=name + "_current_verifier")
        return row, None


def _runtime_union(manifests: list[dict | None]) -> dict:
    files = {}
    try:
        for manifest in manifests:
            if not isinstance(manifest, dict):
                raise ValueError("a current runtime manifest is missing")
            for row in manifest["files"]:
                path, digest = row["path"], row["sha256"]
                if path in files and files[path] != digest:
                    raise ValueError("current runtimes disagree about an imported source")
                files[path] = digest
        # Each child verifier already checks every entry against this checkout.
        # Different processes may import different supersets of source modules.
        rows = [{"path": path, "sha256": digest} for path, digest in sorted(files.items())]
        return {"consistent": True, "file_count": len(rows), "sha256": sha256_json(rows), "error": None}
    except Exception as exc:
        return {"consistent": False, "file_count": 0, "sha256": None,
                "error": _error(exc, stage="current_runtime_union")}


def _gate_evidence(gate_outcomes: dict | None, commit: str) -> dict:
    receipt = gate_outcomes if isinstance(gate_outcomes, dict) else {}
    supplied = receipt.get("outcomes")
    supplied = supplied if isinstance(supplied, dict) else {}
    valid_states = {"success", "failure", "cancelled", "skipped"}
    binding_valid = (
        set(receipt) == {"schema_version", "code_commit", "run_id", "run_attempt", "outcomes"}
        and receipt.get("schema_version") == 1
        and receipt.get("code_commit") == commit
        and all(isinstance(receipt.get(key), str)
                and re.fullmatch(r"[1-9][0-9]*", receipt[key]) is not None
                for key in ("run_id", "run_attempt"))
    )
    inventory_valid = set(supplied) == set(REQUIRED_GATES) and all(
        isinstance(state, str) and state in valid_states for state in supplied.values()
    )
    rows = [
        {"id": name, "outcome": supplied.get(name)
         if isinstance(supplied.get(name), str) and supplied.get(name) in valid_states else "missing",
         "passed": supplied.get(name) == "success"}
        for name in REQUIRED_GATES
    ]
    return {
        "checkout_binding_valid": binding_valid, "inventory_valid": inventory_valid,
        "receipt": {key: receipt[key] for key in ("code_commit", "run_id", "run_attempt")}
        if binding_valid else None,
        "outcomes": rows,
        "passed": binding_valid and inventory_valid and all(row["passed"] for row in rows),
    }


def default_current_paths(root: Path) -> dict[str, Path]:
    if root.resolve() != ROOT / "eval/agent_developer_v1":
        raise ValueError("current report defaults belong to this checkout")
    from scripts.run_paraphrase_proofability_gate import DEFAULT_OUTPUT as p14_output
    from scripts.run_mixed_evidence_provenance_gate import DEFAULT_OUTPUT as p15_output
    from scripts.run_evidence_is_data_gate import DEFAULT_OUTPUT as p16_output
    return {"p1_4": p14_output, "p1_5": p15_output, "p1_6": p16_output}


def derive_from_paths(*, repo_root: Path, root: Path,
                      current_paths: dict[str, Path] | None = None,
                      gate_outcomes: dict | None = None) -> dict:
    repo_root, root = repo_root.resolve(), root.resolve()
    if repo_root != ROOT or root != ROOT / "eval/agent_developer_v1":
        raise ValueError("P1 closure must use the evaluator's current checkout")
    commit = current_code_commit(repo_root)
    paths = default_current_paths(root) if current_paths is None else current_paths
    history = _history(repo_root, root)
    current = [_current_slice(name, paths.get(name), repo_root, commit) for name in CURRENT_IDS]
    rows = [row for row, _ in current]
    runtime = _runtime_union([manifest for _, manifest in current])
    gates = _gate_evidence(gate_outcomes, commit)
    checks = {
        "historical_archive_guards": history["archive_guards_valid"],
        "installed_harness_identities": history["installed_harness_available"],
        "current_report_inventory": set(paths) == set(CURRENT_IDS),
        "current_report_integrity": all(row["integrity_valid"] for row in rows),
        "current_quality": all(row["quality_passed"] for row in rows),
        "current_runtime_consistency": runtime["consistent"],
        "required_gate_checkout": gates["checkout_binding_valid"],
        "required_gate_inventory": gates["inventory_valid"],
        "required_gates_succeeded": gates["passed"],
    }
    scorecard = [
        {
            "id": "P1.1", "execution_status": "HISTORICAL_CONTEXT",
            "facts": {
                "installed_harness_available": history["installed_harness_available"],
                "installed_transport_file_count": len(history["installed_source_identities"]),
                "reviewer_replay_11_of_11_committed": history["reviewer_replay_11_of_11_committed"],
                "complete_fresh_autonomous_run": history["complete_fresh_autonomous_run"],
                "current_installed_transport_proven": False,
            },
        },
        {"id": "P1.2", "execution_status": "HISTORICAL_CONTEXT",
         "facts": history["summaries"].get("p1_2")},
        {"id": "P1.3", "execution_status": "HISTORICAL_CONTEXT",
         "facts": history["decisions"].get("p1_3")},
        *rows,
    ]
    passed = all(value is True for value in checks.values())
    return {
        "schema_version": SCHEMA_VERSION, "protocol": PROTOCOL,
        "phase": "P1_AGENT_TRUTH", "code_commit": commit,
        "execution_status": "PASS" if passed else "FAIL", "passed": passed,
        "outcome": "AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN", "product_maturity": "Beta",
        "claim_boundary": deepcopy(BOUNDARY), "checks": checks,
        "historical_context": history, "scorecard": scorecard,
        "current_runtime_union": runtime, "required_gates": gates,
        "decision": deepcopy(DECISION),
    }


def verify_closure(report: dict, *, repo_root: Path = ROOT, root: Path | None = None,
                   current_paths: dict[str, Path] | None = None,
                   gate_outcomes: dict | None = None, require_quality: bool = True) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1 current closure identity mismatch")
    if report.get("product_maturity") != "Beta":
        raise ValueError("P1 closure improperly promotes product maturity")
    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("P1 closure contains an absolute local path")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P1 closure omitted the execution boundary")
    for name, expected in BOUNDARY.items():
        if boundary.get(name) is not expected:
            raise ValueError(f"P1 closure overclaims {name}")
    decision = report.get("decision")
    if not isinstance(decision, dict) or decision.get("accepted_production_changes") != []:
        raise ValueError("P1 closure accepted an unproven production change")
    rows = report.get("scorecard")
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
        or [row.get("id") for row in rows] != ["P1.1", "P1.2", "P1.3", "P1.4", "P1.5", "P1.6"]):
        raise ValueError("P1 closure scorecard is incomplete or reordered")
    expected = derive_from_paths(
        repo_root=repo_root, root=root or repo_root / "eval/agent_developer_v1",
        current_paths=current_paths, gate_outcomes=gate_outcomes,
    )
    if canonical_json(report) != canonical_json(expected):
        raise ValueError("P1 closure differs from current reports, gates, or derived checks")
    if require_quality and not expected["passed"]:
        failed = [name for name, passed in expected["checks"].items() if not passed]
        raise ValueError("P1 current closure failed: " + ", ".join(failed))
