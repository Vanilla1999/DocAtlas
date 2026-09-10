#!/usr/bin/env python3
"""Independent report-only project context quality v2 evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "eval/project_context_quality_v2"
CASES_PATH = CORPUS_DIR / "cases.json"
MIGRATION_PATH = CORPUS_DIR / "migration-crosswalk.json"
DIAGNOSTIC_PATH = CORPUS_DIR / "diagnostic.json"
LOCK_PATH = CORPUS_DIR / "protocol.lock.json"
SUPPORTED_DOCUMENT_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".adoc"}
EXCLUDED_DIRECTORY_NAMES = {
    ".git", ".hg", ".svn", ".dart_tool", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".tox", ".venv", "venv", "env", "node_modules", "build",
    "dist", "target", ".next", ".turbo", "coverage", "htmlcov", "__pycache__",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_prose(value: str) -> str:
    """Normalize Markdown presentation without semantic rewriting."""
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|>\s?)", "", value)
    value = re.sub(r"[*~]", "", value).replace("`", "")
    return " ".join(value.casefold().split())


def _call_keyword_signature(value: str) -> tuple[str, dict[str, str]] | None:
    """Parse a simple keyword-only call used as a semantic witness."""
    match = re.fullmatch(r"([a-z_]\w*(?:\.[a-z_]\w*)*)\(([^()]*)\)", value.strip(), re.I)
    if not match:
        return None
    function, body = match.groups()
    parts = [part.strip() for part in body.split(",") if part.strip()]
    if not parts or any("=" not in part for part in parts):
        return None
    kwargs: dict[str, str] = {}
    for part in parts:
        key, raw_value = part.split("=", 1)
        key = key.strip().casefold()
        if not re.fullmatch(r"[a-z_]\w*", key, re.I):
            return None
        kwargs[key] = re.sub(r"\s+", "", raw_value.casefold())
    return function.casefold(), kwargs


def _witness_visible(witness: str, visible_text: str) -> bool:
    """Match prose exactly, but allow extra kwargs on the same witnessed call."""
    witness_normalized = normalize_prose(witness)
    visible_normalized = normalize_prose(visible_text)
    if witness_normalized in visible_normalized:
        return True
    signature = _call_keyword_signature(witness_normalized)
    if signature is None:
        return False
    function, required_kwargs = signature
    for match in re.finditer(
        rf"(?<![\w.]){re.escape(function)}\(([^()]*)\)", visible_normalized, re.I,
    ):
        candidate = _call_keyword_signature(f"{function}({match.group(1)})")
        if candidate is not None and all(
            candidate[1].get(key) == value for key, value in required_kwargs.items()
        ):
            return True
    return False


def _catalog() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load((ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8"))
    documents = {
        str(row["path"]): row for row in payload["documents"]
        if row.get("status") == "active"
    }
    for row in payload.get("roots", []):
        if row.get("status", "active") != "active":
            continue
        root_path = ROOT / str(row["path"])
        for path in root_path.glob("**/*"):
            relative_to_root = path.relative_to(root_path)
            if (path.is_file() and not path.is_symlink()
                    and path.suffix.casefold() in SUPPORTED_DOCUMENT_SUFFIXES
                    and not any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_to_root.parts)):
                documents.setdefault(path.relative_to(ROOT).as_posix(), row)
    return documents


def _payload() -> dict[str, Any]:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    for name, path in (
        ("cases", CASES_PATH), ("migration_crosswalk", MIGRATION_PATH),
        ("diagnostic", DIAGNOSTIC_PATH),
    ):
        if lock["files"][name] != _sha256(path):
            raise ValueError(f"v2 {name} hash does not match independent lock")
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def load_cases(lane: str | None = None) -> tuple[dict[str, Any], ...]:
    payload = _payload()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    rows = tuple(dict(row) for row in payload["cases"])
    ids = [row["id"] for row in rows]
    if ids != lock["inventory"]["case_ids"] or len(set(ids)) != len(ids):
        raise ValueError("v2 corpus inventory mismatch")
    obligations = payload["obligations"]
    for row in rows:
        resolved = []
        for reference in row["obligations"]:
            obligation_id = reference.get("obligation_id", reference.get("id"))
            lookup_query_ids = reference.get("lookup_query_ids", reference.get("component_query_ids"))
            obligation = dict(obligations[obligation_id])
            obligation["lookup_query_ids"] = list(lookup_query_ids)
            resolved.append(obligation)
        row["obligations"] = resolved
    if lane is not None:
        if lane not in lock["inventory"]["lanes"]:
            raise ValueError(f"unknown v2 lane: {lane}")
        rows = tuple(row for row in rows if row["lane"] == lane)
    return rows


def validate_corpus() -> dict[str, Any]:
    rows = load_cases()
    catalog = _catalog()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    migration = json.loads(MIGRATION_PATH.read_text(encoding="utf-8"))["crosswalk"]
    if {row["v2_id"] for row in migration} != {row["id"] for row in rows}:
        raise ValueError("v2 migration crosswalk is incomplete")
    witness_paths: set[str] = set()
    lane_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    for case in rows:
        lane_counts[case["lane"]] += 1
        case_type = case.get("case_type", "positive" if case["expected_kind"] == "docs_context" else "strict_negative")
        type_counts[case_type] += 1
        if case["question"] != case["original_question"]:
            raise ValueError(f"original prompt changed: {case['id']}")
        if case.get("case_type", "positive" if case["expected_kind"] == "docs_context" else "strict_negative") == "positive" and not case["obligations"]:
            raise ValueError(f"positive case has no obligations: {case['id']}")
        if len(case["lookup_queries"]) != len(case["lookup_query_ids"]):
            raise ValueError(f"lookup inventory mismatch: {case['id']}")
        for obligation in case["obligations"]:
            if not obligation.get("accepted_witnesses") or not obligation.get("lookup_query_ids"):
                raise ValueError(f"incomplete obligation: {case['id']}/{obligation['id']}")
            if obligation["id"] in case["lookup_query_ids"]:
                raise ValueError(f"semantic obligation reuses a lookup id: {case['id']}/{obligation['id']}")
            for witness in obligation["accepted_witnesses"]:
                path = witness["path"]
                metadata = catalog.get(path)
                if metadata is None:
                    raise ValueError(f"witness is not an active catalog document: {path}")
                if metadata["authority"] not in obligation["accepted_authorities"] or metadata["scope"] not in obligation["accepted_scopes"]:
                    raise ValueError(f"witness authority/scope mismatch: {path}")
                if normalize_prose(witness["text"]) not in normalize_prose((ROOT / path).read_text(encoding="utf-8")):
                    raise ValueError(f"witness text is absent from active document: {path}")
                witness_paths.add(path)
    if dict(lane_counts) != lock["inventory"]["lanes"]:
        raise ValueError("v2 lane inventory mismatch")
    expected_type_counts = {
        "positive": lock["inventory"]["positive_count"],
        "strict_negative": lock["inventory"]["negative_count"],
        "unsupported_answer_control": lock["inventory"]["unsupported_answer_control_count"],
    }
    if dict(type_counts) != expected_type_counts:
        raise ValueError("v2 case-type inventory mismatch")
    if {path: _sha256(ROOT / path) for path in sorted(witness_paths)} != lock["active_document_sha256"]:
        raise ValueError("active witness document revision mismatch")
    return {"case_count": len(rows), "lane_counts": dict(lane_counts), "witness_document_count": len(witness_paths)}


def _source_identity(source: dict[str, Any], synthetic: bool, catalog: dict[str, dict[str, Any]]) -> tuple[str, str, str]:
    path = str(source.get("path_or_url") or (source.get("path") if synthetic else "") or "")
    if synthetic:
        return path, str(source.get("authority") or ""), str(source.get("scope") or "")
    metadata = catalog.get(path) or {}
    return path, str(metadata.get("authority") or ""), str(metadata.get("scope") or "")


def _heading_only(value: str) -> bool:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return bool(lines) and all(re.fullmatch(r"#{1,6}\s+\S.*", line) for line in lines)


def _runtime_component_claim(response: dict[str, Any], returned_evidence_ids: set[str]) -> dict[str, Any]:
    diagnostics = response.get("diagnostics") or {}
    claim = diagnostics.get("runtime_component_coverage", diagnostics.get("component_coverage"))
    if not isinstance(claim, dict):
        return {"available": False, "valid": None, "status": "unavailable", "full": None}
    mandatory = claim.get("mandatory_component_ids")
    covered = claim.get("covered_component_ids")
    missing = claim.get("missing_component_ids")
    evidence_ids = claim.get("evidence_ids")
    valid_shape = all(isinstance(value, list) and all(isinstance(item, str) and item for item in value)
                      and len(set(value)) == len(value) for value in (mandatory, covered, missing, evidence_ids))
    if not valid_shape:
        return {"available": True, "valid": False, "status": str(claim.get("status") or ""), "full": None}
    bindings = diagnostics.get("component_evidence_bindings")
    bound_components: set[str] = set()
    bound_runtime_ids: set[str] = set()
    binding_valid = isinstance(bindings, list)
    for binding in bindings if isinstance(bindings, list) else []:
        if not isinstance(binding, dict):
            binding_valid = False
            continue
        source = next((source for source in response.get("sources") or []
                       if isinstance(source, dict) and source.get("evidence_id") == binding.get("evidence_id")), {})
        if (not source or binding.get("path_or_url") != source.get("path_or_url")
                or binding.get("snippet_sha256") != hashlib.sha256(str(source.get("snippet") or "").encode()).hexdigest()
                or binding.get("component_id") not in covered):
            binding_valid = False
        else:
            bound_components.add(binding["component_id"])
            bound_runtime_ids.update(binding.get("runtime_evidence_ids") or [])
    normalized_evidence = [str(value) for value in evidence_ids or [] if str(value)]
    valid = bool(valid_shape and len(normalized_evidence) == len(evidence_ids or [])
                 and len(set(normalized_evidence)) == len(normalized_evidence)
                 and (set(normalized_evidence) <= returned_evidence_ids or
                      binding_valid and set(normalized_evidence) <= bound_runtime_ids))
    coherent = (set(covered) | set(missing) == set(mandatory) and not set(covered) & set(missing)
                and claim.get("status") == ("full" if mandatory and not missing and not claim.get("unresolved_residue")
                                            else "partial" if covered else "unavailable"))
    valid = valid and coherent and (bindings is None or binding_valid and bound_components == set(covered))
    if covered and "runtime_component_coverage" in diagnostics and bindings is None:
        valid = False
    return {
        "available": True, "valid": valid, "status": str(claim.get("status") or ""),
        "full": claim.get("status") == "full" if valid else None,
        "mandatory_component_ids": [str(value) for value in mandatory or []],
        "covered_component_ids": [str(value) for value in covered or []],
        "missing_component_ids": [str(value) for value in missing or []],
        "evidence_ids": normalized_evidence,
        "visible_binding_verified": binding_valid and bound_components == set(covered),
    }


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    sources = response.get("sources") if isinstance(response.get("sources"), list) else []
    synthetic = response.get("fixture_kind") == "synthetic"
    catalog = _catalog()
    source_rows = [(*_source_identity(source, synthetic, catalog), source) for source in sources if isinstance(source, dict)]
    evidence_ids = [str(source.get("evidence_id") or "") for _, _, _, source in source_rows]
    evidence_id_counts = Counter(evidence_ids)
    returned_evidence_ids = {value for value in evidence_ids if value}
    accepted_paths = {w["path"] for o in case["obligations"] for w in o["accepted_witnesses"]}
    visible = normalize_prose(json.dumps({key: value for key, value in response.items() if key != "diagnostics"}, ensure_ascii=False))
    safety_ok = not any(normalize_prose(value) in visible for value in case.get("forbidden_fragments", []))
    identity_ok = (isinstance(response.get("sources", []), list) and len(source_rows) == len(sources) and all(path and authority and scope and evidence_id and str(source.get("snippet") or "").strip() and not _heading_only(str(source.get("snippet", "")))
                       for (path, authority, scope, source), evidence_id in zip(source_rows, evidence_ids))
                   and len(returned_evidence_ids) == len(source_rows))
    limits = _payload()["limits"]
    token_value = response.get("estimated_tokens")
    token_known = isinstance(token_value, int) and not isinstance(token_value, bool) and token_value >= 0
    public_payload = {key: value for key, value in response.items() if key != "diagnostics"}
    actual_tokens = max(1, (len(json.dumps(public_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()) + 3) // 4)
    budget_ok = len(sources) <= limits["maximum_sources"] and token_known and max(token_value, actual_tokens) <= limits["maximum_estimated_tokens"]
    obligation_results = []
    for obligation in case["obligations"]:
        matches = []
        for witness in obligation["accepted_witnesses"]:
            for path, authority, scope, source in source_rows:
                if (path == witness["path"] and authority in obligation["accepted_authorities"]
                        and scope in obligation["accepted_scopes"]
                        and str(source.get("evidence_id") or "")
                        and evidence_id_counts[str(source.get("evidence_id") or "")] == 1
                        and not _heading_only(str(source.get("snippet", "")))
                        and _witness_visible(witness["text"], str(source.get("snippet", "")))):
                    matches.append({"path_or_url": path, "evidence_id": source.get("evidence_id")})
        obligation_results.append({"id": obligation["id"], "met": bool(matches), "lookup_query_ids": obligation["lookup_query_ids"], "visible_witnesses": matches})
    case_type = case.get("case_type", "positive" if case["expected_kind"] == "docs_context" else "strict_negative")
    expected_negative = case_type == "strict_negative"
    unsupported_control = case_type == "unsupported_answer_control"
    all_components = bool(obligation_results) and all(row["met"] for row in obligation_results)
    semantic_useful = response.get("kind") == "docs_context" and all_components and safety_ok and identity_ok and budget_ok
    required_lookups = set(case["lookup_query_ids"])
    runtime_covered = {str(value) for value in response.get("covered_query_ids") or []}
    covered_lookups = required_lookups & runtime_covered
    lookup_attribution_complete = covered_lookups == required_lookups
    verified_component_ids = {row["id"] for row in obligation_results if row["met"]}
    required_component_ids = {row["id"] for row in obligation_results}
    verified_full = bool(required_component_ids) and verified_component_ids == required_component_ids
    runtime_original_claimed = "query-original" in runtime_covered
    authorization_denied = not any(response.get(field) is True for field in (
        "answer_supported", "answer_available", "edit_ready", "mutation_ready", "authorized", "authorization_granted",
    )) and not response.get("authorized_actions")
    semantic_useful = semantic_useful and authorization_denied
    unsupported_payload_kind = response.get("kind") == "insufficient_evidence" or (
        response.get("kind") in {None, "docs_context"} and response.get("status") == "insufficient_evidence"
    )
    negative_correct = expected_negative and unsupported_payload_kind and safety_ok and identity_ok and budget_ok and authorization_denied
    unsupported_answer_control_correct = unsupported_control and safety_ok and identity_ok and budget_ok and authorization_denied and (
        unsupported_payload_kind or (
            response.get("kind") == "docs_context"
            and response.get("answer_supported") is False
            and response.get("answer_available") is False
            and response.get("edit_ready") is False
        )
    )
    runtime_component_claim = _runtime_component_claim(response, returned_evidence_ids)
    false_full_coverage = bool(runtime_component_claim["available"] and runtime_component_claim["valid"]
                               and runtime_component_claim["full"] and not verified_full)
    extra_paths = sorted({path for path, _, _, _ in source_rows if path not in accepted_paths})
    adjudicated_count = sum(path in accepted_paths for path, _, _, _ in source_rows)
    if not safety_ok:
        root_cause = "safety_failure"
    elif not identity_ok:
        root_cause = "source_identity_failure"
    elif not budget_ok:
        root_cause = "budget_failure"
    elif runtime_component_claim["available"] and not runtime_component_claim["valid"]:
        root_cause = "runtime_component_claim_invalid"
    elif expected_negative and not negative_correct:
        root_cause = "negative_false_positive"
    elif unsupported_control and not unsupported_answer_control_correct:
        root_cause = "unsupported_answer_false_positive"
    elif false_full_coverage:
        root_cause = "false_full_coverage"
    elif not expected_negative and not unsupported_control and not semantic_useful:
        diagnostics = response.get("diagnostics") or {}
        if "retrieved_candidate_ids" in diagnostics and not diagnostics["retrieved_candidate_ids"]:
            root_cause = "no_retrieval_hit"
        elif diagnostics.get("qualification_rejections"):
            root_cause = "qualification_rejection"
        elif diagnostics.get("pre_projection_qualified_ids") and not diagnostics.get("selected_candidate_ids"):
            root_cause = "ranking_loss"
        elif diagnostics.get("selected_candidate_ids") and diagnostics.get("projection_rejections"):
            root_cause = "projection_truncation"
        else:
            root_cause = "semantic_obligation_missing"
    elif not lookup_attribution_complete:
        root_cause = "lookup_attribution_missing"
    elif extra_paths:
        root_cause = "precision_loss"
    else:
        root_cause = "none"
    return {
        "id": case["id"], "lane": case["lane"], "semantic_useful": semantic_useful,
        "negative_correct": negative_correct, "lookup_attribution_complete": lookup_attribution_complete,
        "unsupported_answer_control_correct": unsupported_answer_control_correct,
        "lookup_covered": len(covered_lookups), "lookup_required": len(required_lookups),
        "runtime_claimed_original_retrieval_coverage": runtime_original_claimed,
        "runtime_component_coverage_claim": runtime_component_claim,
        "evaluator_verified_component_coverage": {"numerator": len(verified_component_ids), "denominator": len(required_component_ids), "full": verified_full},
        "false_full_coverage": false_full_coverage, "unadjudicated_source_paths": extra_paths,
        "unadjudicated_relevance": bool(extra_paths),
        "adjudicated_source_count": adjudicated_count, "returned_source_count": len(source_rows),
        "obligations": obligation_results,
        "hard_gates": {"safety": safety_ok, "source_identity": identity_ok, "budget": budget_ok, "estimated_tokens_present": token_known, "authorization_denied": authorization_denied},
        "root_cause": root_cause,
        "diagnostics": response.get("diagnostics") or {},
    }


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    return {"numerator": numerator, "denominator": denominator}


def evaluate(responses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    validation = validate_corpus()
    rows = load_cases()
    results = [evaluate_case(case, responses.get(case["id"], {"kind": "missing", "sources": [], "estimated_tokens": 0})) for case in rows]
    lane_reports: dict[str, Any] = {}
    for lane in ("natural", "exposed_paraphrases"):
        pairs = [(case, result) for case, result in zip(rows, results) if case["lane"] == lane]
        positives = [result for case, result in pairs if case.get("case_type", "positive" if case["expected_kind"] == "docs_context" else "strict_negative") == "positive"]
        negatives = [result for case, result in pairs if case.get("case_type", "positive" if case["expected_kind"] == "docs_context" else "strict_negative") == "strict_negative"]
        unsupported_controls = [result for case, result in pairs if case.get("case_type") == "unsupported_answer_control"]
        lane_reports[lane] = {
            "status": "BASELINE_REPORT_ONLY" if lane == "natural" else "EXPOSED_PARAPHRASES_REPORT_ONLY",
            "positive_cases": len(positives), "negative_cases": len(negatives),
            "unsupported_answer_control_cases": len(unsupported_controls),
            "metrics": {
                "semantic_usefulness": _fraction(sum(r["semantic_useful"] for r in positives), len(positives)),
                "lookup_attribution": _fraction(sum(r["lookup_covered"] for r in positives), sum(r["lookup_required"] for r in positives)),
                "source_precision": _fraction(sum(r["adjudicated_source_count"] for r in positives), sum(r["returned_source_count"] for r in positives)),
                "safety": _fraction(sum(r["hard_gates"]["safety"] for _, r in pairs), len(pairs)),
                "budget_compliance": _fraction(sum(r["hard_gates"]["budget"] for _, r in pairs), len(pairs)),
                "negative_correctness": _fraction(sum(r["negative_correct"] for r in negatives), len(negatives)),
                "unsupported_answer_control_correctness": _fraction(sum(r["unsupported_answer_control_correct"] for r in unsupported_controls), len(unsupported_controls)),
                "runtime_claimed_original_retrieval_coverage": _fraction(sum(r["runtime_claimed_original_retrieval_coverage"] for r in positives), len(positives)),
                "evaluator_verified_full_semantic_component_coverage": _fraction(sum(r["evaluator_verified_component_coverage"]["full"] for r in positives), len(positives)),
                "false_full_coverage": _fraction(sum(r["false_full_coverage"] for r in positives), len(positives)),
            },
            "root_cause_counts": dict(sorted(Counter(r["root_cause"] for _, r in pairs).items())),
        }
    return {"schema_version": "project-context-quality-v2-result-2", "report_only": True,
            "verdict": "REPORT_ONLY", "thresholds": None, "validation": validation,
            "lanes": lane_reports, "results": results}


def run_live() -> dict[str, Any]:
    """Run current in-process self-host production, then score only visible payloads."""
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    rows = load_cases()
    runnable = [row for row in rows if row.get("case_type", "positive" if row["expected_kind"] == "docs_context" else "strict_negative") != "strict_negative"]
    negatives = [row for row in rows if row not in runnable]
    live_cases = tuple(LiveCase(
        case_id=row["id"], question=row["question"], scope=row["scope"],
        expected_kind="docs_context" if row.get("case_type", "positive") == "positive" else None,
        relevant_paths=tuple(dict.fromkeys(w["path"] for o in row["obligations"] for w in o["accepted_witnesses"])),
        required_fact_groups=tuple(tuple((w["path"], w["text"]) for w in o["accepted_witnesses"]) for o in row["obligations"]),
        lookup_queries=tuple(row["lookup_queries"]), minimum_lookup_coverage=0,
        allowed_paths=tuple(dict.fromkeys(w["path"] for o in row["obligations"] for w in o["accepted_witnesses"])),
        expected_public_query_ids=tuple(row["expected_public_query_ids"]),
    ) for row in runnable)
    production = run(cases=live_cases, negative_cases=tuple(LiveCase(
        case_id=row["id"], question=row["question"], scope=row["scope"], expected_kind="insufficient_evidence", relevant_paths=(),
    ) for row in negatives))
    responses = {str(row["case_id"]): row.get("payload") or {"status": row.get("observed", {}).get("status"), "kind": row.get("observed", {}).get("kind"), "sources": [], "estimated_tokens": 0} for row in production["results"]}
    report = evaluate(responses)
    report["run_mode"] = "live_self_host"
    report["claim_boundary"] = "in_process_current_production_not_installed_agent"
    report["production_runner_verdict"] = production.get("verdict")
    report["production_runner_errors"] = production.get("errors")
    report["production_results"] = production["results"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.live and args.responses:
        parser.error("--live and --responses are mutually exclusive")
    responses = json.loads(args.responses.read_text(encoding="utf-8")) if args.responses else {}
    report = run_live() if args.live else evaluate(responses)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
