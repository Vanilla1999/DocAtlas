#!/usr/bin/env python3
"""Provider-free and optional live gate for project context quality."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "eval/project_context_quality/cases.json"
LOCK_PATH = ROOT / "eval/project_context_quality/protocol.lock.json"


def load_cases() -> tuple[dict[str, Any], ...]:
    raw = CASES_PATH.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "project-context-quality-corpus-v1":
        raise ValueError("unsupported project context quality corpus schema")
    if lock.get("schema_version") != "project-context-quality-protocol-v1":
        raise ValueError("unsupported project context quality protocol lock")
    digest = hashlib.sha256(raw).hexdigest()
    if lock.get("case_file_sha256") != digest:
        raise ValueError("project context quality corpus hash does not match protocol lock")
    rows = tuple(dict(item) for item in payload.get("cases") or ())
    ids = [str(item.get("id") or "") for item in rows]
    if (
        len(rows) != int(lock.get("case_count") or 0)
        or ids != list(lock.get("case_ids") or ())
        or len(set(ids)) != len(ids)
        or not all(ids)
    ):
        raise ValueError("project context quality corpus inventory mismatch")
    return rows


def run_contract() -> dict[str, Any]:
    results = []
    for case in load_cases():
        expected = case.get("intent")
        language_results: dict[str, Any] = {}
        passed = True
        for language, question in (
            ("ru", str(case["question"])),
            ("en", str(case["pair"])),
        ):
            aliases = build_project_retrieval_aliases(question)
            plan = build_documentation_query_plan(question, requirements=())
            contract = build_project_answer_contract(question)
            intent_ids = {alias.intent_id for alias in aliases}
            public_tools = any(
                obligation.attribute == "public_tools"
                for obligation in contract.proof_obligations
            )
            language_passed = (
                (expected in intent_ids if expected else not aliases)
                and (
                    any(item.origin == "canonical_intent" for item in plan.queries)
                    == bool(expected)
                )
                and not (case["id"] == "ru-first-commands" and public_tools)
            )
            passed = passed and language_passed
            language_results[language] = {
                "intent_ids": sorted(intent_ids),
                "public_tools": public_tools,
                "passed": language_passed,
            }
        results.append({
            "id": case["id"],
            "languages": language_results,
            "passed": passed,
        })
    report = {
        "schema_version": "project-context-quality-contract-result-v1",
        "case_count": len(results),
        "passed_count": sum(row["passed"] for row in results),
        "results": results,
    }
    report["verdict"] = "PASS" if report["passed_count"] == report["case_count"] else "FAIL"
    return report


def run_live() -> dict[str, Any]:
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    rows = load_cases()
    positives = tuple(item for item in rows if item.get("intent"))
    negatives = tuple(item for item in rows if not item.get("intent"))
    cases = tuple(
        LiveCase(
            question=str(item["question"]),
            relevant_paths=tuple(str(value) for value in item.get("sources") or ()),
            expected_kind=str(item["expected_kind"]),
            required_facts_by_path=(),
            forbidden_source_prefixes=("eval/", ".hermes/plans/", "roadmap/"),
            # Semantic substitution is checked in the contract gate. Relevant
            # source snippets may legitimately mention public tool names.
            forbidden_answer_fragments=(),
        )
        for item in positives
    )
    return run(
        cases=cases,
        negative_cases=tuple(str(item["question"]) for item in negatives),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    report = run_live() if args.live else run_contract()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
