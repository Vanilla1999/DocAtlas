#!/usr/bin/env python3
"""Blocking acceptance wrapper around the independent V2 quality evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.project_context_quality_v2_protocol import run_live

LOCK_PATH = ROOT / "eval/project_context_quality_v2/acceptance.lock.json"
V2_PROTOCOL_LOCK = ROOT / "eval/project_context_quality_v2/protocol.lock.json"
LEGACY_PROTOCOL_LOCK = ROOT / "eval/project_context_quality/protocol.lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fraction(value: Any, *, name: str) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not a fraction")
    numerator, denominator = value.get("numerator"), value.get("denominator")
    if type(numerator) is not int or type(denominator) is not int or numerator < 0 or denominator < 0:
        raise ValueError(f"{name} has invalid fraction values")
    return numerator, denominator


def load_acceptance_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "project-context-quality-v2-acceptance-v3":
        raise ValueError("unsupported V2 acceptance lock")
    expected = {
        "v2_protocol_lock_sha256": _sha256(V2_PROTOCOL_LOCK),
        "legacy_protocol_lock_sha256": _sha256(LEGACY_PROTOCOL_LOCK),
    }
    for key, digest in expected.items():
        if lock.get(key) != digest:
            raise ValueError(f"{key} does not bind the current frozen protocol")
    return lock


def verify_v2_acceptance(report: dict[str, Any], lock: dict[str, Any] | None = None) -> list[str]:
    lock = lock or load_acceptance_lock()
    failures: list[str] = []
    if report.get("schema_version") != "project-context-quality-v2-result-4":
        return ["unexpected V2 report schema"]
    if report.get("output_cost_policy") != lock["output_cost_policy"]:
        failures.append("V2 output cost policy does not match the reviewed acceptance policy")
    if report.get("run_mode") != "live_self_host":
        failures.append("V2 acceptance requires live_self_host mode")
    validation = report.get("validation") or {}
    if validation.get("case_count") != 25:
        failures.append("V2 acceptance requires the complete 25-case frozen corpus")
    lanes = report.get("lanes") or {}
    for lane, thresholds in lock["lanes"].items():
        metrics = (lanes.get(lane) or {}).get("metrics") or {}
        for metric, threshold in thresholds.items():
            try:
                numerator, denominator = _fraction(metrics.get(metric), name=f"{lane}.{metric}")
            except ValueError as exc:
                failures.append(str(exc))
                continue
            if denominator != threshold["denominator"]:
                failures.append(
                    f"{lane}.{metric} denominator changed: {denominator} != {threshold['denominator']}"
                )
                continue
            if "minimum" in threshold and numerator < threshold["minimum"]:
                failures.append(
                    f"{lane}.{metric} below acceptance: {numerator}/{denominator} < "
                    f"{threshold['minimum']}/{denominator}"
                )
            if "maximum" in threshold and numerator > threshold["maximum"]:
                failures.append(
                    f"{lane}.{metric} above acceptance: {numerator}/{denominator} > "
                    f"{threshold['maximum']}/{denominator}"
                )
    return failures


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


def print_focused_stage_records(report: dict[str, Any]) -> None:
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
                    "stage_status", "delivery_decision", "observer_counts", "planned_query_ids",
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
        print("V2_FOCUSED_STAGE " + json.dumps(_focused_bound(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or verify blocking project-context V2 acceptance")
    parser.add_argument("--report", type=Path, help="verify an existing V2 live report instead of executing retrieval")
    parser.add_argument("--output", type=Path, help="write the live report for artifact retention")
    args = parser.parse_args(argv)
    report = (
        json.loads(args.report.read_text(encoding="utf-8"))
        if args.report else run_live()
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = verify_v2_acceptance(report)
    print_focused_stage_records(report)
    if failures:
        print("V2 project-context acceptance: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    natural = report["lanes"]["natural"]["metrics"]
    exposed = report["lanes"]["exposed_paraphrases"]["metrics"]
    print(
        "V2 project-context acceptance: PASS; "
        f"natural={natural['semantic_usefulness']['numerator']}/15; "
        f"paraphrases={exposed['semantic_usefulness']['numerator']}/5; "
        "false_full=0; safety/cost observations=25/25; source count and output cost are measured without fixed ceilings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
