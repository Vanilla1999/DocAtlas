"""Read existing acceptance artifacts with the standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


_FOCUSED_CASE_IDS = (
    "v2-paraphrase-cache-reset",
    "v2-natural-architecture",
    "v2-natural-request-flow",
)


def _focused_fields(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value[key] for key in keys if key in value} if isinstance(value, dict) else {}


def _focused_bound(value: Any, depth: int = 0) -> Any:
    """Bound only private log output; retain counts and hashes when shortened."""
    if depth >= 12:
        return {"log_omitted": "depth"}
    if isinstance(value, str):
        if len(value) <= 512:
            return value
        return {"prefix": value[:512], "characters": len(value),
                "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
    if isinstance(value, list):
        rows = [_focused_bound(row, depth + 1) for row in value[:32]]
        return {"items": rows, "report_count": len(value), "log_omitted": max(0, len(value) - len(rows))}
    if isinstance(value, dict):
        return {key: _focused_bound(item, depth + 1) for key, item in value.items()}
    return value if value is None or type(value) in (int, float, bool) else {"log_omitted": "type"}


def _focused_qualification(row: dict[str, Any]) -> dict[str, Any]:
    observed = row.get("observed_candidate") or {}
    observed = observed if isinstance(observed, dict) else {}
    reference = observed.get("source_reference") or {}
    reference = reference if isinstance(reference, dict) else {}
    source = reference.get("source") or {}
    source = source if isinstance(source, dict) else {}
    root_references = observed.get("root_references")
    root_references = root_references if isinstance(root_references, list) else []
    return {
        **_focused_fields(row, ("stable_chunk_id", "document_id", "parent_logical_id", "query_id", "outcome", "reason")),
        "qualification": _focused_fields(row.get("observed_qualification"), (
            "query_text", "query_origin", "relation", "reference_body_query", "query_terms", "exact_terms",
            "body_matched_terms", "matched_terms", "matched_term_count", "match_ratio",
            "missing_exact_terms", "missing_parent_exact_terms", "heading_context_used", "table_context_used",
            "reference_visible_span", "lexical_score", "qualification_route", "admission_only", "context_only",
        )),
        "candidate": {
            **_focused_fields(observed, ("window_sha256", "window_characters", "root_catalog_complete", "root_reference_count")),
            "lexical_match": _focused_fields(observed.get("candidate_lexical_match"), (
                "mode", "query_terms", "matched_terms", "exact_terms", "missing_exact_terms",
                "query_term_count", "matched_term_count", "match_ratio", "bm25_cost", "lexical_score",
            )),
            "source": {
                **_focused_fields(source, ("document_id", "canonical_path", "content_sha256")),
                "scope": _focused_fields(source.get("scope"), ("project_id", "version", "snapshot_id")),
            },
            "member_binding": _focused_fields(reference.get("member_binding"), (
                "generation_id", "catalog_sha256", "catalog_entry_hash", "document_id",
                "content_sha256", "project_identity", "doc_scope", "module_path", "source_class",
            )),
            **_focused_fields(reference, ("char_start", "char_end")),
            "root_references": [
                {**_focused_fields(ref, ("role", "state", "reason")),
                 "mention": _focused_fields(ref.get("mention"), ("text", "syntax_role", "explicit", "start", "end"))}
                for ref in root_references if isinstance(ref, dict)
            ],
        },
    }


def print_focused_stage_records(report: dict[str, Any], emit=print) -> None:
    """Expose three existing same-call records; never run or rescore a case."""
    results = report.get("results")
    production = report.get("production_results")
    results = results if isinstance(results, list) else []
    production = production if isinstance(production, list) else []
    for case_id in _FOCUSED_CASE_IDS:
        scored = [row for row in results if isinstance(row, dict) and row.get("id") == case_id]
        observed = [row for row in production if isinstance(row, dict) and row.get("case_id") == case_id]
        case = scored[0] if len(scored) == 1 else {}
        actual = observed[0] if len(observed) == 1 else {}
        payload = actual.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        diagnostics = case.get("diagnostics")
        diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
        outcomes = diagnostics.get("qualification_outcomes")
        outcomes = outcomes if isinstance(outcomes, list) else []
        sources = payload.get("sources")
        sources = sources if isinstance(sources, list) else []
        record = {
            "case_id": case_id, "run_mode": report.get("run_mode"),
            "record_counts": {"evaluator": len(scored), "production": len(observed)},
            "question": actual.get("question"),
            "verdict": _focused_fields(case, (
                "root_cause", "semantic_useful", "lookup_covered", "lookup_required", "false_full_coverage",
                "returned_source_count", "evaluator_verified_component_coverage", "hard_gates", "obligations",
            )),
            "payload": {
                **_focused_fields(payload, (
                    "kind", "status", "reason_code", "support_status", "context_available",
                    "answer_supported", "answer_available", "edit_ready", "covered_query_ids", "missing_query_ids",
                )),
                "source_count": len(sources),
                "sources": [
                    {**_focused_fields(source, (
                        "evidence_id", "path_or_url", "project_identity", "authority", "scope", "catalog_role",
                        "source_identity", "source_content_hash", "line_start", "line_end", "char_start", "char_end",
                    )),
                     "snippet_sha256": hashlib.sha256(source["snippet"].encode("utf-8")).hexdigest()
                     if isinstance(source.get("snippet"), str) else None}
                    for source in sources if isinstance(source, dict)
                ],
            },
            "stages": {
                "diagnostics_present": bool(diagnostics),
                **_focused_fields(diagnostics, (
                    "stage_status", "delivery_decision", "delivery_observations", "observer_counts", "planned_query_ids",
                    "retrieved_candidates", "retrieved_candidate_ids", "qualification_rejections",
                    "pre_projection_qualified_ids", "ranked_candidate_ids", "selected_candidate_ids",
                    "considered_variants", "projection_rejections", "final_visible_evidence_ids",
                )),
                "qualification_outcomes": [
                    _focused_qualification(row) for row in outcomes if isinstance(row, dict)
                ],
            },
            "claim_boundary": "existing_same_call_report_diagnostics_not_new_runtime_or_selection_proof",
        }
        emit("V2_FOCUSED_STAGE " + json.dumps(_focused_bound(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _focused_items(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return value["items"]
    return []


def _delivery_window_summary(value: Any) -> dict:
    if not isinstance(value, dict):
        return {"observation": "unavailable"}
    rows = [row for row in _focused_items(value.get("items")) if isinstance(row, dict)]
    return {
        **_focused_fields(value, ("count", "omitted")),
        "captured_windows": [
            _focused_fields(row, (
                "path", "source", "stable_chunk_id", "char_start", "char_end",
                "source_class", "doc_scope", "module_path", "qualified_query_ids",
            ))
            for row in rows
        ],
        "claim_boundary": "captured_window_metadata_not_source_fact_proof",
    }


def _delivery_operand_summary(record: dict) -> dict:
    stages = record.get("stages")
    stages = stages if isinstance(stages, dict) else {}
    observations = stages.get("delivery_observations")
    observations = observations if isinstance(observations, dict) else {}
    returns = []
    for observed in _focused_items(observations.get("returns")):
        if not isinstance(observed, dict):
            continue
        result = observed.get("result")
        result = result if isinstance(result, dict) else {}
        returns.append({
            **_focused_fields(observed, (
                "stage", "request", "project_docs", "dependency_docs", "observation_error",
                "project_trust_decision", "routing", "routing_stages", "lanes",
            )),
            "result": {
                **_focused_fields(result, (
                    "status", "requires_confirmation", "confirmation_reason", "reason",
                    "reason_code", "answer_available", "delivery_decision",
                    "request_scope", "requirements",
                )),
                "result_windows": _delivery_window_summary(result.get("result_windows")),
                "context_windows": _delivery_window_summary(result.get("context_windows")),
            },
        })
    return {
        "record_type": "V2_DELIVERY_OPERANDS",
        **_focused_fields(record, (
            "case_id", "artifact_file", "sha256", "bytes", "run_mode",
            "record_counts", "question", "verdict",
        )),
        "payload": _focused_fields(record.get("payload"), (
            "kind", "status", "reason_code", "support_status", "context_available",
            "answer_supported", "answer_available", "edit_ready", "source_count",
            "covered_query_ids", "missing_query_ids",
        )),
        "stages": _focused_fields(stages, ("diagnostics_present", "stage_status", "observer_counts")),
        "delivery_observation_counts": _focused_fields(observations, ("return_counts", "omitted")),
        "captured_returns": returns,
        "claim_boundary": "existing_bounded_same_call_operands_not_new_runtime_or_source_fact_proof",
    }


def _json_file(path: Path, root: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("report root is not an object")
    return {
        "artifact_file": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }, value


def _source_rows(payload: dict) -> list[dict]:
    sources = payload.get("sources")
    return [
        {
            **_focused_fields(row, (
                "evidence_id", "path_or_url", "project_identity", "scope", "authority",
                "line_start", "line_end", "char_start", "char_end", "source_content_hash", "content_sha256",
            )),
            "snippet_sha256": hashlib.sha256(row["snippet"].encode("utf-8")).hexdigest()
                if isinstance(row.get("snippet"), str) else None,
            "snippet_characters": len(row["snippet"]) if isinstance(row.get("snippet"), str) else None,
        }
        for row in sources if isinstance(row, dict)
    ] if isinstance(sources, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-dir", type=Path, required=True)
    parser.add_argument("--contract-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records: list[dict] = []
    issues: list[dict] = []

    def record(kind: str, value: dict) -> None:
        records.append({"record_type": kind, **value})

    def read(path: Path, root: Path):
        try:
            return _json_file(path, root)
        except (OSError, ValueError) as exc:
            issues.append({"artifact_file": path.relative_to(root).as_posix(),
                           "status": "unreadable", "error_type": type(exc).__name__})
            return None

    def rows(value, field: str, provenance: dict) -> list[dict]:
        if not isinstance(value, list):
            issues.append({**provenance, "field": field, "status": "unavailable_array",
                           "observed_type": type(value).__name__})
            return []
        invalid = sum(not isinstance(row, dict) for row in value)
        if invalid:
            issues.append({**provenance, "field": field, "status": "non_object_rows",
                           "invalid_row_count": invalid, "row_count": len(value)})
        return [row for row in value if isinstance(row, dict)]

    for filename, expected_schema in (
        ("project-context-quality-hermetic.json", "project-context-quality-contract-result-v2"),
        ("project-context-quality-legacy-live.json", "project-answer-quality-live-result-v1"),
        ("project-context-quality-v2-live.json", "project-context-quality-v2-result-4"),
    ):
        matches = sorted(args.quality_dir.rglob(filename))
        if len(matches) != 1:
            issues.append({"expected_file": filename, "match_count": len(matches),
                           "status": "missing" if not matches else "ambiguous"})
            continue
        loaded = read(matches[0], args.quality_dir)
        if loaded is None:
            continue
        provenance, report = loaded
        record("QUALITY_ARTIFACT", {
            **provenance,
            **_focused_fields(report, (
                "schema_version", "run_mode", "lane", "case_count", "positive_case_count",
                "negative_case_count", "metrics", "legacy_fact_acceptance", "validation", "lanes",
                "verdict", "passed_count", "positive_passed_count", "errors", "input_mode",
                "report_only", "acceptance_role", "evaluation_kind", "retrieval_executed",
                "claim_boundary", "quality_boundary", "production_runner_verdict",
                "production_runner_errors", "deterministic_result_digest", "corpus_sha256",
            )),
        })
        if report.get("schema_version") != expected_schema:
            issues.append({**provenance, "status": "unexpected_schema",
                           "expected_schema": expected_schema,
                           "observed_schema": report.get("schema_version")})
            continue
        if filename.endswith("-v2-live.json"):
            def focused(line: str) -> None:
                prefix, encoded = line.split(" ", 1)
                value = json.loads(encoded)
                if value.get("record_counts") != {"evaluator": 1, "production": 1}:
                    issues.append({**provenance, "status": "missing_or_ambiguous_focused_case",
                                   "case_id": value.get("case_id"),
                                   "record_counts": value.get("record_counts")})
                record(prefix, {**value, **provenance})
            try:
                print_focused_stage_records(report, emit=focused)
            except (ValueError, TypeError, AttributeError) as exc:
                issues.append({**provenance, "status": "unreadable_focused_record",
                               "error_type": type(exc).__name__})
        elif filename.endswith("-legacy-live.json"):
            if not isinstance(report.get("legacy_fact_acceptance"), dict):
                issues.append({**provenance, "field": "legacy_fact_acceptance",
                               "status": "unavailable_object"})
            for row in rows(report.get("results"), "results", provenance):
                payload = row.get("payload")
                payload = payload if isinstance(payload, dict) else {}
                record("LEGACY_ARTIFACT_CASE", {
                    **provenance, **_focused_fields(row, (
                        "case_id", "question", "observed", "passed", "checks",
                        "fact_checks", "path_fact_checks", "group_fact_checks", "top1_fact_bearing",
                    )),
                    "payload": _focused_fields(payload, (
                        "kind", "status", "reason_code", "context_status", "context_available",
                        "answer_supported", "answer_available", "edit_ready",
                        "covered_query_ids", "missing_query_ids",
                    )),
                    "sources": _source_rows(payload),
                })

    required_contract_files = ("recovery-contract.json", "agent-developer-v1.json", "agent-developer-v2.json")
    for filename in required_contract_files:
        if not (args.contract_dir / filename).is_file():
            issues.append({"expected_file": filename, "status": "missing"})
    contract_json = [
        path for path in sorted(args.contract_dir.rglob("*.json"))
        if path.relative_to(args.contract_dir).parts == (path.name,) and path.name in required_contract_files
        or (path.relative_to(args.contract_dir).parts[0].startswith("docatlas-recovery-evidence-")
            and len(path.relative_to(args.contract_dir).parts) == 2)
        or (path.name == "evidence.json"
            and path.relative_to(args.contract_dir).parts[0].startswith("docmancer-mutation-evidence-"))
        or (path.name == "comparison.json"
            and "literal-contract-comparison" in path.relative_to(args.contract_dir).parts)
    ]
    if not contract_json:
        issues.append({"expected_file": "contract reports", "status": "missing"})
    for path in contract_json:
        loaded = read(path, args.contract_dir)
        if loaded is None:
            continue
        provenance, report = loaded
        if report.get("schema_version") == "recovery-contract-v2":
            record("RECOVERY_ARTIFACT", {
                **provenance, **_focused_fields(report, (
                    "schema_version", "counts", "question_sha256", "source_sha256", "modules",
                )),
                "cases": [_focused_fields(row, (
                    "id", "outcome", "guard", "error_type", "message",
                )) for row in rows(report.get("cases"), "cases", provenance)],
            })
        elif path.name == "evidence.json":
            missing = [key for key in ("run", "validated", "returncode", "junit", "mutation") if key not in report]
            if missing:
                issues.append({**provenance, "status": "incomplete_producer_receipt", "missing_fields": missing})
            junit = report.get("junit")
            if not isinstance(junit, dict):
                issues.append({**provenance, "field": "junit", "status": "unavailable_object"})
                junit = {}
            record("CRITICAL_ARTIFACT", {
                **provenance, **_focused_fields(report, ("run", "validated", "returncode", "mutation")),
                "junit": {key: value for key, value in junit.items() if key != "cases"},
                "claim_boundary": "stored_producer_receipt_not_revalidated",
            })
        else:
            record("CONTRACT_ARTIFACT", {
                **provenance, **_focused_fields(report, (
                    "schema_version", "status", "passed", "baseline_cases", "mutants_killed",
                    "gate_sha256", "frozen_question_sha256", "frozen_source_sha256",
                    "counts", "metrics", "summary", "failures", "validation", "baseline", "mutations",
                    "historical_tests", "compact_tests", "mutant_count", "pairs", "errors",
                    "protocol", "baseline_ok", "target_ok", "task_count", "executed_task_count",
                    "target_closed_tasks", "target_gap_count", "target_gaps", "false_supported",
                    "forbidden_source_contamination", "v1_target_ok", "v1_task_count",
                    "adversarial_case_count", "adversarial_passed_cases", "execution_errors",
                    "execution_identity", "migration_control_count", "migration_controls_ok",
                )),
            })

    # A rejected mutation baseline has no validated evidence.json. Read its
    # already retained JUnit directly, and never infer kills from these failures.
    baseline_xml = [
        path for path in sorted(args.contract_dir.rglob("baseline.junit.xml"))
        if path.relative_to(args.contract_dir).parts[0].startswith("docmancer-mutation-")
    ]
    if not baseline_xml and not any(path.name == "evidence.json" for path in contract_json):
        issues.append({"expected_file": "critical evidence.json or retained baseline.junit.xml",
                       "status": "missing", "mutation_credit": "not_inferred"})
    for path in baseline_xml:
        try:
            raw = path.read_bytes()
            xml = ET.fromstring(raw)
            cases = list(xml.iter("testcase"))
            failed = []
            for case in cases:
                for reason in (*case.findall("failure"), *case.findall("error")):
                    failed.append({"classname": case.get("classname"), "name": case.get("name"),
                                   "kind": reason.tag, "message": reason.get("message", "")})
            record("CRITICAL_BASELINE", {
                "artifact_file": path.relative_to(args.contract_dir).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(), "observed_case_count": len(cases),
                "failures": failed, "mutation_credit": "not_inferred",
            })
        except (OSError, ValueError, ET.ParseError) as exc:
            issues.append({"artifact_file": path.relative_to(args.contract_dir).as_posix(),
                           "status": "unreadable", "error_type": type(exc).__name__})

    # Recovery already writes body-free structured failure diagnostics to its
    # captured stdout. Decode those records; do not import or rerun the gate.
    for path in sorted(args.contract_dir.rglob("*.stdout.log")):
        if not path.relative_to(args.contract_dir).parts[0].startswith("docatlas-recovery-evidence-"):
            continue
        provenance = {"artifact_file": path.relative_to(args.contract_dir).as_posix()}
        try:
            raw = path.read_bytes()
            provenance.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            lines = raw.decode("utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            issues.append({**provenance, "status": "unreadable", "error_type": type(exc).__name__})
            continue
        for line in lines:
            if line.startswith("RECOVERY_FAILURE "):
                try:
                    value = json.loads(line.partition(" ")[2])
                    if not isinstance(value, dict):
                        raise ValueError("diagnostic root is not an object")
                    record("RECOVERY_FAILURE", {**value, **provenance})
                except ValueError as exc:
                    issues.append({**provenance, "status": "unreadable_record",
                                   "error_type": type(exc).__name__})

    # Emit a compact operand row for every focused case before large ledgers.
    # Full focused records remain unchanged below and in the saved artifact.
    records = [
        *[_delivery_operand_summary(row) for row in records
          if row["record_type"] == "V2_FOCUSED_STAGE"],
        *records,
    ]
    result = {
        "schema_version": 1, "purpose": "existing_artifacts_only_not_gate_acceptance",
        "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "checkout_commit": os.environ.get("GITHUB_SHA"), "issues": issues, "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    remaining, omitted = 384_000, 0

    def emit(kind: str, value: dict, *, already_bounded: bool = False) -> None:
        nonlocal remaining, omitted
        line = kind + " " + json.dumps(value if already_bounded else _focused_bound(value), ensure_ascii=False)
        size = len(line.encode("utf-8")) + 1
        if size > remaining - 512:  # Retain space for the fixed console receipt below.
            omitted += 1
            return
        print(line)
        remaining -= size

    emit("ARTIFACT_PROVENANCE", {key: value for key, value in result.items() if key != "records"})
    for row in records:
        # Shared V2 serialization already applied the original depth/list bound.
        # Applying it twice would wrap list envelopes again and lose more leaves.
        emit(row["record_type"], {key: value for key, value in row.items() if key != "record_type"},
             already_bounded=row["record_type"] in {"V2_FOCUSED_STAGE", "V2_DELIVERY_OPERANDS"})
    print("ARTIFACT_CONSOLE " + json.dumps({"omitted_rows": omitted, "record_count": len(records),
                                           "complete_selected_records_in_artifact": True,
                                           "original_reports_preserved": True}))
    return 2 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
