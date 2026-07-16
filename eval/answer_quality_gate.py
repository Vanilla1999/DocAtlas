#!/usr/bin/env python3
"""Frozen Task 43 protocol validation and provider-free quality primitives.

This protocol-phase module intentionally has no real-case execution entrypoint.
The frozen Task 39 and Task 42 fixtures may be evaluated only by the follow-up
implementation after this protocol has merged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "eval" / "answer_quality"
PROTOCOL_PATH = DATA_ROOT / "protocol_v1.lock.json"
CASE_CONTRACT_PATHS = (
    DATA_ROOT / "docs_cases.json",
    DATA_ROOT / "patch_cases.json",
    DATA_ROOT / "adversarial_cases.json",
)
EXPECTED_SOURCE_REFS = {
    "task39": {
        "development": ROOT / "eval" / "retrieval_quality" / "development.json",
        "holdout": ROOT / "eval" / "retrieval_quality" / "holdout.json",
        "adversarial": ROOT / "eval" / "retrieval_quality" / "adversarial.json",
    },
    "task42": {
        "docs_cases": ROOT / "eval" / "evidence_selection" / "docs_cases.json",
        "patch_cases": ROOT / "eval" / "evidence_selection" / "patch_cases.json",
        "adversarial_cases": ROOT / "eval" / "evidence_selection" / "adversarial_cases.json",
    },
}
ALLOWED_TAXONOMIES = frozenset({
    "exact_api", "configuration", "cli", "error", "conceptual", "code_example",
    "version_migration", "project_policy", "cross_module", "paraphrase",
    "insufficient_evidence", "distractor", "scope", "identity", "patch_contract",
})
REQUIRED_QUALITY_GATES = {
    "protected_required_fact_rate_min_delta": 0.0,
    "forbidden_source_violations_max": 0,
    "forbidden_version_violations_max": 0,
    "unsupported_claim_violations_max": 0,
    "citation_validity_rate_min": 1.0,
    "insufficient_false_success_rate_max_delta": 0.0,
    "docs_median_visible_tokens_max_delta": 0.0,
    "patch_median_visible_tokens_max_delta": 0.0,
    "retrieval_projection_p95_latency_ratio_max": 1.10,
}
REQUIRED_SOURCE_REVISION = {
    "commit_sha": "59aa94c39c6885b30018a9af6e9b81fa1839075d",
    "tree_sha": "468e17f991dd1bf938353dd5c92b1d39f45ce6d0",
}
REQUIRED_PROJECTION_BUDGETS = {
    "docs_answer_max_tokens": 800,
    "patch_context_target_tokens": 1_500,
    "patch_context_absolute_tokens": 2_000,
    "insufficient_evidence_max_tokens": 300,
}
REQUIRED_PRODUCTION_GATE = {
    "task_id": "decisive_nbo_cross_module_gate_large_001",
    "conditions": ["repo_only_strict_offline", "docatlas_bounded_direct"],
    "repeats": 3,
    "max_model_requests": 12,
    "max_serialized_input_tokens_per_request": 7_000,
    "max_repair_passes": 1,
    "max_test_invocations": 2,
    "correctness_parity_required": True,
    "median_total_token_ratio_max": 0.75,
    "median_latency_ratio_max": 1.10,
    "missing_credentials_canaries_or_usage_verdict": "INCONCLUSIVE",
    "provider_usage_source": "provider_records_only",
}
REQUIRED_BOUND_PATHS = frozenset({
    "eval/answer_quality_gate.py",
    "eval/answer_quality/docs_cases.json",
    "eval/answer_quality/patch_cases.json",
    "eval/answer_quality/adversarial_cases.json",
    "eval/answer_quality/human_review_rubric.md",
    "eval/answer_quality/human_review_selection_v1.json",
    "eval/retrieval_quality/development.json",
    "eval/retrieval_quality/holdout.json",
    "eval/retrieval_quality/adversarial.json",
    "eval/retrieval_quality/baseline_v1/summary.json",
    "eval/evidence_selection/docs_cases.json",
    "eval/evidence_selection/patch_cases.json",
    "eval/evidence_selection/adversarial_cases.json",
    "eval/evidence_selection/baseline_v1.json",
    "roadmap/43_ANSWER_QUALITY_AND_END_TO_END_TOKEN_GATE.md",
})
SUCCESS_KEYS = frozenset({
    "answer", "answer_evidence_ids", "sources", "targets", "invariants",
    "forbidden_changes", "implementation_guidance", "checks",
})
PATCH_FACT_FIELDS = (
    "invariants", "forbidden_changes", "implementation_guidance", "checks",
    "uncertainties",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError("Task 43 protocol must be an object")
    return value


def load_case_contracts(
    paths: Iterable[Path] = CASE_CONTRACT_PATHS,
) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for path in paths:
        value = load_json(path)
        if value.get("schema_version") != "task43-case-contracts-v1":
            raise ValueError(f"unsupported Task 43 case schema: {path}")
        rows = value.get("cases")
        if not isinstance(rows, list):
            raise ValueError(f"Task 43 cases must be a list: {path}")
        contracts.extend(rows)
    return contracts


def validate_protocol(
    protocol: dict[str, Any] | None = None,
    *,
    root: Path = ROOT,
) -> list[str]:
    protocol = protocol or load_protocol()
    errors: list[str] = []
    if protocol.get("schema_version") != "task43-answer-quality-protocol-v1":
        errors.append("protocol:schema_version")
    if protocol.get("phase") != "protocol_freeze":
        errors.append("protocol:phase")
    if protocol.get("provider_free") is not True:
        errors.append("protocol:provider_free")
    execution = protocol.get("execution_policy") or {}
    if execution.get("real_case_execution") != "forbidden_until_protocol_merge":
        errors.append("protocol:real_case_execution_not_locked")
    if execution.get("production_model_execution") != "deferred_operator_gate":
        errors.append("protocol:production_execution_not_deferred")
    if protocol.get("quality_gates") != REQUIRED_QUALITY_GATES:
        errors.append("protocol:quality_gates_changed")

    source_revision = protocol.get("source_revision") or {}
    if source_revision != REQUIRED_SOURCE_REVISION:
        errors.append("protocol:source_revision_changed")
    for field in ("commit_sha", "tree_sha"):
        if re.fullmatch(r"[0-9a-f]{40}", str(source_revision.get(field) or "")) is None:
            errors.append(f"protocol:source_revision:{field}")
    lower_layers = protocol.get("lower_layer_bindings") or {}
    task41_sha = str(lower_layers.get("task41_published_commit_sha") or "")
    baseline42 = load_json(root / "eval/evidence_selection/baseline_v1.json")
    if task41_sha != baseline42.get("commit_sha"):
        errors.append("protocol:task41_published_commit_sha")
    if protocol.get("projection_budgets") != REQUIRED_PROJECTION_BUDGETS:
        errors.append("protocol:projection_budgets_changed")
    if protocol.get("production_model_gate") != REQUIRED_PRODUCTION_GATE:
        errors.append("protocol:production_model_gate_changed")
    aggregation = protocol.get("aggregation_policy") or {}
    if (
        aggregation.get("docs_and_patch_must_pass_independently") is not True
        or aggregation.get("taxonomy_groups_must_be_reported") is not True
        or aggregation.get("per_case_regressions_cannot_be_hidden_by_aggregates")
            is not True
        or aggregation.get("weighted_quality_score_is_authoritative") is not False
    ):
        errors.append("protocol:aggregation_policy_changed")
    determinism = protocol.get("determinism") or {}
    if (
        determinism.get("canonical_json") is not True
        or determinism.get("candidate_order_permutation_check") is not True
        or determinism.get("raw_source_text_in_report") is not False
        or set(determinism.get("excluded_from_result_digest") or ())
            != {"latency_samples", "timestamps", "machine_identity"}
    ):
        errors.append("protocol:determinism_changed")

    bindings = protocol.get("file_bindings") or {}
    if set(bindings) != REQUIRED_BOUND_PATHS:
        errors.append("binding:path_set")
    for relative, expected in sorted(bindings.items()):
        path = root / relative
        if not path.is_file():
            errors.append(f"binding:missing:{relative}")
        elif file_sha256(path) != expected:
            errors.append(f"binding:digest_mismatch:{relative}")

    try:
        contracts = load_case_contracts(
            tuple(root / path for path in protocol.get("case_contract_files") or ())
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"contracts:load:{exc}")
        contracts = []
    errors.extend(_validate_case_contracts(contracts))
    expected_refs = _source_case_refs(root)
    actual_refs = {str(row.get("source_ref") or "") for row in contracts}
    if actual_refs != expected_refs:
        for ref in sorted(expected_refs - actual_refs):
            errors.append(f"contracts:missing_source_ref:{ref}")
        for ref in sorted(actual_refs - expected_refs):
            errors.append(f"contracts:unknown_source_ref:{ref}")

    counts = protocol.get("case_counts") or {}
    if counts.get("task39") != 16 or counts.get("task42") != 13:
        errors.append("protocol:source_case_counts")
    if counts.get("total") != len(contracts) or len(contracts) != 29:
        errors.append("protocol:total_case_count")

    errors.extend(_validate_human_review(protocol, contracts, root))
    errors.extend(_validate_timing_protocol(protocol))
    return errors


def protocol_manifest(protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    protocol = protocol or load_protocol()
    contracts = load_case_contracts(
        tuple(ROOT / path for path in protocol["case_contract_files"])
    )
    return {
        "schema_version": "task43-protocol-manifest-v1",
        "phase": protocol["phase"],
        "provider_free": protocol["provider_free"],
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "case_contract_digest": hashlib.sha256(canonical_bytes(contracts)).hexdigest(),
        "case_count": len(contracts),
        "source_case_refs": sorted(row["source_ref"] for row in contracts),
        "real_case_execution": protocol["execution_policy"]["real_case_execution"],
    }


def evaluate_projection_contract(
    projection: dict[str, Any],
    snapshot: dict[str, dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one already-produced projection without running a real fixture."""

    errors: list[str] = []
    expected_status = contract["expected_status"]
    if projection.get("status") != expected_status:
        errors.append("projection:status")
    if projection.get("kind") != contract["result_kind"]:
        errors.append("projection:kind")
    maximum = int(contract["maximum_visible_tokens"])
    declared = projection.get("estimated_tokens")
    actual = max(1, math.ceil(len(canonical_bytes(projection)) / 4))
    if not isinstance(declared, int) or declared != actual or actual > maximum:
        errors.append("projection:token_budget_or_estimate")

    if expected_status == "insufficient_evidence":
        if any(projection.get(key) for key in SUCCESS_KEYS):
            errors.append("projection:insufficient_authorizes_success")
        return _case_result(contract, actual, errors)

    sources = projection.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("citation:sources_missing")
        sources = []
    source_ids = _validate_sources(sources, snapshot, contract, errors)
    visible_text = _normalized(canonical_bytes(projection).decode("utf-8"))
    for claim in contract.get("forbidden_claims") or ():
        if _normalized(claim) in visible_text:
            errors.append(f"claim:forbidden:{claim}")
    visible_versions = {
        str(row.get("version_binding") or "") for row in sources if isinstance(row, dict)
    }
    for version in contract.get("forbidden_versions") or ():
        if str(version) in visible_versions:
            errors.append(f"citation:forbidden_version:{version}")

    if contract["result_kind"] == "docs_answer":
        _validate_docs_answer(projection, sources, source_ids, contract, errors)
    else:
        _validate_patch_context(projection, source_ids, contract, errors)
    return _case_result(contract, actual, errors)


def compare_pareto_candidate(
    candidate: dict[str, Any], baseline: dict[str, Any]
) -> list[str]:
    """Apply the frozen non-compensating Task 43 Pareto decision rule."""

    errors: list[str] = []
    for kind in ("docs_answer", "patch_context"):
        current = (candidate.get("groups") or {}).get(kind) or {}
        frozen = (baseline.get("groups") or {}).get(kind) or {}
        for metric in ("required_fact_rate", "answer_fact_coverage"):
            if float(current.get(metric, -1)) < float(frozen.get(metric, -1)):
                errors.append(f"{kind}:{metric}_regressed")
        for metric in (
            "forbidden_source_violations", "forbidden_version_violations",
            "unsupported_claim_violations",
        ):
            if int(current.get(metric, 1)) > int(frozen.get(metric, 0)):
                errors.append(f"{kind}:{metric}_regressed")
        if float(current.get("citation_validity_rate", 0)) < 1.0:
            errors.append(f"{kind}:citation_validity_regressed")
        if float(current.get("insufficient_false_success_rate", 1)) > float(
            frozen.get("insufficient_false_success_rate", 0)
        ):
            errors.append(f"{kind}:insufficient_false_success_regressed")
        if float(current.get("median_visible_tokens", math.inf)) > float(
            frozen.get("median_visible_tokens", math.inf)
        ):
            errors.append(f"{kind}:median_visible_tokens_regressed")
        if float(current.get("retrieval_projection_p95_ms", math.inf)) > (
            float(frozen.get("retrieval_projection_p95_ms", 0)) * 1.10
        ):
            errors.append(f"{kind}:retrieval_projection_p95_latency_regressed")

    holdout = candidate.get("holdout") or {}
    frozen_holdout = baseline.get("holdout") or {}
    for metric in ("recall@5", "answer_fact_coverage"):
        if float(holdout.get(metric, -1)) < float(frozen_holdout.get(metric, -1)):
            errors.append(f"holdout:{metric}_regressed")
    baseline_cases = baseline.get("case_gates") or {}
    candidate_cases = candidate.get("case_gates") or {}
    for case_id, frozen in baseline_cases.items():
        current = candidate_cases.get(case_id)
        if current is None:
            errors.append(f"{case_id}:missing_case")
        elif frozen.get("passed") is True and current.get("passed") is not True:
            errors.append(f"{case_id}:protected_case_regressed")
    return errors


def _validate_case_contracts(contracts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    refs: set[str] = set()
    for index, row in enumerate(contracts):
        prefix = f"contracts:{index}"
        contract_id = row.get("contract_id")
        source_ref = row.get("source_ref")
        if not isinstance(contract_id, str) or not contract_id:
            errors.append(f"{prefix}:contract_id")
        elif contract_id in ids:
            errors.append(f"contracts:duplicate_id:{contract_id}")
        else:
            ids.add(contract_id)
        if not isinstance(source_ref, str) or not source_ref:
            errors.append(f"{prefix}:source_ref")
        elif source_ref in refs:
            errors.append(f"contracts:duplicate_source_ref:{source_ref}")
        else:
            refs.add(source_ref)
        if row.get("taxonomy") not in ALLOWED_TAXONOMIES:
            errors.append(f"{prefix}:taxonomy")
        if row.get("result_kind") not in {"docs_answer", "patch_context"}:
            errors.append(f"{prefix}:result_kind")
        if row.get("expected_status") not in {"ok", "insufficient_evidence"}:
            errors.append(f"{prefix}:expected_status")
        maximum = row.get("maximum_visible_tokens")
        expected_maximum = 800 if row.get("result_kind") == "docs_answer" else 1_500
        if maximum != expected_maximum:
            errors.append(f"{prefix}:maximum_visible_tokens")
        for field in (
            "required_answer_facts", "acceptable_evidence", "forbidden_claims",
            "forbidden_versions", "exact_identifiers", "required_public_commands",
        ):
            if not isinstance(row.get(field), list):
                errors.append(f"{prefix}:{field}")
        if not isinstance(row.get("required_patch_fields"), dict):
            errors.append(f"{prefix}:required_patch_fields")
    return errors


def _source_case_refs(root: Path) -> set[str]:
    refs: set[str] = set()
    for task, groups in EXPECTED_SOURCE_REFS.items():
        for group, default_path in groups.items():
            path = root / default_path.relative_to(ROOT)
            value = load_json(path)
            for row in value["cases"]:
                case_id = row["id"] if task == "task39" else row["case_id"]
                refs.add(f"{task}:{group}:{case_id}")
    return refs


def _validate_human_review(
    protocol: dict[str, Any], contracts: list[dict[str, Any]], root: Path
) -> list[str]:
    errors: list[str] = []
    config = protocol.get("human_review") or {}
    selection_path = root / str(config.get("selection_path") or "")
    rubric_path = root / str(config.get("rubric_path") or "")
    if not selection_path.is_file() or not rubric_path.is_file():
        return ["human_review:artifact_missing"]
    selection = load_json(selection_path)
    rows = selection.get("cases") or []
    selected = [row.get("contract_id") for row in rows if isinstance(row, dict)]
    known = {row.get("contract_id") for row in contracts}
    if len(selected) != config.get("required_case_count") or len(set(selected)) != len(selected):
        errors.append("human_review:selection_count")
    if any(contract_id not in known for contract_id in selected):
        errors.append("human_review:unknown_contract")
    dimensions = set(selection.get("dimensions") or [])
    if dimensions != set(config.get("required_dimensions") or []):
        errors.append("human_review:dimensions")
    return errors


def _validate_timing_protocol(protocol: dict[str, Any]) -> list[str]:
    timing = protocol.get("timing") or {}
    errors: list[str] = []
    if timing.get("warmup_repeats_per_case") != 5:
        errors.append("timing:warmup_repeats")
    if timing.get("measured_repeats_per_case") != 25:
        errors.append("timing:measured_repeats")
    if timing.get("candidate_to_baseline_p95_ratio_max") != 1.10:
        errors.append("timing:p95_ratio")
    if timing.get("raw_measurements_in_deterministic_digest") is not False:
        errors.append("timing:digest_separation")
    return errors


def _validate_sources(
    sources: list[Any],
    snapshot: dict[str, dict[str, Any]],
    contract: dict[str, Any],
    errors: list[str],
) -> set[str]:
    source_ids: set[str] = set()
    allowed = set(contract.get("acceptable_evidence") or [])
    found_paths: set[str] = set()
    for row in sources:
        if not isinstance(row, dict):
            errors.append("citation:source_not_object")
            continue
        evidence_id = str(row.get("evidence_id") or "")
        bound = snapshot.get(evidence_id)
        if not evidence_id or not isinstance(bound, dict):
            errors.append("citation:unknown_evidence_id")
            continue
        source_ids.add(evidence_id)
        if row.get("content_sha256") != bound.get("content_sha256"):
            errors.append("citation:content_hash_mismatch")
        for key in ("path_or_url", "section", "snippet", "version_binding"):
            if key in row and row.get(key) != bound.get(key):
                errors.append(f"citation:{key}_mismatch")
        path = str(row.get("path_or_url") or "")
        if path in allowed:
            found_paths.add(path)
        elif allowed:
            errors.append(f"citation:unacceptable_evidence:{path}")
    for path in sorted(allowed - found_paths):
        errors.append(f"citation:acceptable_evidence_missing:{path}")
    return source_ids


def _validate_docs_answer(
    projection: dict[str, Any],
    sources: list[Any],
    source_ids: set[str],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    answer = str(projection.get("answer") or "")
    answer_normalized = _normalized(answer)
    for fact in contract.get("required_answer_facts") or ():
        if _normalized(fact) not in answer_normalized:
            errors.append(f"answer:required_fact_missing:{fact}")
    for identifier in contract.get("exact_identifiers") or ():
        pattern = rf"(?<!\w){re.escape(str(identifier))}(?!\w)"
        if re.search(pattern, answer, re.IGNORECASE | re.UNICODE) is None:
            errors.append(f"answer:exact_identifier_missing:{identifier}")
    refs = projection.get("answer_evidence_ids")
    if not isinstance(refs, list) or not refs or any(ref not in source_ids for ref in refs):
        errors.append("answer:evidence_ids_invalid")
        return
    snippets = {
        str(row.get("evidence_id")): _normalized(row.get("snippet") or "")
        for row in sources if isinstance(row, dict)
    }
    cited = [snippets.get(str(ref), "") for ref in refs]
    claims = [
        _normalized(value) for value in re.split(r"(?<=[.!?])\s+|\n+", answer)
        if _normalized(value)
    ]
    for claim in claims:
        if not any(claim in snippet for snippet in cited):
            errors.append("answer:unsupported_claim")


def _validate_patch_context(
    projection: dict[str, Any],
    source_ids: set[str],
    contract: dict[str, Any],
    errors: list[str],
) -> None:
    visible_projection = canonical_bytes(projection).decode("utf-8")
    for identifier in contract.get("exact_identifiers") or ():
        pattern = rf"(?<!\w){re.escape(str(identifier))}(?!\w)"
        if re.search(pattern, visible_projection, re.IGNORECASE | re.UNICODE) is None:
            errors.append(f"patch:exact_identifier_missing:{identifier}")
    for field, required in (contract.get("required_patch_fields") or {}).items():
        visible = _normalized(canonical_bytes(projection.get(field)).decode("utf-8"))
        for fact in required:
            if _normalized(fact) not in visible:
                errors.append(f"patch:{field}:required_fact_missing:{fact}")
    checks = _normalized(canonical_bytes(projection.get("checks")).decode("utf-8"))
    for command in contract.get("required_public_commands") or ():
        if _normalized(command) not in checks:
            errors.append(f"patch:required_command_missing:{command}")
    for field in PATCH_FACT_FIELDS:
        for item in _dict_items(projection.get(field)):
            refs = item.get("evidence_ids")
            if not isinstance(refs, list) or not refs or any(ref not in source_ids for ref in refs):
                errors.append(f"patch:{field}:evidence_ids_invalid")


def _dict_items(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if any(key in value for key in ("claim", "text", "rule", "command", "description")):
            yield value
        else:
            for child in value.values():
                yield from _dict_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _dict_items(child)


def _normalized(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _case_result(
    contract: dict[str, Any], actual_tokens: int, errors: list[str]
) -> dict[str, Any]:
    return {
        "contract_id": contract["contract_id"],
        "source_ref": contract["source_ref"],
        "result_kind": contract["result_kind"],
        "estimated_tokens": actual_tokens,
        "errors": errors,
        "passed": not errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-protocol", action="store_true", required=True)
    parser.add_argument("--print-manifest", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_protocol()
    output = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "manifest": protocol_manifest() if args.print_manifest and not errors else None,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
