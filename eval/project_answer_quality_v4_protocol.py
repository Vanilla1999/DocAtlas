#!/usr/bin/env python3
"""Hermetic production-path quality protocol for QuestionPlan v4."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from eval import project_answer_quality_protocol as v1


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "eval" / "project_answer_quality_v4"
CASES_PATH = DATA_ROOT / "cases.json"
LOCK_PATH = DATA_ROOT / "protocol_v4.lock.json"


def load_cases() -> tuple[v1.QualityCase, ...]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project-answer-quality-corpus-v4":
        raise ValueError("unsupported project-answer quality v4 corpus schema")
    rows: list[v1.QualityCase] = []
    seen: set[str] = set()
    for raw in payload.get("cases") or ():
        case_id = str(raw.get("case_id") or "").strip()
        question = str(raw.get("question") or "").strip()
        if not case_id or case_id in seen or not question:
            raise ValueError("quality cases require unique IDs and non-empty questions")
        seen.add(case_id)
        files = tuple(sorted(
            (str(path), str(text))
            for path, text in dict(raw.get("files") or {}).items()
        ))
        documents = tuple(dict(row) for row in raw.get("documents") or ())
        file_paths = {path for path, _ in files}
        document_paths = {str(row.get("path") or "") for row in documents}
        if not files or not document_paths.issubset(file_paths):
            raise ValueError(f"{case_id}: catalog entries must reference fixture files")
        expected_raw = dict(raw.get("expected") or {})
        expected = v1.ExpectedOutcome(
            status=str(expected_raw.get("status") or ""),
            evidence_paths=tuple(str(value) for value in expected_raw.get("evidence_paths") or ()),
            required_fragments=tuple(str(value) for value in expected_raw.get("required_fragments") or ()),
            forbidden_fragments=tuple(str(value) for value in expected_raw.get("forbidden_fragments") or ()),
            forbidden_paths=tuple(str(value) for value in expected_raw.get("forbidden_paths") or ()),
        )
        if expected.status not in {"ok", "insufficient_evidence"}:
            raise ValueError(f"{case_id}: unsupported expected status")
        if not set(expected.evidence_paths).issubset(document_paths):
            raise ValueError(f"{case_id}: expected evidence path is not cataloged")
        rows.append(v1.QualityCase(
            case_id=case_id, question=question, files=files,
            documents=documents, expected=expected,
        ))
    return tuple(rows)


def validate_protocol_lock() -> dict[str, Any]:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    if lock.get("schema_version") != "project-answer-quality-protocol-v4":
        errors.append("schema_version")
    if lock.get("case_file") != "cases.json":
        errors.append("case_file")
    if lock.get("case_file_sha256") != v1.file_sha256(CASES_PATH):
        errors.append("case_file_sha256")
    if tuple(lock.get("public_argument_fields") or ()) != v1.PUBLIC_ARGUMENT_FIELDS:
        errors.append("public_argument_fields")
    if int(lock.get("supported_token_limit") or 0) != v1.SUPPORTED_TOKEN_LIMIT:
        errors.append("supported_token_limit")
    if int(lock.get("insufficient_token_limit") or 0) != v1.INSUFFICIENT_TOKEN_LIMIT:
        errors.append("insufficient_token_limit")
    if tuple(lock.get("case_ids") or ()) != tuple(case.case_id for case in load_cases()):
        errors.append("case_ids")
    if errors:
        raise ValueError("invalid project-answer quality v4 protocol lock: " + ", ".join(errors))
    return lock


def run(output: Path | None = None) -> dict[str, Any]:
    lock = validate_protocol_lock()
    cases = load_cases()
    results: list[v1.CaseResult] = []
    with tempfile.TemporaryDirectory(prefix="docatlas-project-answer-quality-v4-") as temporary:
        root = Path(temporary)
        for case in cases:
            results.append(v1.run_case(case, root / case.case_id))
    supported = [row for row, case in zip(results, cases) if case.expected.status == "ok"]
    report = {
        "schema_version": "project-answer-quality-result-v4",
        "provider_free": True,
        "protocol_sha256": v1.file_sha256(LOCK_PATH),
        "case_file_sha256": lock["case_file_sha256"],
        "public_argument_fields": list(v1.PUBLIC_ARGUMENT_FIELDS),
        "case_count": len(results),
        "passed_count": sum(row.passed for row in results),
        "stage_metrics": {
            "document_acquisition_recall": v1._mean(results, "document_acquisition_recall"),
            "indexed_fact_coverage": v1._mean(supported, "indexed_fact_coverage"),
            "candidate_recall_at_k": v1._mean(supported, "candidate_recall_at_k"),
            "selected_obligation_coverage": v1._mean(supported, "selected_obligation_coverage"),
            "projected_answer_coverage": v1._mean(supported, "projected_answer_coverage"),
            "citation_integrity": v1._mean(results, "citation_integrity"),
            "abstention_correctness": v1._mean(results, "abstention_correctness"),
            "contamination_free": v1._mean(results, "contamination_free"),
            "maximum_visible_tokens": max(row.visible_tokens for row in results),
        },
        "verdict": "PASS" if all(row.passed for row in results) else "FAIL",
        "results": [
            {
                "case_id": row.case_id,
                "status": row.status,
                "passed": row.passed,
                "checks": dict(row.checks),
                "diagnostics": list(row.diagnostics),
                "stage_metrics": dict(row.stage_metrics),
                "public_arguments": dict(row.public_arguments),
                "selected_paths": list(row.selected_paths),
                "candidate_paths": list(row.candidate_paths),
                "visible_tokens": row.visible_tokens,
                "decision_hash": row.decision_hash,
            }
            for row in results
        ],
    }
    report["deterministic_result_digest"] = hashlib.sha256(v1.canonical_bytes(report)).hexdigest()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-protocol", action="store_true")
    args = parser.parse_args()
    if args.validate_protocol:
        validate_protocol_lock()
        print("PASS")
        return 0
    report = run(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
