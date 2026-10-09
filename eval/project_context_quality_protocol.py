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
    """Check literal query identity without treating planning as retrieval quality.

    Legacy intent labels remain frozen historical metadata. The current contract
    permits only the original question and explicit host lookups, with no inferred
    obligations, aliases, or inherited original-query coverage.
    """
    results = []
    for case in load_cases(lane):
        inputs = (("ru", str(case["question"]), "lookup_queries"),)
        if lane == "legacy":
            inputs += (("en", str(case["pair"]), "pair_lookup_queries"),)
        language_results: dict[str, Any] = {}
        for language, question, lookup_key in inputs:
            lookups = tuple(str(value) for value in case.get(lookup_key) or ())
            plan = build_documentation_query_plan(
                question, lookup_queries=lookups, requirements=(),
            )
            payload = plan.as_payload()
            contract = build_project_answer_contract(question)
            expected_ids = ["query-original", *(
                f"query-lookup-{index}" for index in range(1, len(lookups) + 1)
            )]
            expected_queries = [("query-original", question, "original", "direct", True)]
            expected_queries.extend(
                (f"query-lookup-{index}", text, "host_lookup", "host_lookup", False)
                for index, text in enumerate(lookups, 1)
            )
            checks = {
                "original_unchanged": plan.original_question == question,
                "explicit_public_inventory": payload["public_query_ids"] == expected_ids,
                "literal_query_lineage": [
                    (item.query_id, item.text, item.origin, item.relation, item.coverage_required)
                    for item in plan.queries
                ] == expected_queries,
                "original_required_lookups_optional": payload["required_query_ids"] == ["query-original"],
                "no_parent_coverage_transfer": all(item.public_parent_query_id is None for item in plan.queries),
                "no_inferred_aliases": not build_project_retrieval_aliases(question),
                "no_inferred_answer_contract": not any((
                    contract.proof_obligations, contract.subjects,
                    contract.retrieval_hints, contract.concept_queries,
                )),
                "question_identity_bound": contract.question_hash == hashlib.sha256(
                    json.dumps(question, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                "no_completeness_claim": not plan.component_scope_complete and not contract.component_scope_complete,
            }
            language_results[language] = {
                "public_query_ids": payload["public_query_ids"],
                "checks": checks, "passed": all(checks.values()),
            }
        results.append({
            "id": case["id"], "languages": language_results,
            "passed": all(row["passed"] for row in language_results.values()),
        })
    report = {
        "schema_version": "project-context-quality-contract-result-v2",
        "case_count": len(results), "passed_count": sum(row["passed"] for row in results),
        "results": results, "lane": lane, "report_only": False,
        "evaluation_kind": "literal_query_identity_and_lineage_contract",
        "retrieval_executed": False,
        "quality_boundary": "useful_source_bound_positive_and_negative_facts_require_separate_live_report",
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
