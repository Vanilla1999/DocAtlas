"""Thin library-service adapter for the existing provider-free eval harnesses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from docmancer.core.models import RetrievedChunk
from eval.evidence_selection_quality import evaluate_case
from eval.retrieval_quality_baseline import (
    _aggregate as aggregate_retrieval_results,
    _run_case as evaluate_retrieval_case,
)


DATA_ROOT = Path(__file__).resolve().parent / "library_retrieval_quality"
SPLITS = ("development", "holdout", "adversarial")


def load_cases() -> tuple[list[dict[str, Any]], dict[str, str]]:
    cases: list[dict[str, Any]] = []
    digests: dict[str, str] = {}
    for split in SPLITS:
        path = DATA_ROOT / f"{split}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw_case in payload["cases"]:
            cases.append({**raw_case, "split": split})
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return cases, digests


def evaluate_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [evaluate_case(case) for case in cases]


class _RankedCandidateStore:
    def __init__(self, candidates: list[dict[str, Any]], limit: int | None = None):
        ordered = sorted(candidates, key=lambda row: int(row.get("retrieval_rank") or 0))
        self._candidates = ordered[:limit] if limit is not None else ordered

    def query(self, _query: str, *, limit: int, budget: int) -> list[RetrievedChunk]:
        del budget
        return [
            RetrievedChunk(
                source=str(row["source"]),
                chunk_index=index,
                text=str(row["display_text"]),
                score=max(0.0, 1.0 - (index * 0.05)),
                metadata={
                    "title": row.get("parent_logical_id"),
                    "authority": row.get("authority"),
                    "version": row.get("version"),
                    "ranking": {"stable_id": row.get("stable_chunk_id")},
                },
            )
            for index, row in enumerate(self._candidates[:limit])
        ]


def _retrieval_case(case: dict[str, Any]) -> dict[str, Any]:
    expected_ids = set(case.get("expected_selected") or [])
    return {
        "id": case["case_id"],
        "query": case["question"],
        "taxonomy_class": case.get("taxonomy_class", "library_natural_language"),
        "expected_sources": [
            {"source": row["source"], "relevance": 1}
            for row in case["candidates"]
            if row.get("stable_chunk_id") in expected_ids
        ],
        "required_facts": list(case.get("required_facts") or []),
        "forbidden_sources": list(case.get("forbidden_sources") or []),
        "forbidden_versions": list(case.get("forbidden_versions") or []),
        "expected_authority": case.get("expected_authority", "official"),
        "expect_insufficient_evidence": case.get("expected_status") == "insufficient_evidence",
    }


def _mean_optional(values: list[bool | None]) -> float | None:
    applicable = [value for value in values if value is not None]
    if not applicable:
        return None
    return sum(bool(value) for value in applicable) / len(applicable)


def _output_modes_consistent(case: dict[str, Any]) -> bool | None:
    decisions = list((case.get("output_mode_decisions") or {}).values())
    if not decisions:
        return None
    canonical = {
        json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for decision in decisions
    }
    return len(canonical) == 1


def _required_code_group_pass(
    case: dict[str, Any], evidence_result: dict[str, Any]
) -> bool | None:
    required = [str(value).casefold() for value in case.get("required_code_group") or []]
    if not required:
        return None
    selected_ids = set(evidence_result.get("selected_stable_ids") or [])
    blocks = [
        str(block).casefold()
        for candidate in case["candidates"]
        if candidate.get("stable_chunk_id") in selected_ids
        for block in candidate.get("code_blocks") or []
    ]
    return any(all(fragment in block for fragment in required) for block in blocks)


def evaluate_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_results = evaluate_cases(cases)
    retrieval_results = [
        evaluate_retrieval_case(
            cast(Any, _RankedCandidateStore(case["candidates"])),
            case["split"],
            _retrieval_case(case),
        )
        for case in cases
    ]
    rank_one_results = [
        evaluate_retrieval_case(
            cast(Any, _RankedCandidateStore(case["candidates"], limit=1)),
            case["split"],
            _retrieval_case(case),
        )
        for case in cases
    ]
    _, digests = load_cases()
    expected_digest_path = DATA_ROOT / "digests.json"
    expected_digests = (
        json.loads(expected_digest_path.read_text(encoding="utf-8")).get("datasets", {})
        if expected_digest_path.exists()
        else {}
    )
    answerable = [
        result["status"] == "insufficient_evidence"
        for case, result in zip(cases, evidence_results, strict=True)
        if case["expected_status"] == "ok"
    ]
    unsupported = [
        result["status"] != "insufficient_evidence"
        for case, result in zip(cases, evidence_results, strict=True)
        if case["expected_status"] == "insufficient_evidence"
    ]
    partial_overlap = [
        result["status"] != "insufficient_evidence"
        for case, result in zip(cases, evidence_results, strict=True)
        if case.get("partial_overlap")
    ]
    return {
        "provider_free": True,
        "dataset_digests": digests,
        "dataset_digest_match": digests == expected_digests,
        "retrieval": {
            "cases": retrieval_results,
            "overall": aggregate_retrieval_results(retrieval_results),
        },
        "evidence_results": evidence_results,
        "derived": {
            "mandatory_requirement_coverage@1": _mean_optional(
                [row["metrics"]["required_fact_pass"] for row in rank_one_results]
            ),
            "mandatory_requirement_coverage@5": _mean_optional(
                [row["metrics"]["required_fact_pass"] for row in retrieval_results]
            ),
            "support_decision_consistency_rate": _mean_optional(
                [_output_modes_consistent(case) for case in cases]
            ),
            "answerable_abstention_rate": _mean_optional(answerable),
            "unsupported_answer_rate": _mean_optional(unsupported),
            "partial_overlap_false_positive_rate": _mean_optional(partial_overlap),
            "required_code_group_pass_rate": _mean_optional(
                [
                    _required_code_group_pass(case, result)
                    for case, result in zip(cases, evidence_results, strict=True)
                ]
            ),
        },
    }


__all__ = [
    "aggregate_retrieval_results",
    "evaluate_cases",
    "evaluate_report",
    "load_cases",
]
