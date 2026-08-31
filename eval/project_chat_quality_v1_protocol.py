#!/usr/bin/env python3
"""Novel adversarial semantic gate for project chat answer authorization."""
from __future__ import annotations

import json
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval/project_chat_quality_v1/cases.json"
ONBOARDING_CASES_PATH = ROOT / "eval/project_chat_quality_v1/onboarding_cases.json"
ONBOARDING_LOCK_PATH = ROOT / "eval/project_chat_quality_v1/onboarding_protocol.lock.json"
V4_CASES_PATH = ROOT / "eval/project_answer_quality_v4/cases.json"


def _ngrams(text: str, size: int = 8) -> set[tuple[str, ...]]:
    tokens = re.findall(r"[a-zа-яё0-9_]+", text.casefold())
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def _unit(text: str) -> AnswerUnit:
    return AnswerUnit(
        unit_id="project-chat-quality",
        kind="sentence",
        text=text,
        char_start=0,
        char_end=len(text),
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        proposition=True,
    )


def load_cases() -> tuple[dict[str, Any], ...]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project-chat-quality-corpus-v1":
        raise ValueError("unsupported project chat quality corpus schema")
    cases = tuple(dict(item) for item in payload.get("cases") or ())
    ids = [str(item.get("case_id") or "") for item in cases]
    if len(cases) != 40 or len(set(ids)) != 40 or not all(ids):
        raise ValueError("project chat quality corpus requires 40 unique cases")
    return cases


def load_onboarding_cases() -> tuple[dict[str, Any], ...]:
    payload = json.loads(ONBOARDING_CASES_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project-chat-onboarding-corpus-v1":
        raise ValueError("unsupported project chat onboarding corpus schema")
    cases = tuple(dict(item) for item in payload.get("cases") or ())
    ids = [str(item.get("case_id") or "") for item in cases]
    if len(cases) != 20 or len(set(ids)) != 20 or not all(ids):
        raise ValueError("project chat onboarding corpus requires 20 unique cases")
    allowed_kinds = {"docs_answer", "docs_context", "insufficient_evidence"}
    if any(case.get("expected_kind") not in allowed_kinds for case in cases):
        raise ValueError("project chat onboarding cases require a supported expected_kind")
    lock = json.loads(ONBOARDING_LOCK_PATH.read_text(encoding="utf-8"))
    class_counts = Counter(str(case.get("class") or "") for case in cases)
    errors = []
    if lock.get("schema_version") != "project-chat-onboarding-protocol-v1":
        errors.append("schema_version")
    if lock.get("case_file") != ONBOARDING_CASES_PATH.name:
        errors.append("case_file")
    if lock.get("case_file_sha256") != hashlib.sha256(ONBOARDING_CASES_PATH.read_bytes()).hexdigest():
        errors.append("case_file_sha256")
    if int(lock.get("case_count") or 0) != len(cases):
        errors.append("case_count")
    if tuple(lock.get("case_ids") or ()) != tuple(ids):
        errors.append("case_ids")
    if dict(lock.get("class_counts") or {}) != dict(class_counts):
        errors.append("class_counts")
    if errors:
        raise ValueError("invalid onboarding protocol lock: " + ", ".join(errors))
    return cases


def run_onboarding() -> dict[str, Any]:
    from scripts.run_project_docs_self_host_gate import LiveCase, run as run_live

    live_cases = tuple(
        LiveCase(
            question=str(case["question"]),
            relevant_paths=tuple(str(value) for value in case.get("acceptable_sources") or ()),
            expected_kind=str(case["expected_kind"]),
            required_facts_by_path=tuple(
                (str(item["source"]), str(item["text"]))
                for item in case.get("required_facts") or ()
            ),
            forbidden_source_prefixes=tuple(
                str(value) for value in case.get("forbidden_source_prefixes") or ()
            ),
            forbidden_answer_fragments=tuple(
                str(value) for value in case.get("forbidden_answer_fragments") or ()
            ),
        )
        for case in load_onboarding_cases()
    )
    report = run_live(cases=live_cases, negative_cases=())
    report["case_ids"] = [case["case_id"] for case in load_onboarding_cases()]
    return report


def contamination_overlaps(cases: tuple[dict[str, Any], ...]) -> list[str]:
    frozen = json.loads(V4_CASES_PATH.read_text(encoding="utf-8"))
    frozen_ngrams = set().union(*(
        _ngrams(str(item.get("question") or "")) for item in frozen.get("cases") or ()
    ))
    return [
        str(case["case_id"])
        for case in cases
        if _ngrams(str(case.get("question") or "")) & frozen_ngrams
    ]


def run() -> dict[str, Any]:
    cases = load_cases()
    overlaps = contamination_overlaps(cases)
    results: list[dict[str, Any]] = []
    for case in cases:
        contract = build_project_answer_contract(str(case["question"]))
        expected_obligations = case.get("expected_obligations")
        if expected_obligations is not None:
            observed = len(contract.proof_obligations)
            passed = observed == int(expected_obligations) and bool(contract.unresolved_parts)
        else:
            proof = bool(
                contract.proof_obligations
                and any(
                    local_proof_for_obligation(
                        obligation, _unit(str(case.get("evidence") or "")),
                    ).valid
                    for obligation in contract.proof_obligations
                )
            )
            observed = proof
            passed = proof is bool(case["expected_proof"])
        results.append({
            "case_id": case["case_id"],
            "class": case["class"],
            "observed": observed,
            "passed": passed,
        })
    false_supported = sum(
        not bool(case.get("expected_proof")) and result["observed"] is True
        for case, result in zip(cases, results)
        if "expected_proof" in case
    )
    report = {
        "schema_version": "project-chat-quality-result-v1",
        "case_count": len(cases),
        "passed_count": sum(result["passed"] for result in results),
        "false_supported_count": false_supported,
        "class_failures": {
            name: sum(
                not result["passed"] for result in results if result["class"] == name
            )
            for name in sorted({str(result["class"]) for result in results})
        },
        "contamination_overlap_case_ids": overlaps,
        "results": results,
    }
    report["verdict"] = "PASS" if all(result["passed"] for result in results) and not overlaps else "FAIL"
    return report


def main() -> int:
    proof_report = run()
    onboarding_report = run_onboarding()
    report = {
        "schema_version": "project-chat-quality-combined-result-v1",
        "verdict": (
            "PASS" if proof_report["verdict"] == onboarding_report["verdict"] == "PASS"
            else "FAIL"
        ),
        "proof_gate": proof_report,
        "production_gate": onboarding_report,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
