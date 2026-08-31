#!/usr/bin/env python3
"""Provider-free current-repository gate for the context-first Docs pipeline.

The gate indexes this repository into an isolated temporary SQLite store and then
runs canonical Project Docs questions through the unpatched public
``get_docs_context`` MCP handler. It proves the current production chain:

question -> retrieval -> proof metadata -> final answer-or-context projection.

The corpus intentionally covers the stable QuestionPlan families plus two
premise/condition cases that depend on the clear-index source of truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import DocsJobTracker, LibraryDocsService


REPO_ROOT = Path(__file__).resolve().parents[1]
TOP1_RELEVANCE_MIN = 0.80
TOP3_RELEVANCE_MIN = 0.95
FALSE_ABSTENTION_MAX = 2
SCORE_8_PLUS_RATE_MIN = 0.80
MEAN_SCORE_MIN = 8.0

@dataclass(frozen=True, slots=True)
class LiveCase:
    question: str
    relevant_paths: tuple[str, ...]
    required_fragments: tuple[str, ...] = ()
    surface_case_id: int | None = None
    expected_kind: str | None = None
    required_facts_by_path: tuple[tuple[str, str], ...] = ()
    forbidden_source_prefixes: tuple[str, ...] = ()
    forbidden_answer_fragments: tuple[str, ...] = ()


def _load_gold_cases() -> tuple[LiveCase, ...]:
    payload = json.loads(
        (REPO_ROOT / "eval/project_chat_quality_v1/onboarding_cases.json").read_text(
            encoding="utf-8"
        )
    )
    return tuple(
        LiveCase(
            question=str(case["question"]),
            relevant_paths=tuple(str(value) for value in case.get("acceptable_sources") or ()),
            surface_case_id=index,
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
        for index, case in enumerate(payload.get("cases") or (), 1)
    )


GOLD_CASES = _load_gold_cases()

NEGATIVE_CASES: tuple[str, ...] = ()


def _source_paths(payload: dict[str, object]) -> tuple[str, ...]:
    rows = payload.get("sources") or ()
    if not isinstance(rows, list):
        return ()
    result: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            value = str(row.get("path_or_url") or "").strip()
            if value:
                result.append(value)
    return tuple(result)


def _citations(payload: dict[str, object]) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for row in payload.get("sources") or ():
        if not isinstance(row, dict):
            continue
        citations.append({
            "path": str(row.get("path_or_url") or ""),
            "evidence_id": str(row.get("evidence_id") or ""),
            "content_sha256": str(row.get("content_sha256") or ""),
        })
    return citations


def _historical_paths() -> set[str]:
    catalog = yaml.safe_load((REPO_ROOT / "docatlas.project-docs.yaml").read_text(encoding="utf-8")) or {}
    return {
        str(row.get("path") or "")
        for row in catalog.get("documents") or ()
        if row.get("status") != "active"
    }


def _query_coverage(payload: dict[str, object]) -> float:
    value = payload.get("query_coverage")
    if value is None and payload.get("kind") == "docs_answer" and payload.get("answer_supported") is True:
        return float(payload.get("mandatory_coverage") or 1.0)
    if value in {"full", "complete"}:
        return 1.0
    if value in {"partial"}:
        return 0.5
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _validate_context_result(payload: dict[str, object]) -> str | None:
    kind = str(payload.get("kind") or "")
    if kind == "docs_answer":
        if payload.get("answer_supported") is not True or payload.get("answer_available") is not True:
            return "docs_answer lacks strict answer support"
    elif kind == "docs_context":
        if not (
            payload.get("context_status") == "ready"
            and payload.get("answer_supported") is False
            and payload.get("answer_available") is False
            and payload.get("edit_ready") is False
            and payload.get("answer_policy") == "cite_only"
            and isinstance(payload.get("facets"), list)
        ):
            return "docs_context violates the context-first safety contract"
    else:
        return f"unexpected result kind={kind!r}"
    for source in payload.get("sources") or ():
        if not isinstance(source, dict):
            return "source is not structured"
        digest = str(source.get("content_sha256") or "")
        if (
            not str(source.get("snippet") or "").strip()
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            return "source lacks a grounded snippet or content hash"
    return None


def _citation_integrity(payload: dict[str, object]) -> bool:
    answer_ids = {str(value) for value in payload.get("answer_evidence_ids") or ()}
    source_ids: set[str] = set()
    for source in payload.get("sources") or ():
        if not isinstance(source, dict):
            return False
        evidence_id = str(source.get("evidence_id") or "")
        path = str(source.get("path_or_url") or "")
        snippet = str(source.get("snippet") or "").strip()
        target = (REPO_ROOT / path).resolve()
        if (
            not evidence_id
            or not path
            or not target.is_relative_to(REPO_ROOT)
            or not target.is_file()
            or (
                snippet != path
                and snippet not in target.read_text(encoding="utf-8", errors="replace")
            )
        ):
            return False
        source_ids.add(evidence_id)
    return answer_ids.issubset(source_ids) and (not answer_ids or bool(source_ids))


def _threshold_failures(metrics: dict[str, object], case_count: int) -> list[str]:
    failures: list[str] = []
    if int(metrics["false_supported_count"]):
        failures.append("false-supported answers must be zero")
    if int(metrics["operational_contamination_count"]):
        failures.append("forbidden source contamination must be zero")
    if float(metrics["top1_relevance"]) < TOP1_RELEVANCE_MIN:
        failures.append("acceptable source must appear Top-1 for at least 80% of cases")
    if float(metrics["top3_relevance"]) < TOP3_RELEVANCE_MIN:
        failures.append("acceptable source must appear in Top-3 for at least 95% of cases")
    if int(metrics["false_abstention_count"]) > FALSE_ABSTENTION_MAX:
        failures.append("false abstentions exceed two")
    required_high_scores = math.ceil(case_count * SCORE_8_PLUS_RATE_MIN)
    if int(metrics["cases_scoring_8_plus"]) < required_high_scores:
        failures.append("fewer than 80% of cases scored at least 8")
    if float(metrics["mean_score"]) < MEAN_SCORE_MIN:
        failures.append("mean behavioral score is below 8")
    return failures


def run(
    output: Path | None = None,
    *,
    cases: tuple[LiveCase, ...] = GOLD_CASES,
    negative_cases: tuple[str, ...] = NEGATIVE_CASES,
) -> dict[str, object]:
    previous_home = os.environ.get("DOCATLAS_HOME")
    errors: list[str] = []
    results: list[dict[str, object]] = []
    historical_paths = _historical_paths()
    try:
        with TemporaryDirectory(prefix="docatlas-self-host-") as raw_tmp:
            tmp = Path(raw_tmp)
            os.environ["DOCATLAS_HOME"] = str(tmp / "home")
            config = DocmancerConfig()
            config.index.db_path = str(tmp / "docmancer.db")
            config.index.extracted_dir = str(tmp / "extracted")
            service = LibraryDocsService(
                config=config,
                config_source="explicit",
                registry=LibraryRegistry(config.index.db_path),
                agent=DocmancerAgent(config=config),
                job_tracker=DocsJobTracker(),
            )

            preflight_question = cases[0].question
            preflight = call_docs_tool_payload(
                "get_docs_context",
                {
                    "question": preflight_question,
                    "project_path": str(REPO_ROOT),
                    "mode": "project",
                },
                service,
            )
            preflight_action = (
                (preflight or {}).get("recommended_next_action")
                or (preflight or {}).get("next_action")
                or {}
            )
            action_patch = preflight_action.get("arguments_patch") or {}
            if action_patch.get("action") != "sync_project_docs":
                errors.append(f"pre-sync query did not recommend sync_project_docs: {preflight!r}")

            sync = service.sync_project_docs(str(REPO_ROOT), with_vectors=False)
            if getattr(sync, "status", None) != "success":
                errors.append(f"self-host sync status={getattr(sync, 'status', None)!r}")

            for index, case in enumerate(cases, 1):
                question = case.question
                payload = call_docs_tool_payload(
                    "get_docs_context",
                    {
                        "question": question,
                        "project_path": str(REPO_ROOT),
                        "mode": "project",
                    },
                    service,
                )
                if payload is None:
                    errors.append(f"{index:02d}: no payload: {question}")
                    continue
                status = str(payload.get("status") or "")
                observed_kind = str(payload.get("kind") or "")
                paths = _source_paths(payload)
                contract_error = (
                    None if case.expected_kind == "insufficient_evidence"
                    else _validate_context_result(payload)
                )
                relevant_sources = [
                    row for row in payload.get("sources") or ()
                    if isinstance(row, dict)
                    and str(row.get("path_or_url") or "") in case.relevant_paths
                ]
                visible = json.dumps(relevant_sources, ensure_ascii=False).casefold()
                fact_checks = {
                    fragment: fragment.casefold() in visible
                    for fragment in case.required_fragments
                }
                path_fact_checks = {
                    f"{path}:{fragment}": any(
                        str(row.get("path_or_url") or "") == path
                        and fragment.casefold() in json.dumps(row, ensure_ascii=False).casefold()
                        for row in payload.get("sources") or () if isinstance(row, dict)
                    )
                    for path, fragment in case.required_facts_by_path
                }
                answer_text = str(payload.get("answer") or "").casefold()
                answer_fact_checks = {
                    fragment: fragment.casefold() in answer_text
                    for fragment in case.required_fragments
                }
                answer_path_fact_checks = {
                    f"{path}:{fragment}": fragment.casefold() in answer_text
                    for path, fragment in case.required_facts_by_path
                }
                top3 = paths[:3]
                relevant_ranks = [rank for rank, path in enumerate(paths, 1) if path in case.relevant_paths]
                reciprocal_rank = 1.0 / relevant_ranks[0] if relevant_ranks else 0.0
                distractors = [
                    path for path in top3
                    if any(path.startswith(prefix) for prefix in case.forbidden_source_prefixes)
                ]
                forbidden_visible = json.dumps(payload, ensure_ascii=False).casefold()
                if case.expected_kind == "insufficient_evidence":
                    checks = {
                        "correct_abstention": status == "insufficient_evidence",
                        "not_false_supported": payload.get("answer_supported") is not True,
                    }
                else:
                    checks = {
                        "status_ok": status == "ok",
                        "kind_matches": case.expected_kind is None or observed_kind == case.expected_kind,
                        "source_backed": bool(paths),
                        "context_contract": contract_error is None,
                        "relevant_source_in_top3": any(path in case.relevant_paths for path in top3),
                        "required_facts": all((*fact_checks.values(), *path_fact_checks.values())),
                        "answer_contains_required_facts": (
                            observed_kind != "docs_answer"
                            or all((*answer_fact_checks.values(), *answer_path_fact_checks.values()))
                        ),
                        "citation_integrity": _citation_integrity(payload),
                        "no_forbidden_source": not distractors,
                        "no_forbidden_answer_fragment": not any(
                            fragment.casefold() in forbidden_visible
                            for fragment in case.forbidden_answer_fragments
                        ),
                    }
                score = round(10 * sum(checks.values()) / max(len(checks), 1), 2)
                result = {
                    "case_id": f"live_{index:02d}",
                    "surface_case_id": case.surface_case_id,
                    "question": question,
                    "expected": {
                        "kind": case.expected_kind,
                        "relevant_paths": list(case.relevant_paths),
                        "required_fragments": list(case.required_fragments),
                    },
                    "observed": {
                        "status": status,
                        "kind": payload.get("kind"),
                        "support_status": payload.get("support_status"),
                        "answer_supported": payload.get("answer_supported"),
                        "query_coverage": _query_coverage(payload),
                    },
                    "ranking": {
                        "top3_paths": list(top3),
                        "first_relevant_rank": relevant_ranks[0] if relevant_ranks else None,
                        "reciprocal_rank": reciprocal_rank,
                        "distractor_paths": distractors,
                        "historical_paths": [path for path in top3 if path in historical_paths],
                    },
                    "fact_checks": fact_checks,
                    "path_fact_checks": path_fact_checks,
                    "answer_fact_checks": answer_fact_checks,
                    "citations": _citations(payload),
                    "payload": payload,
                    "checks": checks,
                    "decision_hash": payload.get("decision_hash"),
                    "passed": all(checks.values()),
                    "score": score,
                }
                results.append(result)
                if (
                    case.expected_kind not in {None, "docs_answer"}
                    and payload.get("answer_supported") is True
                ):
                    errors.append(f"{index:02d}: false-supported answer: {question}")
                if distractors:
                    errors.append(f"{index:02d}: forbidden source contamination={distractors!r}: {question}")
                if case.expected_kind == "insufficient_evidence" and status != "insufficient_evidence":
                    errors.append(f"{index:02d}: nonexistent fact did not abstain: {question}")
                if paths and paths[0].startswith((".hermes/plans/", "roadmap/")) and not any(
                    token in question.casefold() for token in ("plan", "roadmap", "status")
                ):
                    errors.append(f"{index:02d}: operational query ranked a plan first: {paths[0]!r}: {question}")
            for question in negative_cases:
                payload = call_docs_tool_payload(
                    "get_docs_context",
                    {"question": question, "project_path": str(REPO_ROOT), "mode": "project"},
                    service,
                )
                if not payload or payload.get("status") != "insufficient_evidence":
                    errors.append(f"negative query did not fail closed: {question}: {payload!r}")
                results.append({
                    "case_id": "negative_lunar_quantum",
                    "question": question,
                    "expected": {"status": "insufficient_evidence"},
                    "observed": {
                        "status": (payload or {}).get("status"),
                        "kind": (payload or {}).get("kind"),
                        "support_status": (payload or {}).get("support_status"),
                        "answer_supported": (payload or {}).get("answer_supported"),
                    },
                    "checks": {"correct_abstention": bool(payload and payload.get("status") == "insufficient_evidence")},
                    "passed": bool(payload and payload.get("status") == "insufficient_evidence"),
                })
    finally:
        if previous_home is None:
            os.environ.pop("DOCATLAS_HOME", None)
        else:
            os.environ["DOCATLAS_HOME"] = previous_home

    positives = results[:len(cases)]
    source_count = sum(len(row.get("ranking", {}).get("top3_paths", ())) for row in positives)
    distractor_count = sum(len(row.get("ranking", {}).get("distractor_paths", ())) for row in positives)
    historical_count = sum(len(row.get("ranking", {}).get("historical_paths", ())) for row in positives)
    false_supported_count = sum(
        row.get("expected", {}).get("kind") not in {None, "docs_answer"}
        and row.get("observed", {}).get("answer_supported") is True
        for row in positives
    )
    scores = [float(row.get("score", 10.0 if row.get("passed") else 0.0)) for row in positives]
    failed_cases = [str(row.get("case_id")) for row in results if not row.get("passed")]
    if failed_cases:
        errors.append(f"failed cases: {failed_cases!r}")
    report: dict[str, object] = {
        "schema_version": "project-answer-quality-live-result-v1",
        "run_mode": "live_self_host",
        "provider_free": True,
        "case_count": len(results),
        "passed_count": sum(bool(row.get("passed")) for row in results),
        "metrics": {
            "top1_relevance": sum(
                bool(row.get("ranking", {}).get("first_relevant_rank") == 1)
                for row in positives
            ) / max(len(positives), 1),
            "top3_relevance": sum(bool(row.get("checks", {}).get("relevant_source_in_top3")) for row in positives) / max(len(positives), 1),
            "mrr": sum(float(row.get("ranking", {}).get("reciprocal_rank", 0.0)) for row in positives) / max(len(positives), 1),
            "distractor_rate": distractor_count / max(source_count, 1),
            "historical_source_rate": historical_count / max(source_count, 1),
            "mean_query_coverage": sum(float(row.get("observed", {}).get("query_coverage", 0.0)) for row in positives) / max(len(positives), 1),
            "false_abstention_count": sum(
                row.get("expected", {}).get("kind") != "insufficient_evidence"
                and not bool(row.get("checks", {}).get("status_ok"))
                for row in positives
            ),
            "false_supported_count": false_supported_count,
            "operational_contamination_count": distractor_count,
            "cases_scoring_8_plus": sum(score >= 8.0 for score in scores),
            "mean_score": sum(scores) / max(len(scores), 1),
        },
        "verdict": "FAIL" if errors else "PASS",
        "errors": errors,
        "results": results,
    }
    threshold_failures = _threshold_failures(report["metrics"], len(cases))
    if threshold_failures:
        errors.extend(threshold_failures)
        report["errors"] = errors
        report["verdict"] = "FAIL"
    digest_payload = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report["deterministic_result_digest"] = hashlib.sha256(digest_payload.encode()).hexdigest()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.output)
    if report["verdict"] == "PASS":
        print(
            f"PASS: {len(GOLD_CASES)} current-repository questions and "
            f"{len(NEGATIVE_CASES)} negative query close the unpatched context-first production path"
        )
        return 0
    print("FAIL: Project Docs self-hosting closure")
    for error in report["errors"]:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
