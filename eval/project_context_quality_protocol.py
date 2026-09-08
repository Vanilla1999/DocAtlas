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
LANES_LOCK_PATH = LOCK_PATH.with_name("lanes.lock.json")


def load_cases(lane: str = "legacy") -> tuple[dict[str, Any], ...]:
    if lane not in {"legacy", "natural", "paraphrases"}:
        raise ValueError(f"unknown corpus lane: {lane}")
    legacy = lane == "legacy"
    path = CASES_PATH if legacy else CASES_PATH.with_name(f"{lane}.json")
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if legacy:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    else:
        lanes_lock = json.loads(LANES_LOCK_PATH.read_text(encoding="utf-8"))
        if lanes_lock["protocol_lock_sha256"] != hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest():
            raise ValueError("frozen numeric threshold protocol changed")
        lock = lanes_lock["lanes"][lane]
    schema = "corpus" if legacy else lane
    if payload.get("schema_version") != f"project-context-quality-{schema}-v1":
        raise ValueError("unsupported project context quality corpus schema")
    if legacy and lock.get("schema_version") != "project-context-quality-protocol-v1":
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
    if legacy:
        if CASES_PATH.with_name("cases.legacy.json").read_bytes() != raw:
            raise ValueError("immutable legacy snapshot differs from cases.json")
        return rows
    if lane == "paraphrases":
        # Validate the shared fact bank's frozen bytes before resolving references.
        load_cases("natural")
        facts = json.loads(CASES_PATH.with_name("natural.json").read_text(encoding="utf-8"))["facts"]
    else:
        facts = payload["facts"]
    positives = sum(row["expected_kind"] == "docs_context" for row in rows)
    if positives != lock["positive_case_count"] or len(rows) - positives != lock["negative_case_count"]:
        raise ValueError("positive/negative inventory mismatch")
    for row in rows:
        if row["scope"] not in {"project", "all"}:
            raise ValueError("unsupported corpus scope")
        row["required_fact_groups"] = tuple(
            tuple((str(path), str(text)) for path, text in facts[name])
            for name in row["fact_groups"]
        )
        row["sources"] = list(dict.fromkeys(
            path for group in row["required_fact_groups"] for path, _ in group
        ))
        if row["expected_kind"] == "docs_context" and (
            len(row["required_fact_groups"]) < 2
            or any(not group for group in row["required_fact_groups"])
            or not 0 < row["minimum_lookup_coverage"] <= len(row["lookup_queries"]) <= 5
        ):
            raise ValueError("compound cases require independent facts and nonzero lookup coverage")
    return rows


def run_contract(lane: str = "legacy") -> dict[str, Any]:
    results = []
    for case in load_cases(lane):
        if lane != "legacy":
            plan = build_documentation_query_plan(
                case["question"], lookup_queries=tuple(case["lookup_queries"]), requirements=(),
            ).as_payload()
            checks = {
                "explicit_public_inventory": plan["public_query_ids"] == case["expected_public_query_ids"],
                "optional_lookups": not any(q.startswith("query-lookup-") for q in plan["required_query_ids"]),
                "no_public_canonical_aliases": not any(q.startswith("query-intent-") for q in plan["public_query_ids"]),
            }
            results.append({"id": case["id"], "public_query_ids": plan["public_query_ids"],
                            "checks": checks, "passed": all(checks.values())})
            continue
        expected = case.get("intent")
        language_results: dict[str, Any] = {}
        passed = True
        for language, question in (
            ("ru", str(case["question"])),
            ("en", str(case["pair"])),
        ):
            lookup_key = "lookup_queries" if language == "ru" else "pair_lookup_queries"
            lookup_queries = tuple(str(value) for value in case.get(lookup_key) or ())
            aliases = build_project_retrieval_aliases(question)
            plan = build_documentation_query_plan(
                question, lookup_queries=lookup_queries, requirements=(),
            )
            plan_payload = plan.as_payload()
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
                and all(
                    f"query-lookup-{index}" in plan_payload["public_query_ids"]
                    for index in range(1, len(lookup_queries) + 1)
                )
                and not any(
                    query_id.startswith("query-lookup-")
                    for query_id in plan_payload["required_query_ids"]
                )
                and not any(
                    query_id.startswith("query-intent-")
                    for query_id in plan_payload["public_query_ids"]
                )
            )
            passed = passed and language_passed
            language_results[language] = {
                "intent_ids": sorted(intent_ids),
                "public_tools": public_tools,
                "public_query_ids": plan_payload["public_query_ids"],
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
        "lane": lane,
        "report_only": False,
        "evaluation_kind": (
            "alias_and_query_plan_contract" if lane == "legacy"
            else "query_plan_public_inventory_contract"
        ),
        "retrieval_executed": False,
    }
    report["verdict"] = "PASS" if report["passed_count"] == report["case_count"] else "FAIL"
    return report


def run_live(lane: str = "legacy", *, question_only: bool = False) -> dict[str, Any]:
    from scripts.run_project_docs_self_host_gate import LiveCase, run

    rows = load_cases(lane)
    positives = tuple(item for item in rows if item["expected_kind"] != "insufficient_evidence")
    negatives = tuple(item for item in rows if item["expected_kind"] == "insufficient_evidence")
    cases = tuple(
        LiveCase(
            case_id=str(item["id"]),
            scope=str(item.get("scope", "project")),
            question=str(item["question"]),
            relevant_paths=tuple(str(value) for value in item.get("sources") or ()),
            expected_kind=str(item["expected_kind"]),
            required_facts_by_path=tuple(
                (str(value["source"]), str(value["text"]))
                for value in item.get("required_facts") or ()
            ),
            required_fact_groups=tuple(item.get("required_fact_groups") or ()),
            forbidden_source_prefixes=(
                "eval/", "docs/analysis/", ".hermes/plans/", "roadmap/",
                *(str(value) for value in item.get("forbidden_source_prefixes") or ()),
            ),
            forbidden_answer_fragments=tuple(
                str(value) for value in item.get("forbidden_answer_fragments") or ()
            ),
            lookup_queries=() if question_only else tuple(
                str(value) for value in item.get("lookup_queries") or ()
            ),
            minimum_lookup_coverage=0 if question_only else int(item.get("minimum_lookup_coverage") or 0),
            allowed_paths=tuple(
                str(value) for value in item.get("allowed_paths") or item.get("sources") or ()
            ),
            expected_public_query_ids=tuple(
                str(value) for value in item.get("expected_public_query_ids") or ()
                if not question_only or not str(value).startswith("query-lookup-")
            ),
        )
        for item in positives
    )
    report = run(
        cases=cases,
        negative_cases=tuple(LiveCase(
            case_id=str(item["id"]), question=str(item["question"]),
            scope=str(item.get("scope", "project")), relevant_paths=(),
            expected_kind="insufficient_evidence",
        ) for item in negatives),
    )
    report.update({
        "lane": lane,
        "input_mode": "question_only" if question_only else "question_with_lookups",
        "report_only": question_only or lane == "paraphrases",
        "thresholds": json.loads(LOCK_PATH.read_text(encoding="utf-8"))["thresholds"],
        "corpus_sha256": hashlib.sha256(
            (CASES_PATH if lane == "legacy" else CASES_PATH.with_name(f"{lane}.json")).read_bytes()
        ).hexdigest(),
        "claim_boundary": "in_process_self_host_not_installed_agent",
    })
    # The runner digest describes its unmodified report, before lane metadata.
    if "deterministic_result_digest" in report:
        report["runner_result_digest"] = report.pop("deterministic_result_digest")
    report["deterministic_result_digest"] = hashlib.sha256(json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--lane", choices=("legacy", "natural", "paraphrases"), default="legacy")
    parser.add_argument("--question-only", action="store_true", help="Live report-only ablation; omit host lookups without changing gate thresholds")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-only", action="store_true", help="preserve the legacy live report without using its path-specific verdict as release acceptance")
    args = parser.parse_args(argv)
    if args.question_only and not args.live:
        parser.error("--question-only requires --live")
    report = run_live(args.lane, question_only=args.question_only) if args.live else run_contract(args.lane)
    if args.report_only:
        report["report_only"] = True
        report["acceptance_role"] = "legacy_compatibility_report_only"
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report.get("verdict") == "PASS" or report.get("report_only") else 1


if __name__ == "__main__":
    raise SystemExit(main())
