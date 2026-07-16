#!/usr/bin/env python3
"""Execute the merged Task 43 provider-free answer-quality protocol."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.action_packet import (
    build_action_packet,
    validate_action_packet,
)
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer,
    project_patch_context,
    sanitized_projection_manifest,
    validate_model_visible_projection,
)
from eval.answer_quality_gate import (
    DATA_ROOT,
    ROOT,
    canonical_bytes,
    compare_pareto_candidate,
    evaluate_projection_contract,
    file_sha256,
    load_case_contracts,
    load_json,
    load_protocol,
    validate_protocol,
)
from eval.evidence_selection_quality import evaluate as evaluate_task42
from eval.retrieval_quality_baseline import (
    DATA_ROOT as TASK39_DATA,
    RETRIEVAL_CONFIG,
    SPLITS,
    compare_to_baseline,
    run_baseline,
)


PROTOCOL_MERGE_COMMIT_SHA = "bd516eb0eb426ccc5233cd08347dcb8218f73657"
TASK39_BASELINE = TASK39_DATA / "baseline_v1" / "summary.json"
TASK42_DATA = ROOT / "eval" / "evidence_selection"
TASK43_BASELINE = DATA_ROOT / "baseline_v1.json"
PRODUCT_CODE_PATHS = (
    "docmancer/core/sqlite_store.py",
    "docmancer/docs/application/evidence_selection.py",
    "docmancer/docs/application/action_packet.py",
    "docmancer/docs/application/model_visible_projection.py",
    "docmancer/docs/interfaces/mcp/context_tools.py",
)


def run(output_dir: Path) -> dict[str, Any]:
    protocol = load_protocol()
    protocol_errors = validate_protocol(protocol)
    if protocol_errors:
        raise ValueError("Task 43 protocol validation failed: " + ", ".join(protocol_errors))
    output_dir.mkdir(parents=True, exist_ok=True)
    contracts = {row["source_ref"]: row for row in load_case_contracts()}

    with tempfile.TemporaryDirectory(prefix="docatlas-task43-lower-") as temporary:
        task39_current = run_baseline(Path(temporary) / "task39")
    task39_errors = compare_to_baseline(task39_current, load_json(TASK39_BASELINE))
    task42_report = evaluate_task42()

    results: list[dict[str, Any]] = []
    timing_samples: dict[str, list[float]] = {}
    review_inputs: dict[str, dict[str, Any]] = {}
    integrity_inputs: dict[str, tuple[dict[str, Any], dict[str, dict[str, Any]], int]] = {}

    with tempfile.TemporaryDirectory(prefix="docatlas-task43-quality-") as temporary:
        store = _build_task39_store(Path(temporary))
        for split in SPLITS:
            dataset = load_json(TASK39_DATA / f"{split}.json")
            for case in dataset["cases"]:
                source_ref = f"task39:{split}:{case['id']}"
                contract = contracts[source_ref]
                measured = _measure_case(
                    lambda case=case: _task39_projection(store, case), protocol
                )
                case_result = _evaluate_measured_case(contract, measured)
                results.append(case_result)
                timing_samples[contract["contract_id"]] = measured["samples_ms"]
                _record_auxiliary_inputs(
                    contract, measured, review_inputs, integrity_inputs
                )

    for group in ("docs_cases", "patch_cases", "adversarial_cases"):
        dataset = load_json(TASK42_DATA / f"{group}.json")
        for case in dataset["cases"]:
            source_ref = f"task42:{group}:{case['case_id']}"
            contract = contracts[source_ref]
            measured = _measure_case(
                lambda case=case: _task42_projection(case), protocol
            )
            case_result = _evaluate_measured_case(contract, measured)
            results.append(case_result)
            timing_samples[contract["contract_id"]] = measured["samples_ms"]
            _record_auxiliary_inputs(contract, measured, review_inputs, integrity_inputs)

    results.sort(key=lambda row: row["contract_id"])
    measured_groups = {
        kind: _aggregate_group(
            [row for row in results if row["result_kind"] == kind], timing_samples
        )
        for kind in ("docs_answer", "patch_context")
    }
    groups = {
        kind: {
            key: value
            for key, value in row.items()
            if key != "retrieval_projection_p95_ms"
        }
        for kind, row in measured_groups.items()
    }
    taxonomy_groups = {
        kind: {
            taxonomy: {
                key: value
                for key, value in _aggregate_group(
                    [row for row in results if row["result_kind"] == kind
                     and row["taxonomy"] == taxonomy],
                    timing_samples,
                ).items()
                if key != "retrieval_projection_p95_ms"
            }
            for taxonomy in sorted({
                row["taxonomy"] for row in results if row["result_kind"] == kind
            })
        }
        for kind in ("docs_answer", "patch_context")
    }
    case_gates = {
        row["contract_id"]: {
            "source_ref": row["source_ref"],
            "passed": row["passed"],
            "errors": row["errors"],
            "estimated_tokens": row["estimated_tokens"],
        }
        for row in results
    }
    holdout_rows = [
        row for row in results if row["source_ref"].startswith("task39:holdout:")
    ]
    holdout = {
        "recall@5": task39_current["splits"]["holdout"]["recall@5"],
        "answer_fact_coverage": _fact_coverage(holdout_rows),
    }
    integrity_gate = _run_integrity_mutation_gate(integrity_inputs)
    lower_layers = {
        "task39": {
            "status": "PASS" if not task39_errors else "FAIL",
            "errors": task39_errors,
            "deterministic_result_digest": task39_current[
                "deterministic_result_digest"
            ],
        },
        "task42": {
            "status": task42_report["verdict"],
            "correctness_gate": task42_report["correctness_gate"],
            "task41_gate": task42_report["task41_gate"],
            "candidate_order_permutation_gate": (
                "PASS"
                if all(
                    row["checks"]["deterministic"]
                    for row in task42_report["results"]
                )
                else "FAIL"
            ),
        },
    }
    automated_pass = (
        not task39_errors
        and task42_report["verdict"] == "PASS"
        and all(row["passed"] for row in results)
        and integrity_gate["status"] == "PASS"
    )
    stable = {
        "schema_version": "task43-provider-free-result-v1",
        "provider_free": True,
        "protocol_sha256": file_sha256(DATA_ROOT / "protocol_v1.lock.json"),
        "protocol_merge_commit_sha": PROTOCOL_MERGE_COMMIT_SHA,
        "source_revision": protocol["source_revision"],
        "product_code_digests": {
            path: file_sha256(ROOT / path) for path in PRODUCT_CODE_PATHS
        },
        "lower_layers": lower_layers,
        "groups": groups,
        "taxonomy_groups": taxonomy_groups,
        "holdout": holdout,
        "case_gates": case_gates,
        "integrity_mutation_gate": integrity_gate,
        "automated_quality_gate": "PASS" if automated_pass else "FAIL",
        "human_review_gate": "INCONCLUSIVE",
        "production_model_gate": "INCONCLUSIVE",
        "results": results,
    }
    stable_digest = hashlib.sha256(canonical_bytes(stable)).hexdigest()
    candidate_baseline = {
        "schema_version": "task43-answer-quality-baseline-v1",
        "protocol_sha256": stable["protocol_sha256"],
        "source_revision": stable["source_revision"],
        "deterministic_result_digest": stable_digest,
        "product_code_digests": stable["product_code_digests"],
        "groups": copy.deepcopy(measured_groups),
        "holdout": holdout,
        "case_gates": case_gates,
    }
    baseline = load_json(TASK43_BASELINE)
    if (
        baseline.get("protocol_sha256") != stable["protocol_sha256"]
        or baseline.get("source_revision") != stable["source_revision"]
    ):
        raise ValueError("Task 43 baseline is not bound to the frozen protocol")
    identity_candidate = (
        candidate_baseline["product_code_digests"]
        == baseline.get("product_code_digests")
    )
    if identity_candidate:
        for kind in ("docs_answer", "patch_context"):
            candidate_baseline["groups"][kind][
                "retrieval_projection_p95_ms"
            ] = baseline["groups"][kind]["retrieval_projection_p95_ms"]
    pareto_errors = compare_pareto_candidate(candidate_baseline, baseline)
    report = {
        **stable,
        "deterministic_result_digest": stable_digest,
        "frozen_baseline_pareto_gate": {
            "status": "PASS" if not pareto_errors else "FAIL",
            "errors": pareto_errors,
        },
        "provider_free_verdict": (
            "INCONCLUSIVE" if automated_pass else "FAIL"
        ),
        "verdict_reason": (
            "human_review_pending" if automated_pass else "automated_gate_failed"
        ),
    }
    timing = _timing_artifact(
        protocol, timing_samples, measured_groups, baseline["groups"],
        identity_candidate,
    )
    human_inputs = _human_review_artifact(protocol, review_inputs, stable_digest)
    _write_json(output_dir / "baseline_v1.json", baseline)
    _write_json(output_dir / "result_v1.json", report)
    _write_json(output_dir / "latency_v1.json", timing)
    _write_json(output_dir / "human_review_inputs_v1.json", human_inputs)
    return report


def _build_task39_store(root: Path) -> SQLiteStore:
    corpus = load_json(TASK39_DATA / "corpus.json")
    store = SQLiteStore(root / "index.db", root / "extracted")
    store.add_documents(
        [
            Document(
                source=row["source"],
                content=row["content"],
                metadata={
                    "title": row["title"],
                    "authority": row["authority"],
                    "version": row["version"],
                    "corpus_id": corpus["corpus_id"],
                },
            )
            for row in corpus["documents"]
        ],
        recreate=True,
    )
    return store


def _task39_projection(
    store: SQLiteStore, case: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    chunks = store.query(
        str(case["query"]),
        limit=RETRIEVAL_CONFIG["candidate_limit"],
        budget=RETRIEVAL_CONFIG["candidate_budget"],
    )
    items = [
        {
            "source": chunk.source,
            "title": chunk.metadata.get("title"),
            "content": chunk.text,
            "version": chunk.metadata.get("version", "unversioned"),
        }
        for chunk in chunks[: RETRIEVAL_CONFIG["selected_limit"]]
    ]
    retrieval: dict[str, Any] = {
        "status": "success" if items else "unavailable",
        "answer_available": bool(items),
    }
    if items:
        retrieval["primary_snippet"] = items[0]
        retrieval["supporting_snippets"] = items[1:]
    projection, snapshot = project_docs_answer(
        question=str(case["query"]),
        retrieval=retrieval,
        max_tokens=RETRIEVAL_CONFIG["projection_budget"],
    )
    errors = validate_model_visible_projection(
        projection,
        snapshot=snapshot,
        max_tokens=(
            300 if projection.get("status") == "insufficient_evidence" else 800
        ),
    )
    return projection, snapshot, errors


def _task42_projection(
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    maximum = int(case["maximum_visible_tokens"])
    candidates = [_host_bind_candidate(item) for item in case["candidates"]]
    trust = {
        "sources": {
            "rejected": [
                {"source": source} for source in case.get("forbidden_sources", [])
            ]
        }
    }
    errors: list[str] = []
    if case["result_kind"] == "docs_answer":
        projection, snapshot = project_docs_answer(
            question=case["question"],
            retrieval={
                "status": "success",
                "answer_available": True,
                "context_pack": candidates,
                "trust_contract": trust,
                "docs_exactness": "exact" if case.get("exact_version") else None,
                "requested_version": case.get("exact_version"),
                "required_evidence_paths": case.get("required_evidence_paths", []),
                "required_target_paths": case.get("required_target_paths", []),
                "public_requirements": case.get("required_facts", []),
                "project_identity": case.get("project_identity"),
                "module_id": case.get("module_id"),
            },
            max_tokens=maximum,
        )
    else:
        packet = build_action_packet(
            question=case["question"],
            context_pack=candidates,
            trust_contract=trust,
            max_tokens=maximum,
            project_path=case.get("project_path"),
            required_evidence_paths=case.get("required_evidence_paths", []),
            required_target_paths=case.get("required_target_paths", []),
            public_requirements=case.get("required_facts", []),
            exact_version=case.get("exact_version"),
            project_identity=case.get("project_identity"),
            module_id=case.get("module_id"),
        )
        errors.extend(
            validate_action_packet(
                packet,
                evidence_items=candidates,
                max_tokens=maximum,
                project_path=case.get("project_path"),
            )
        )
        projection, snapshot = project_patch_context(
            packet=packet, evidence_items=candidates, max_tokens=maximum
        )
    errors.extend(
        validate_model_visible_projection(
            projection,
            snapshot=snapshot,
            max_tokens=(
                300
                if projection.get("status") == "insufficient_evidence"
                else maximum
            ),
        )
    )
    return projection, snapshot, errors


def _measure_case(
    callback: Callable[
        [], tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]
    ],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    timing = protocol["timing"]
    for _ in range(int(timing["warmup_repeats_per_case"])):
        callback()
    samples: list[float] = []
    first: tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]] | None = None
    for _ in range(int(timing["measured_repeats_per_case"])):
        started = time.perf_counter_ns()
        current = callback()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
        if first is None:
            first = current
        elif canonical_bytes(current[0]) != canonical_bytes(first[0]):
            raise ValueError("Task 43 projection is not deterministic across timing repeats")
    assert first is not None
    return {
        "projection": first[0],
        "snapshot": first[1],
        "validation_errors": first[2],
        "samples_ms": samples,
    }


def _evaluate_measured_case(
    contract: dict[str, Any], measured: dict[str, Any]
) -> dict[str, Any]:
    projection = measured["projection"]
    snapshot = measured["snapshot"]
    primitive_contract = contract
    if contract["result_kind"] == "patch_context":
        primitive_contract = {**contract, "acceptable_evidence": []}
    result = evaluate_projection_contract(projection, snapshot, primitive_contract)
    errors = [
        *[f"canonical_validator:{error}" for error in measured["validation_errors"]],
        *result["errors"],
    ]
    if contract["result_kind"] == "patch_context" and projection.get("status") == "ok":
        errors.extend(_validate_patch_source_paths(projection, snapshot, contract))
    required_total = _required_item_count(contract)
    required_missing = sum("required_fact_missing" in error for error in errors)
    required_missing += sum("required_command_missing" in error for error in errors)
    return {
        "contract_id": contract["contract_id"],
        "source_ref": contract["source_ref"],
        "taxonomy": contract["taxonomy"],
        "result_kind": contract["result_kind"],
        "expected_status": contract["expected_status"],
        "status": projection.get("status"),
        "estimated_tokens": projection.get("estimated_tokens"),
        "projection_digest": hashlib.sha256(canonical_bytes(projection)).hexdigest(),
        "source_manifest": sanitized_projection_manifest(snapshot),
        "required_total": required_total,
        "required_covered": max(0, required_total - required_missing),
        "errors": sorted(set(errors)),
        "passed": not errors,
    }


def _validate_patch_source_paths(
    projection: dict[str, Any],
    snapshot: dict[str, dict[str, Any]],
    contract: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    allowed = set(contract.get("acceptable_evidence") or [])
    found: set[str] = set()
    for source in projection.get("sources") or []:
        if not isinstance(source, dict):
            continue
        evidence_id = str(source.get("evidence_id") or "")
        bound = snapshot.get(evidence_id) or {}
        path = str(source.get("path") or source.get("path_or_url") or "")
        bound_path = str(bound.get("path") or bound.get("path_or_url") or "")
        if path != bound_path:
            errors.append("citation:path_mismatch")
        if path in allowed:
            found.add(path)
        elif allowed:
            errors.append(f"citation:unacceptable_evidence:{path}")
    for path in sorted(allowed - found):
        errors.append(f"citation:acceptable_evidence_missing:{path}")
    return errors


def _record_auxiliary_inputs(
    contract: dict[str, Any],
    measured: dict[str, Any],
    review_inputs: dict[str, dict[str, Any]],
    integrity_inputs: dict[
        str, tuple[dict[str, Any], dict[str, dict[str, Any]], int]
    ],
) -> None:
    selection = load_json(DATA_ROOT / "human_review_selection_v1.json")
    selected = {row["contract_id"] for row in selection["cases"]}
    if contract["contract_id"] in selected:
        review_inputs[contract["contract_id"]] = {
            "contract_id": contract["contract_id"],
            "source_ref": contract["source_ref"],
            "projection": measured["projection"],
            "evidence_manifest": sanitized_projection_manifest(measured["snapshot"]),
        }
    if (
        contract["result_kind"] == "patch_context"
        and measured["projection"].get("status") == "ok"
        and "patch_context" not in integrity_inputs
    ):
        integrity_inputs["patch_context"] = (
            measured["projection"], measured["snapshot"],
            int(contract["maximum_visible_tokens"]),
        )
    if (
        contract["result_kind"] == "docs_answer"
        and measured["projection"].get("status") == "ok"
        and "docs_answer" not in integrity_inputs
    ):
        integrity_inputs["docs_answer"] = (
            measured["projection"], measured["snapshot"],
            int(contract["maximum_visible_tokens"]),
        )


def _run_integrity_mutation_gate(
    inputs: dict[str, tuple[dict[str, Any], dict[str, dict[str, Any]], int]]
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for kind in ("docs_answer", "patch_context"):
        if kind not in inputs:
            checks[kind] = {"passed": False, "errors": ["successful_fixture_missing"]}
            continue
        projection, snapshot, maximum = inputs[kind]
        tampered = copy.deepcopy(projection)
        source = tampered["sources"][0]
        path_key = "path" if "path" in source else "path_or_url"
        source[path_key] = "tampered/foreign-source.md"
        errors = validate_model_visible_projection(
            tampered, snapshot=snapshot, max_tokens=maximum
        )
        expected_error = (
            f"projection source {path_key} does not match the internal snapshot"
        )
        checks[kind] = {
            "passed": expected_error in errors,
            "mutation": f"sources[0].{path_key}",
            "expected_validator_error": expected_error,
            "validator_errors": errors,
        }
    passed = all(check.get("passed") is True for check in checks.values())
    return {"status": "PASS" if passed else "FAIL", "checks": checks}


def _aggregate_group(
    rows: list[dict[str, Any]], timing_samples: dict[str, list[float]]
) -> dict[str, Any]:
    successful = [row for row in rows if row["expected_status"] == "ok"]
    citation_valid = [
        row for row in successful
        if not any(
            error.startswith(("citation:", "answer:evidence_ids", "patch:"))
            and "required_fact_missing" not in error
            and "required_command_missing" not in error
            for error in row["errors"]
        )
    ]
    insufficient = [
        row for row in rows if row["expected_status"] == "insufficient_evidence"
    ]
    samples = [
        value for row in rows for value in timing_samples[row["contract_id"]]
    ]
    return {
        "cases": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "required_fact_rate": _required_pass_rate(rows),
        "answer_fact_coverage": _fact_coverage(rows),
        "forbidden_source_violations": _error_count(rows, "citation:unacceptable"),
        "forbidden_version_violations": _error_count(rows, "forbidden_version"),
        "unsupported_claim_violations": _error_count(rows, "unsupported_claim"),
        "citation_validity_rate": (
            len(citation_valid) / len(successful) if successful else 1.0
        ),
        "insufficient_false_success_rate": (
            sum(row["status"] != "insufficient_evidence" for row in insufficient)
            / len(insufficient)
            if insufficient else 0.0
        ),
        "median_visible_tokens": statistics.median(
            int(row["estimated_tokens"]) for row in rows
        ),
        "retrieval_projection_p95_ms": _percentile(samples, 0.95),
    }


def _timing_artifact(
    protocol: dict[str, Any],
    samples: dict[str, list[float]],
    groups: dict[str, Any],
    baseline_groups: dict[str, Any],
    identity_candidate: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "task43-latency-observation-v1",
        "protocol_sha256": file_sha256(DATA_ROOT / "protocol_v1.lock.json"),
        "identity_candidate": identity_candidate,
        "warmup_repeats_per_case": protocol["timing"]["warmup_repeats_per_case"],
        "measured_repeats_per_case": protocol["timing"]["measured_repeats_per_case"],
        "machine_identity": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "samples_ms": samples,
        "groups": {
            kind: {
                "baseline_p95_ms": baseline_groups[kind][
                    "retrieval_projection_p95_ms"
                ],
                "candidate_p95_ms": row["retrieval_projection_p95_ms"],
                "ratio": (
                    row["retrieval_projection_p95_ms"]
                    / baseline_groups[kind]["retrieval_projection_p95_ms"]
                ),
                "status": (
                    "BASELINE_IDENTITY_OBSERVATION"
                    if identity_candidate else "CANDIDATE_OBSERVATION"
                ),
            }
            for kind, row in groups.items()
        },
    }


def _human_review_artifact(
    protocol: dict[str, Any],
    review_inputs: dict[str, dict[str, Any]],
    result_digest: str,
) -> dict[str, Any]:
    selection = load_json(DATA_ROOT / "human_review_selection_v1.json")
    ordered = [review_inputs[row["contract_id"]] for row in selection["cases"]]
    return {
        "schema_version": "task43-human-review-inputs-v1",
        "protocol_sha256": file_sha256(DATA_ROOT / "protocol_v1.lock.json"),
        "deterministic_result_digest": result_digest,
        "rubric_path": protocol["human_review"]["rubric_path"],
        "review_status": "PENDING_HUMAN_REVIEW",
        "cases": ordered,
    }


def _host_bind_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    item = dict(raw)
    display = str(
        item.get("display_text") or item.get("code") or item.get("snippet")
        or item.get("content") or ""
    )
    item.setdefault("content", display)
    if item.get("stable_chunk_id"):
        item.setdefault(
            "display_content_hash", hashlib.sha256(display.encode()).hexdigest()
        )
    return item


def _required_item_count(contract: dict[str, Any]) -> int:
    return (
        len(contract.get("required_answer_facts") or [])
        + sum(len(values) for values in (contract.get("required_patch_fields") or {}).values())
        + len(contract.get("required_public_commands") or [])
    )


def _required_pass_rate(rows: list[dict[str, Any]]) -> float:
    applicable = [row for row in rows if row["required_total"] > 0]
    return (
        sum(row["required_covered"] == row["required_total"] for row in applicable)
        / len(applicable)
        if applicable else 1.0
    )


def _fact_coverage(rows: list[dict[str, Any]]) -> float:
    total = sum(row["required_total"] for row in rows)
    return sum(row["required_covered"] for row in rows) / total if total else 1.0


def _error_count(rows: list[dict[str, Any]], fragment: str) -> int:
    return sum(fragment in error for row in rows for error in row["errors"])


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(args.output_dir)
    print(json.dumps({
        "provider_free_verdict": report["provider_free_verdict"],
        "automated_quality_gate": report["automated_quality_gate"],
        "human_review_gate": report["human_review_gate"],
    }, sort_keys=True))
    return 0 if report["provider_free_verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
