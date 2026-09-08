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


PROTOCOL = "mixed-evidence-provenance-report-v1"
SCHEMA_VERSION = 1
PROTECTED_PROOF_ROLES = frozenset({
    "document_statement",
    "project_rule",
    "implementation_fact",
    "dependency_fact",
})
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


def _candidate(row: dict[str, Any]) -> dict[str, Any]:
    text = str(row["text"])
    source = str(row["source"])
    return {
        "stable_chunk_id": str(row["id"]),
        "parent_logical_id": f"document:{source}",
        "source": source,
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "authority": str(row["authority"]),
        "source_class": str(row["source_class"]),
        "docs_exactness": "exact",
        "version": "8.2.3" if row["source_class"] == "dependency_docs" else "project",
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
                    required_evidence_paths=[
                        str(value)
                        for value in case.get("required_evidence_paths") or ()
                    ],
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
        [_candidate(row) for row in case.get("candidates") or ()],
        question=str(case["question"]),
        config=docs_selection_config(1200),
        requirements=requirements,
    )
    assignments = [
        {
            "requirement_id": item.requirement_id,
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
    # Query-derived generic_fact requirements may retain a useful candidate in
    # an overall fail-closed result. P1.5 is specifically about whether each
    # protected claim is assigned to an allowed source role, so the acceptance
    # comparison must not conflate those auxiliary generic assignments with a
    # project-rule, implementation, dependency, or path-bound statement proof.
    assignment_sources = sorted({
        row["source"] for row in protected_assignments
    })
    all_assignment_sources = sorted({row["source"] for row in assignments})
    return {
        "id": str(case["id"]),
        "answer_supported": bool(decision.support_decision.answer_supported),
        "support_status": str(decision.support_decision.support_status),
        "reason_code": decision.support_decision.reason_code,
        "expected_supported": bool(case["expected_supported"]),
        "expected_assignment_sources": sorted({
            str(value) for value in case.get("expected_assignment_sources") or ()
        }),
        "assignment_sources": assignment_sources,
        "all_assignment_sources": all_assignment_sources,
        "assignments": assignments,
        "selected_sources": sorted({
            str(item.path_or_url) for item in decision.selected_candidates
        }),
        "public_requirement_shape": public_requirement_shape,
        "requirements_hash": str(decision.support_decision.requirements_hash),
        "assignment_hash": str(decision.support_decision.assignment_hash),
        "decision_hash": str(decision.support_decision.decision_hash),
    }


def derive_report(
    *,
    protocol: dict[str, Any],
    source_identities: dict[str, Any],
) -> dict[str, Any]:
    if protocol.get("schema_version") != 1 or protocol.get("protocol") != "mixed-evidence-provenance-v1":
        raise ValueError("P1.5 protocol identity mismatch")
    cases = protocol.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("P1.5 protocol requires cases")
    rows = [evaluate_case(case) for case in cases if isinstance(case, dict)]
    if len(rows) != len(cases):
        raise ValueError("P1.5 protocol contains a non-object case")
    mismatches = [
        row["id"]
        for row in rows
        if (
            row["answer_supported"] != row["expected_supported"]
            or row["assignment_sources"] != row["expected_assignment_sources"]
        )
    ]
    advisory_assignments = [
        {"case_id": row["id"], "source": source}
        for row in rows
        for source in row["assignment_sources"]
        if "advisory.example" in source or "blog.example" in source
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "status": "closed_with_claim_local_provenance",
        "source_identities": source_identities,
        "claim_boundary": {
            "provider_free": True,
            "production_runtime_changed": False,
            "autonomous_agent_truth_proven": False,
        },
        "summary": {
            "case_count": len(rows),
            "matched_cases": len(rows) - len(mismatches),
            "mismatches": mismatches,
            "advisory_assignments": advisory_assignments,
        },
        "cases": rows,
        "decision": {
            "p1_5": "closed",
            "claim_local_provenance": (
                "accepted" if not mismatches and not advisory_assignments else "rejected"
            ),
            "accepted_production_changes": [],
            "next_step": "P1.6 evidence-is-data adversarial gate",
        },
    }


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P1.5 report identity mismatch")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != 7:
        raise ValueError("P1.5 report must contain exactly seven cases")
    ids = [str(row.get("id") or "") for row in cases if isinstance(row, dict)]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("P1.5 case identities are invalid")
    identities = report.get("source_identities")
    if not isinstance(identities, dict) or "proof_runtime" not in identities:
        raise ValueError("P1.5 report source identities are incomplete")
    verify_proof_runtime_manifest(identities["proof_runtime"])
    for row in cases:
        if not isinstance(row, dict):
            raise ValueError("P1.5 case row must be an object")
        if not str(row.get("requirements_hash") or ""):
            raise ValueError("P1.5 case omitted requirements identity")
        if not str(row.get("assignment_hash") or ""):
            raise ValueError("P1.5 case omitted assignment identity")
        if not str(row.get("decision_hash") or ""):
            raise ValueError("P1.5 case omitted decision identity")
        assignments = row.get("assignments")
        if not isinstance(assignments, list):
            raise ValueError("P1.5 case omitted assignment ledger")
        expected_all_sources = sorted({
            str(item.get("source") or "")
            for item in assignments
            if isinstance(item, dict) and str(item.get("source") or "")
        })
        if row.get("all_assignment_sources") != expected_all_sources:
            raise ValueError("P1.5 full assignment sources are hidden or invented")
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
            raise ValueError("P1.5 protected assignment sources are hidden or invented")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("P1.5 report omitted summary")
    expected_mismatches = [
        row["id"] for row in cases
        if (
            row.get("answer_supported") != row.get("expected_supported")
            or row.get("assignment_sources")
            != row.get("expected_assignment_sources")
        )
    ]
    expected_advisory = [
        {"case_id": row["id"], "source": source}
        for row in cases
        for source in row.get("assignment_sources") or ()
        if "advisory.example" in source or "blog.example" in source
    ]
    if summary.get("mismatches") != expected_mismatches:
        raise ValueError("P1.5 provenance mismatches are hidden or invented")
    if summary.get("advisory_assignments") != expected_advisory:
        raise ValueError("P1.5 advisory assignments are hidden or invented")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(key) is not False
        for key in ("production_runtime_changed", "autonomous_agent_truth_proven")
    ):
        raise ValueError("P1.5 report overclaims runtime or autonomous evidence")
    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("P1.5 report omitted decision")
    expected_decision = (
        "accepted"
        if not expected_mismatches and not expected_advisory
        else "rejected"
    )
    if decision.get("claim_local_provenance") != expected_decision:
        raise ValueError("P1.5 decision does not match measured provenance")
    if decision.get("accepted_production_changes") != []:
        raise ValueError("P1.5 accepted an unreviewed production change")
    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("P1.5 report contains an absolute local path")


def derive_from_paths(
    *,
    repo_root: Path,
    protocol_path: Path,
    model_path: Path,
) -> dict[str, Any]:
    return derive_report(
        protocol=load_json(protocol_path),
        source_identities={
            "protocol_git_blob_sha1": git_blob_sha(protocol_path, repo_root=repo_root),
            "proof_runtime": build_proof_runtime_manifest(repo_root),
            "evidence_model_git_blob_sha1": git_blob_sha(model_path, repo_root=repo_root),
        },
    )
