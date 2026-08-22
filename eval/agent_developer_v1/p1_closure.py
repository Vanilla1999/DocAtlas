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


def _installed_mcp_files(repo_root: Path) -> list[Path]:
    candidates: set[Path] = set()
    for pattern in (
        ".github/workflows/*installed*mcp*.yml",
        "eval/**/*installed*mcp*",
        "scripts/*installed*mcp*.py",
    ):
        for path in repo_root.glob(pattern):
            if path.is_file() and "temp-" not in path.name:
                candidates.add(path)
    return sorted(candidates, key=lambda path: path.relative_to(repo_root).as_posix())


def _installed_reports(paths: list[Path]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix != ".json":
            continue
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
    mode = str(
        report.get("planner_mode")
        or (report.get("planner") or {}).get("mode")
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
    mode = str(
        report.get("planner_mode")
        or (report.get("planner") or {}).get("mode")
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
    installed_files = _installed_mcp_files(repo_root)
    reports = _installed_reports(installed_files)
    replay_green = any(_is_replay_green(report) for report in reports)
    autonomous_complete = any(_is_complete_autonomous_run(report) for report in reports)
    if not installed_files:
        raise ValueError("P1.1 installed-MCP implementation evidence is missing")

    source_identities = {
        key: {
            "path": path.relative_to(repo_root).as_posix(),
            "git_blob_sha1": git_blob_sha(path, repo_root=repo_root),
        }
        for key, path in sorted(source_paths.items())
    }
    p11_identities = [
        {
            "path": path.relative_to(repo_root).as_posix(),
            "git_blob_sha1": git_blob_sha(path, repo_root=repo_root),
        }
        for path in installed_files
    ]

    rows = [
        {
            "id": "P1.1",
            "title": "Installed-MCP live benchmark harness",
            "execution_status": "closed",
            "evidence_status": "green_transport_inconclusive_autonomy",
            "facts": {
                "installed_mcp_files": len(installed_files),
                "reviewer_replay_11_of_11": replay_green,
                "complete_fresh_autonomous_run": autonomous_complete,
            },
            "decision": (
                "The installed transport/harness boundary is proven. A complete fresh "
                "same-model autonomous 11-task run is not present and remains unproven."
            ),
        },
        {
            "id": "P1.2",
            "title": "0/11 first-divergence atlas",
            "execution_status": "closed",
            "evidence_status": "green_historical_diagnosis",
            "facts": p12["summary"],
            "decision": "Three first-divergence classes are frozen; API changes remain gated by ablation evidence.",
        },
        {
            "id": "P1.3",
            "title": "Agent Contract v2 ablation",
            "execution_status": "closed",
            "evidence_status": "green_decision_no_runtime_change",
            "facts": {
                "accepted_production_changes": p13["decision"]["accepted_production_changes"],
                "deferred_experiment": p13["decision"]["deferred_experiment"],
            },
            "decision": "working_path duplication and continuation token are rejected; conservative inference remains inconclusive.",
        },
        {
            "id": "P1.4",
            "title": "Paraphrase/proofability robustness",
            "execution_status": "closed",
            "evidence_status": "green_provider_free",
            "facts": p14["summary"],
            "decision": "Candidate discovery is measured separately from support; negative false support remains zero.",
        },
        {
            "id": "P1.5",
            "title": "Mixed-evidence provenance",
            "execution_status": "closed",
            "evidence_status": "green_provider_free",
            "facts": p15["summary"],
            "decision": "Protected claims are assigned only to allowed source roles under conflict.",
        },
        {
            "id": "P1.6",
            "title": "Evidence-is-data adversarial boundary",
            "execution_status": "closed",
            "evidence_status": "green_provider_free_and_production_gates",
            "facts": p16["summary"],
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
        "p1_1_installed_evidence_identities": p11_identities,
        "scorecard": rows,
        "decision": {
            "accepted_production_changes": [],
            "deferred_hypothesis": "conservative_server_owned_scope_inference",
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
    if not isinstance(p11, dict) or p11.get("reviewer_replay_11_of_11") is not True:
        raise ValueError("P1.1 installed replay proof is missing")
    if p11.get("complete_fresh_autonomous_run") is not False:
        raise ValueError("P1 closure hides or invents the fresh autonomous-run boundary")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P1 closure omitted claim boundary")
    if boundary.get("p1_work_items_complete") is not True:
        raise ValueError("P1 closure did not finish all work items")
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
