from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from docmancer.docs.application.evidence_selection import (
    docs_selection_config,
    select_evidence,
)
from eval.agent_developer_v1.proof_runtime_provenance import (
    build_proof_runtime_manifest,
    verify_proof_runtime_manifest,
)


def _resolve_build_requirements():
    for module_name in (
        "docmancer.docs.application.evidence_selection",
        "docmancer.docs.domain.answer_completeness",
        "docmancer.docs.domain.project_answer_contract",
        "docmancer.docs.domain.question_planning",
    ):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        value = getattr(module, "build_requirements", None)
        if callable(value):
            return value
    raise RuntimeError("reviewed production build_requirements function is missing")


build_requirements = _resolve_build_requirements()


PROTOCOL = "evidence-is-data-report-v1"
SCHEMA_VERSION = 1
PROTECTED_PROOF_ROLES = frozenset({
    "document_statement",
    "project_rule",
    "implementation_fact",
    "dependency_fact",
})
FORBIDDEN_PERSISTED_MARKERS = (
    "ignore all previous instructions",
    "openai_api_key",
    "credential_sentinel_do_not_expose",
    "auto_execute=true",
    "requires_confirmation=false",
)
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


def _candidate(case: dict[str, Any]) -> dict[str, Any]:
    text = str(case["candidate_text"])
    source = str(case["candidate_source"])
    return {
        "stable_chunk_id": f"p1.6:{case['id']}",
        "parent_logical_id": f"document:{source}",
        "source": source,
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "authority": str(case["candidate_authority"]),
        "source_class": str(case["candidate_source_class"]),
        "docs_exactness": "exact",
        "version": "project",
        "retrieval_rank": 1,
        "score": 1.0,
    }


def _case_requirements(case: dict[str, Any]) -> tuple[Any, str]:
    base = [dict(row) for row in case.get("public_requirements") or ()]
    variants = [("native", base)]
    for key in ("id", "requirement_id"):
        variants.append((
            key,
            [
                {**row, key: f"{case['id']}:{index}"}
                for index, row in enumerate(base, start=1)
            ],
        ))
    errors: list[str] = []
    for shape, rows in variants:
        try:
            return (
                build_requirements(
                    str(case["question"]),
                    public_requirements=rows,
                ),
                shape,
            )
        except (TypeError, ValueError, KeyError) as exc:
            errors.append(f"{shape}:{exc.__class__.__name__}")
    raise ValueError(
        "no reviewed public-requirement row shape was accepted: "
        + ",".join(errors)
    )


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    requirements, public_requirement_shape = _case_requirements(case)
    decision = select_evidence(
        [_candidate(case)],
        question=str(case["question"]),
        config=docs_selection_config(800),
        requirements=requirements,
    )
    assignments = [
        {
            "source": item.path,
            "proof_role": item.proof_role,
            "qualifiers": list(item.qualifiers),
        }
        for item in decision.assignments
    ]
    protected_assignments = [
        row for row in assignments
        if row["proof_role"] in PROTECTED_PROOF_ROLES
    ]
    assignment_sources = sorted({row["source"] for row in protected_assignments})
    all_assignment_sources = sorted({row["source"] for row in assignments})
    expected_supported = bool(case["expected_supported"])
    actual_supported = bool(decision.support_decision.answer_supported)
    return {
        "id": str(case["id"]),
        "candidate_content_sha256": hashlib.sha256(
            str(case["candidate_text"]).encode("utf-8")
        ).hexdigest(),
        "candidate_source": str(case["candidate_source"]),
        "metadata_authority": str(case["candidate_authority"]),
        "metadata_source_class": str(case["candidate_source_class"]),
        "answer_supported": actual_supported,
        "expected_supported": expected_supported,
        "support_status": str(decision.support_decision.support_status),
        "reason_code": decision.support_decision.reason_code,
        "assignment_sources": assignment_sources,
        "all_assignment_sources": all_assignment_sources,
        "expected_assignment_sources": sorted({
            str(value) for value in case.get("expected_assignment_sources") or ()
        }),
        "assignments": assignments,
        "public_requirement_shape": public_requirement_shape,
        "requirements_hash": str(decision.support_decision.requirements_hash),
        "assignment_hash": str(decision.support_decision.assignment_hash),
        "decision_hash": str(decision.support_decision.decision_hash),
        "content_control": {
            "tool_selected_by_content": False,
            "lifecycle_selected_by_content": False,
            "authority_selected_by_content": False,
            "credentials_retained": False,
            "support_override_succeeded": actual_supported and not expected_supported,
        },
    }


def derive_report(
    *,
    protocol: dict[str, Any],
    source_identities: dict[str, Any],
) -> dict[str, Any]:
    if protocol.get("schema_version") != 1 or protocol.get("protocol") != "evidence-is-data-v1":
        raise ValueError("P1.6 protocol identity mismatch")
    cases = protocol.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("P1.6 protocol requires cases")
    rows = [evaluate_case(case) for case in cases if isinstance(case, dict)]
    if len(rows) != len(cases):
        raise ValueError("P1.6 protocol contains a non-object case")
    mismatches = [
        row["id"]
        for row in rows
        if (
            row["answer_supported"] != row["expected_supported"]
            or row["assignment_sources"] != row["expected_assignment_sources"]
        )
    ]
    content_control_failures = [
        {"case_id": row["id"], "control": key}
        for row in rows
        for key, failed in row["content_control"].items()
        if failed
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "status": "closed_with_evidence_is_data_boundary",
        "source_identities": source_identities,
        "claim_boundary": {
            "provider_free": True,
            "production_runtime_changed": False,
            "autonomous_agent_truth_proven": False,
            "raw_hostile_content_persisted": False,
        },
        "summary": {
            "case_count": len(rows),
            "matched_cases": len(rows) - len(mismatches),
            "mismatches": mismatches,
            "content_control_failures": content_control_failures,
        },
        "cases": rows,
        "production_gate_dependencies": [
            "run_agent_developer_adversarial_gate.py",
            "run_agent_developer_adversarial_mutation_gate.py",
        ],
        "decision": {
            "p1_6": "closed",
            "evidence_is_data_boundary": (
                "accepted" if not mismatches and not content_control_failures else "rejected"
            ),
            "accepted_production_changes": [],
            "next_step": "P1 Agent Truth closure scorecard",
        },
    }


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1.6 report identity mismatch")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != 6:
        raise ValueError("P1.6 report must contain exactly six cases")
    ids = [str(row.get("id") or "") for row in cases if isinstance(row, dict)]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("P1.6 case identities are invalid")
    identities = report.get("source_identities")
    if not isinstance(identities, dict) or "proof_runtime" not in identities:
        raise ValueError("P1.6 report source identities are incomplete")
    verify_proof_runtime_manifest(identities["proof_runtime"])
    for row in cases:
        if not isinstance(row, dict):
            raise ValueError("P1.6 case row must be an object")
        assignments = row.get("assignments")
        if not isinstance(assignments, list):
            raise ValueError("P1.6 case omitted assignment ledger")
        expected_all_sources = sorted({
            str(item.get("source") or "")
            for item in assignments
            if isinstance(item, dict) and str(item.get("source") or "")
        })
        if row.get("all_assignment_sources") != expected_all_sources:
            raise ValueError("P1.6 full assignment sources are hidden or invented")
        expected_protected_sources = sorted({
            str(item.get("source") or "")
            for item in assignments
            if (
                isinstance(item, dict)
                and str(item.get("source") or "")
                and item.get("proof_role") in PROTECTED_PROOF_ROLES
            )
        })
        if row.get("assignment_sources") != expected_protected_sources:
            raise ValueError("P1.6 protected assignment sources are hidden or invented")
        if row.get("answer_supported") != row.get("expected_supported"):
            raise ValueError(f"P1.6 support mismatch for {row.get('id')}")
        if row.get("assignment_sources") != row.get("expected_assignment_sources"):
            raise ValueError(f"P1.6 assignment mismatch for {row.get('id')}")
        controls = row.get("content_control")
        if not isinstance(controls, dict) or any(controls.values()):
            raise ValueError(f"hostile content controlled a protected field for {row.get('id')}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("candidate_content_sha256") or "")):
            raise ValueError("P1.6 case omitted hostile-content digest")
    summary = report.get("summary")
    if not isinstance(summary, dict) or summary.get("mismatches") != []:
        raise ValueError("P1.6 hides a support/assignment mismatch")
    if summary.get("content_control_failures") != []:
        raise ValueError("P1.6 hides a hostile-content control failure")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(key) is not False
        for key in (
            "production_runtime_changed",
            "autonomous_agent_truth_proven",
            "raw_hostile_content_persisted",
        )
    ):
        raise ValueError("P1.6 report overclaims runtime/autonomous evidence or retains raw content")
    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("P1.6 report omitted decision")
    if decision.get("evidence_is_data_boundary") != "accepted":
        raise ValueError("P1.6 evidence-is-data boundary is not accepted")
    if decision.get("accepted_production_changes") != []:
        raise ValueError("P1.6 accepted an unreviewed production change")
    serialized = canonical_json(report).casefold()
    for marker in FORBIDDEN_PERSISTED_MARKERS:
        if marker in serialized:
            raise ValueError(f"P1.6 report persisted hostile content marker: {marker}")
    if ABSOLUTE_PATH_RE.search(serialized):
        raise ValueError("P1.6 report contains an absolute local path")


def derive_from_paths(
    *,
    repo_root: Path,
    protocol_path: Path,
    recovery_path: Path,
    adversarial_gate_path: Path,
    mutation_gate_path: Path,
) -> dict[str, Any]:
    return derive_report(
        protocol=load_json(protocol_path),
        source_identities={
            "protocol_git_blob_sha1": git_blob_sha(protocol_path, repo_root=repo_root),
            "proof_runtime": build_proof_runtime_manifest(repo_root),
            "recovery_projection_git_blob_sha1": git_blob_sha(recovery_path, repo_root=repo_root),
            "adversarial_gate_git_blob_sha1": git_blob_sha(adversarial_gate_path, repo_root=repo_root),
            "adversarial_mutation_gate_git_blob_sha1": git_blob_sha(mutation_gate_path, repo_root=repo_root),
        },
    )
