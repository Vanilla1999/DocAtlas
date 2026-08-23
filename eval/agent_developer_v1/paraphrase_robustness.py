from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from docmancer.docs.application.evidence_selection import (
    build_requirements,
    diagnose_proofability,
    project_docs_selection_config,
    requirement_probe_query,
    select_evidence,
)
from docmancer.docs.domain.project_answer_contract import (
    build_project_answer_contract,
)


PROTOCOL = "paraphrase-proofability-v1"
REPORT_PROTOCOL = "paraphrase-proofability-report-v1"
SCHEMA_VERSION = 1
FAMILIES = (
    "exact_identifier",
    "behavior",
    "requirements",
    "policy",
    "typo",
    "alias",
    "negative_control",
)
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)",
)
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]+", re.UNICODE)


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
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def git_blob_sha1(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _relative_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"P1.4 source is outside the repository: {path}") from exc


def _validate_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("P1.4 protocol schema mismatch")
    if protocol.get("protocol") != PROTOCOL:
        raise ValueError("P1.4 protocol identity mismatch")
    cases = protocol.get("cases")
    if not isinstance(cases, list) or len(cases) != 14:
        raise ValueError("P1.4 protocol must contain exactly 14 cases")
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("P1.4 case must be an object")
        case_id = str(case.get("id") or "")
        family = str(case.get("family") or "")
        if not case_id or case_id in ids:
            raise ValueError(f"invalid or duplicate P1.4 case: {case_id!r}")
        ids.add(case_id)
        if family not in FAMILIES:
            raise ValueError(f"unknown P1.4 family: {family!r}")
        counts[family] += 1
        for key in ("question", "candidate_source", "candidate_text"):
            if not str(case.get(key) or "").strip():
                raise ValueError(f"P1.4 case {case_id} omitted {key}")
        discovery_terms = case.get("discovery_terms")
        if not isinstance(discovery_terms, list) or not discovery_terms:
            raise ValueError(f"P1.4 case {case_id} omitted discovery_terms")
        if any(not str(value).strip() for value in discovery_terms):
            raise ValueError(f"P1.4 case {case_id} has an empty discovery term")
        for key in ("require_discovery", "require_support", "negative_control"):
            if not isinstance(case.get(key), bool):
                raise ValueError(f"P1.4 case {case_id} omitted boolean {key}")
        if case["require_support"] and not case["require_discovery"]:
            raise ValueError(f"P1.4 case {case_id} requires support without discovery")
    if counts != Counter({family: 2 for family in FAMILIES}):
        raise ValueError(f"P1.4 family cardinality drift: {dict(counts)!r}")
    if ABSOLUTE_PATH_RE.search(canonical_json(protocol)):
        raise ValueError("P1.4 protocol contains an absolute local path")


def _singular_token(value: str) -> str:
    token = value.casefold().replace("ё", "е")
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(values: Iterable[Any]) -> frozenset[str]:
    result: set[str] = set()
    for value in values:
        for token in TOKEN_RE.findall(str(value or "")):
            normalized = _singular_token(token)
            if normalized:
                result.add(normalized)
    return frozenset(result)


def _obligation_values(obligation: Any) -> tuple[str, ...]:
    rows = [
        getattr(obligation, "subject", None),
        *(getattr(obligation, "subject_aliases", ()) or ()),
        getattr(obligation, "attribute", None),
        getattr(obligation, "relation", None),
        getattr(obligation, "target", None),
        getattr(obligation, "expected_value", None),
        getattr(obligation, "item_kind", None),
        getattr(obligation, "context", None),
    ]
    return tuple(str(value) for value in rows if str(value or "").strip())


def _planner_state(question: str) -> tuple[Any, Any, dict[str, Any], frozenset[str]]:
    contract = build_project_answer_contract(question)
    requirements = build_requirements(question, profile="project_docs_answer")
    probes = tuple(
        value
        for requirement in requirements
        if (value := requirement_probe_query(requirement))
    )
    obligation_values = tuple(
        value
        for obligation in contract.proof_obligations
        for value in _obligation_values(obligation)
    )
    discovery_values = (
        *contract.subjects,
        *contract.retrieval_hints,
        *contract.concept_queries,
        *requirements.retrieval_hints,
        *requirements.concept_queries,
        *probes,
        *obligation_values,
    )
    planner = {
        "subjects": list(contract.subjects),
        "retrieval_hints": list(requirements.retrieval_hints),
        "concept_queries": list(requirements.concept_queries),
        "parse_trace": list(requirements.parse_trace),
        "unresolved_parts": list(requirements.unresolved_parts),
        "requirement_probe_count": len(probes),
        "proof_obligation_count": sum(
            item.kind == "proof_obligation" for item in requirements
        ),
    }
    return contract, requirements, planner, _tokens(discovery_values)


def _term_matches(
    term: str,
    *,
    planner_tokens: frozenset[str],
    candidate_tokens: frozenset[str],
) -> bool:
    expected = _tokens((term,))
    return bool(expected) and expected <= planner_tokens and expected <= candidate_tokens


def _candidate(case: dict[str, Any]) -> dict[str, Any]:
    text = str(case["candidate_text"])
    stable_id = f"p1.4:{case['id']}"
    parent_id = stable_id + ":parent"
    return {
        "stable_chunk_id": stable_id,
        "parent_logical_id": parent_id,
        "source": str(case["candidate_source"]),
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "authority": "source_of_truth",
        "repository_authority": "source_of_truth",
        "source_class": "project_file",
        "docs_exactness": "exact",
        "version": "not_applicable",
        "freshness": "current",
        "navigation_only": False,
        "retrieval_rank": 1,
        "score": 1.0,
        "metadata": {
            "stable_chunk_id": stable_id,
            "parent_logical_id": parent_id,
        },
    }


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    question = str(case["question"])
    _, requirements, planner, planner_tokens = _planner_state(question)
    candidate = _candidate(case)
    candidate_tokens = _tokens((
        case["candidate_source"],
        case["candidate_text"],
    ))
    matched_terms = sorted(
        str(term)
        for term in case["discovery_terms"]
        if _term_matches(
            str(term),
            planner_tokens=planner_tokens,
            candidate_tokens=candidate_tokens,
        )
    )
    decision = select_evidence(
        [candidate],
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )
    support = decision.support_decision
    selected_sources = sorted({
        item.path_or_url for item in decision.selected_candidates
    })
    return {
        "id": str(case["id"]),
        "family": str(case["family"]),
        "question": question,
        "candidate_source": str(case["candidate_source"]),
        "candidate_content_sha256": hashlib.sha256(
            str(case["candidate_text"]).encode("utf-8")
        ).hexdigest(),
        "negative_control": bool(case["negative_control"]),
        "require_discovery": bool(case["require_discovery"]),
        "require_support": bool(case["require_support"]),
        "candidate_discovered": bool(matched_terms),
        "matched_discovery_terms": matched_terms,
        "answer_supported": bool(support.answer_supported),
        "support_status": str(support.support_status),
        "support_reason_code": support.reason_code,
        "selected_sources": selected_sources,
        "selected_evidence_ids": list(support.selected_evidence_ids),
        "missing_requirement_ids": list(support.missing_requirement_ids),
        "assignment_count": len(decision.assignments),
        "requirements_hash": support.requirements_hash,
        "decision_hash": support.decision_hash,
        "planner": planner,
        "proofability": diagnose_proofability(decision),
    }


def _family_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for family in FAMILIES:
        selected = [row for row in rows if row["family"] == family]
        result[family] = {
            "case_count": len(selected),
            "candidate_discovered": sum(bool(row["candidate_discovered"]) for row in selected),
            "answer_supported": sum(bool(row["answer_supported"]) for row in selected),
            "required_discovery": sum(bool(row["require_discovery"]) for row in selected),
            "required_discovery_passed": sum(
                bool(row["require_discovery"] and row["candidate_discovered"])
                for row in selected
            ),
            "required_support": sum(bool(row["require_support"]) for row in selected),
            "required_support_passed": sum(
                bool(row["require_support"] and row["answer_supported"])
                for row in selected
            ),
            "negative_false_support": sum(
                bool(row["negative_control"] and row["answer_supported"])
                for row in selected
            ),
        }
    return result


def _summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "case_count": len(rows),
        "candidate_discovered": sum(bool(row["candidate_discovered"]) for row in rows),
        "answer_supported": sum(bool(row["answer_supported"]) for row in rows),
        "required_discovery": sum(bool(row["require_discovery"]) for row in rows),
        "required_discovery_passed": sum(
            bool(row["require_discovery"] and row["candidate_discovered"])
            for row in rows
        ),
        "required_support": sum(bool(row["require_support"]) for row in rows),
        "required_support_passed": sum(
            bool(row["require_support"] and row["answer_supported"])
            for row in rows
        ),
        "negative_control_count": sum(bool(row["negative_control"]) for row in rows),
        "false_supported_negative_controls": sum(
            bool(row["negative_control"] and row["answer_supported"])
            for row in rows
        ),
    }


def derive_from_paths(
    *,
    repo_root: Path,
    protocol_path: Path,
    selector_path: Path,
    planner_path: Path,
) -> dict[str, Any]:
    protocol = load_json(protocol_path)
    _validate_protocol(protocol)
    rows = [_run_case(case) for case in protocol["cases"]]
    summary = _summary(rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": REPORT_PROTOCOL,
        "source_identities": {
            "protocol": {
                "path": _relative_path(protocol_path, repo_root),
                "git_blob_sha1": git_blob_sha1(protocol_path),
            },
            "selector": {
                "path": _relative_path(selector_path, repo_root),
                "git_blob_sha1": git_blob_sha1(selector_path),
            },
            "planner": {
                "path": _relative_path(planner_path, repo_root),
                "git_blob_sha1": git_blob_sha1(planner_path),
            },
        },
        "summary": summary,
        "families": _family_metrics(rows),
        "cases": rows,
        "decision": {
            "core_exact_proofability": (
                "accepted"
                if summary["required_discovery_passed"] == summary["required_discovery"]
                and summary["required_support_passed"] == summary["required_support"]
                else "rejected"
            ),
            "negative_control_precision": (
                "accepted"
                if summary["false_supported_negative_controls"] == 0
                else "rejected"
            ),
            "typo_and_alias_results_are_measurement_only": True,
            "production_change_authorized": False,
        },
        "claim_boundary": {
            "candidate_discovery_separate_from_support": True,
            "production_runtime_changed": False,
            "public_api_changed": False,
            "support_semantics_relaxed": False,
            "autonomous_agent_truth_proven": False,
            "product_maturity": "Beta",
        },
    }
    verify_report(report)
    return report


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("P1.4 report schema mismatch")
    if report.get("protocol") != REPORT_PROTOCOL:
        raise ValueError("P1.4 report identity mismatch")
    rows = report.get("cases")
    if not isinstance(rows, list) or len(rows) != 14:
        raise ValueError("P1.4 report must contain exactly 14 cases")
    ids = [str(row.get("id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != 14 or len(set(ids)) != 14:
        raise ValueError("P1.4 report case identities are incomplete")
    if Counter(str(row.get("family") or "") for row in rows) != Counter(
        {family: 2 for family in FAMILIES}
    ):
        raise ValueError("P1.4 report family cardinality drift")

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("P1.4 report case is malformed")
        if row.get("negative_control") is True and row.get("answer_supported") is True:
            raise ValueError("P1.4 negative control was falsely supported")
        if row.get("require_discovery") is True and row.get("candidate_discovered") is not True:
            raise ValueError("P1.4 required candidate discovery failed")
        if row.get("require_support") is True and row.get("answer_supported") is not True:
            raise ValueError("P1.4 required support failed")
        if row.get("answer_supported") is True and not row.get("selected_sources"):
            raise ValueError("P1.4 supported answer has no selected evidence")
        if row.get("answer_supported") is True and row.get("support_status") != "supported":
            raise ValueError("P1.4 support status contradicts the support verdict")
        if row.get("answer_supported") is not True and row.get("support_status") == "supported":
            raise ValueError("P1.4 unsupported row reports supported status")
        if ABSOLUTE_PATH_RE.search(canonical_json(row.get("selected_sources") or [])):
            raise ValueError("P1.4 report contains an absolute local path")

    expected_summary = _summary(rows)
    if report.get("summary") != expected_summary:
        raise ValueError("P1.4 report summary drift")
    if report.get("families") != _family_metrics(rows):
        raise ValueError("P1.4 report family metrics drift")

    identities = report.get("source_identities")
    if not isinstance(identities, dict) or set(identities) != {
        "protocol", "selector", "planner"
    }:
        raise ValueError("P1.4 report source identities are incomplete")
    for identity in identities.values():
        if not isinstance(identity, dict):
            raise ValueError("P1.4 source identity is malformed")
        if not str(identity.get("path") or "") or str(identity["path"]).startswith(("/", "\\")):
            raise ValueError("P1.4 source identity contains an absolute local path")
        if re.fullmatch(r"[0-9a-f]{40}", str(identity.get("git_blob_sha1") or "")) is None:
            raise ValueError("P1.4 source identity has an invalid Git blob hash")

    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("P1.4 report omitted its decision")
    expected_core = (
        "accepted"
        if expected_summary["required_discovery_passed"] == expected_summary["required_discovery"]
        and expected_summary["required_support_passed"] == expected_summary["required_support"]
        else "rejected"
    )
    if decision.get("core_exact_proofability") != expected_core:
        raise ValueError("P1.4 core proofability decision drift")
    expected_negative = (
        "accepted"
        if expected_summary["false_supported_negative_controls"] == 0
        else "rejected"
    )
    if decision.get("negative_control_precision") != expected_negative:
        raise ValueError("P1.4 negative-control decision drift")
    if decision.get("production_change_authorized") is not False:
        raise ValueError("P1.4 report overclaims a production change")

    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P1.4 report omitted its claim boundary")
    if boundary.get("candidate_discovery_separate_from_support") is not True:
        raise ValueError("P1.4 report conflates discovery with support")
    for key in (
        "production_runtime_changed",
        "public_api_changed",
        "support_semantics_relaxed",
        "autonomous_agent_truth_proven",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"P1.4 report overclaims {key}")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P1.4 report overclaims product maturity")
    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("P1.4 report contains an absolute local path")


def render_markdown(report: dict[str, Any]) -> str:
    verify_report(report)
    lines = [
        "# P1.4 — Paraphrase and proofability robustness",
        "",
        "Status: **closed with provider-free measured evidence**.",
        "",
        "Candidate discovery is measured independently from final support. A hit "
        "does not authorize an answer unless the production selector localizes all "
        "mandatory proof obligations in bounded evidence.",
        "",
        "| Family | Cases | Discovered | Supported | Required discovery | Required support |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for family in FAMILIES:
        metric = report["families"][family]
        lines.append(
            f"| `{family}` | {metric['case_count']} | "
            f"{metric['candidate_discovered']} | {metric['answer_supported']} | "
            f"{metric['required_discovery_passed']}/{metric['required_discovery']} | "
            f"{metric['required_support_passed']}/{metric['required_support']} |"
        )
    lines.extend([
        "",
        f"- core exact proofability: `{report['decision']['core_exact_proofability']}`",
        f"- negative-control precision: `{report['decision']['negative_control_precision']}`",
        "- typo and alias outcomes remain measurements, not authority expansion.",
        "- production runtime/public API/support semantics: unchanged.",
        "- autonomous Agent Truth: not proven.",
        "- maturity: Beta.",
        "",
    ])
    return "\n".join(lines)


# Backward-compatible verifier name for older local callers. It does not restore
# the superseded 15-case production-MCP protocol.
validate_report = verify_report


__all__ = [
    "FAMILIES",
    "PROTOCOL",
    "REPORT_PROTOCOL",
    "canonical_json",
    "derive_from_paths",
    "git_blob_sha1",
    "load_json",
    "render_markdown",
    "sha256_json",
    "validate_report",
    "verify_report",
]
