"""Provider-free retrieval quality and token baseline for Task 39."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import INDEX_SCHEMA_VERSION, SQLiteStore, estimate_tokens
from docmancer.docs.application.model_visible_projection import project_docs_answer


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "eval" / "retrieval_quality"
SPLITS = ("development", "holdout", "adversarial")
RETRIEVAL_CONFIG = {
    "mode": "lexical",
    "candidate_limit": 20,
    "candidate_budget": 20_000,
    "selected_limit": 5,
    "projection_budget": 800,
    "ranking_revision": "fts5-explicit-utility-v1",
}
CODE_REVISION_PATHS = (
    ROOT / "docmancer" / "core" / "models.py",
    ROOT / "docmancer" / "core" / "sqlite_store.py",
    ROOT / "docmancer" / "docs" / "application" / "action_packet.py",
    ROOT / "docmancer" / "docs" / "application" / "model_visible_projection.py",
    ROOT / "docmancer" / "docs" / "domain" / "request_intent.py",
    ROOT / "eval" / "retrieval_quality_baseline.py",
)


def _legacy_golden_inventory() -> list[dict[str, str]]:
    paths = sorted((ROOT / "eval").glob("*_golden.yaml"))
    parity_dataset = ROOT / "eval" / "context7_parity" / "dataset.jsonl"
    if parity_dataset.exists():
        paths.append(parity_dataset)
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "digest": _file_digest(path),
            "execution_status": "snapshot_only_external_corpus",
            "reason": "no deterministic local fixture corpus is checked in",
        }
        for path in paths
    ]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_digest(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _code_revision() -> str:
    files = {
        path.relative_to(ROOT).as_posix(): _file_digest(path)
        for path in CODE_REVISION_PATHS
    }
    return _digest_bytes(_canonical_bytes(files))


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _mean(values: Iterable[float]) -> float:
    rows = list(values)
    return statistics.fmean(rows) if rows else 0.0


def _source_relevance(case: dict[str, Any]) -> dict[str, int]:
    return {
        str(row["source"]): int(row.get("relevance", 1))
        for row in case.get("expected_sources") or []
    }


def _ndcg(sources: list[str], relevance: dict[str, int], limit: int = 20) -> float:
    def dcg(grades: list[int]) -> float:
        return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))

    actual = dcg([relevance.get(source, 0) for source in sources[:limit]])
    ideal = dcg(sorted(relevance.values(), reverse=True)[:limit])
    return actual / ideal if ideal else 0.0


def _projection(question: str, chunks: list[RetrievedChunk]) -> dict[str, Any]:
    items = [
        {
            "source": chunk.source,
            "title": chunk.metadata.get("title"),
            "content": chunk.text,
            "version": chunk.metadata.get("version", "unversioned"),
        }
        for chunk in chunks[: RETRIEVAL_CONFIG["selected_limit"]]
    ]
    retrieval: dict[str, Any] = {"status": "success" if items else "unavailable"}
    if items:
        retrieval["primary_snippet"] = items[0]
        retrieval["supporting_snippets"] = items[1:]
    projection, _ = project_docs_answer(
        question=question,
        retrieval=retrieval,
        max_tokens=RETRIEVAL_CONFIG["projection_budget"],
    )
    return projection


def _candidate_trace(chunk: RetrievedChunk, rank: int) -> dict[str, Any]:
    metadata = chunk.metadata or {}
    excerpt = " ".join(chunk.text.split())[:200]
    return {
        "rank": rank,
        "stable_id": (metadata.get("ranking") or {}).get("stable_id"),
        "source": chunk.source,
        "section": metadata.get("title"),
        "content_sha256": metadata.get("content_hash") or _digest_bytes(chunk.text.encode()),
        "token_estimate": int(metadata.get("token_estimate") or estimate_tokens(chunk.text)),
        "authority": metadata.get("authority", "unknown"),
        "version": metadata.get("version", "unknown"),
        "ranking": metadata.get("ranking") or {},
        "excerpt": excerpt,
    }


def _run_case(store: SQLiteStore, split: str, case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    chunks = store.query(
        str(case["query"]),
        limit=RETRIEVAL_CONFIG["candidate_limit"],
        budget=RETRIEVAL_CONFIG["candidate_budget"],
    )
    latency_ms = (time.perf_counter() - started) * 1_000
    traces = [_candidate_trace(chunk, index) for index, chunk in enumerate(chunks, start=1)]
    selected = traces[: RETRIEVAL_CONFIG["selected_limit"]]
    sources = [row["source"] for row in traces]
    selected_sources = sources[: RETRIEVAL_CONFIG["selected_limit"]]
    relevance = _source_relevance(case)
    expected = set(relevance)
    expected_ranks = [index for index, source in enumerate(sources, start=1) if source in expected]
    first_rank = min(expected_ranks) if expected_ranks else None
    required_facts = [str(value) for value in case.get("required_facts") or []]
    forbidden_sources = set(str(value) for value in case.get("forbidden_sources") or [])
    forbidden_versions = set(str(value) for value in case.get("forbidden_versions") or [])
    projection = _projection(str(case["query"]), chunks)
    projection_sources = [
        row for row in projection.get("sources") or [] if isinstance(row, dict)
    ]
    projection_text = json.dumps(
        projection, ensure_ascii=False, sort_keys=True
    ).casefold()
    found_facts = [
        fact for fact in required_facts if fact.casefold() in projection_text
    ]
    projected_source_names = {
        str(row.get("path_or_url") or "") for row in projection_sources
    }
    projected_versions = {
        str(row.get("version_binding") or "") for row in projection_sources
    }
    forbidden_source_hits = sorted(forbidden_sources & projected_source_names)
    forbidden_version_hits = sorted(forbidden_versions & projected_versions)
    exact_identifier = str(case.get("exact_identifier") or "")
    top_projected_text = str(
        projection_sources[0].get("snippet") or ""
    ).casefold() if projection_sources else ""
    snippet_required = bool(case.get("requires_code_snippet"))
    snippet_present = bool(
        projection_sources
        and (
            "```" in str(projection_sources[0].get("snippet") or "")
            or (
                chunks
                and chunks[0].metadata.get("has_code_snippet")
                and chunks[0].source == projection_sources[0].get("path_or_url")
            )
        )
    )
    unique_sources = len(set(selected_sources))
    content_hashes = [str(row["content_sha256"]) for row in selected]
    duplicate_rate = 0.0 if not content_hashes else 1 - (len(set(content_hashes)) / len(content_hashes))
    expect_insufficient = bool(case.get("expect_insufficient_evidence"))
    insufficient_pass = (
        projection.get("status") == "insufficient_evidence"
        if expect_insufficient else None
    )
    authority_by_source = {
        str(row["source"]): str(row["authority"]) for row in traces
    }
    projected_top_authority = (
        authority_by_source.get(str(projection_sources[0].get("path_or_url") or ""))
        if projection_sources else None
    )

    metrics = {
        "recall@1": 1.0 if expected and set(sources[:1]) & expected else 0.0,
        "recall@3": len(set(sources[:3]) & expected) / len(expected) if expected else 0.0,
        "recall@5": len(set(sources[:5]) & expected) / len(expected) if expected else 0.0,
        "recall@20": len(set(sources[:20]) & expected) / len(expected) if expected else 0.0,
        "reciprocal_rank": 1 / first_rank if first_rank else 0.0,
        "ndcg@20": _ndcg(sources, relevance),
        "required_fact_pass": (
            len(found_facts) == len(required_facts) if required_facts else None
        ),
        "forbidden_source_violation": bool(forbidden_source_hits),
        "forbidden_version_violation": bool(forbidden_version_hits),
        "unknown_version_rate": (
            sum(1 for row in selected if row["version"] in {None, "", "unknown"}) / len(selected)
            if selected else 0.0
        ),
        "authoritative_source_at_1": bool(
            projected_top_authority == case.get("expected_authority")
        ) if case.get("expected_authority") else None,
        "exact_identifier_at_1": (
            bool(exact_identifier and exact_identifier.casefold() in top_projected_text)
            if exact_identifier else None
        ),
        "snippet_required_pass": snippet_present if snippet_required else None,
        "unique_sources@5": unique_sources,
        "duplicate_rate@5": duplicate_rate,
        "candidate_tokens": sum(int(row["token_estimate"]) for row in traces),
        "selected_evidence_tokens": sum(int(row["token_estimate"]) for row in selected),
        "model_visible_tokens": int(projection["estimated_tokens"]),
        "required_facts_per_1000_model_visible_tokens": (
            len(found_facts) * 1_000 / max(1, int(projection["estimated_tokens"]))
        ),
        "latency_ms": latency_ms,
        "degraded_mode": False,
        "insufficient_evidence_pass": insufficient_pass,
    }
    return {
        "schema_version": "retrieval-quality-case-result-v1",
        "id": case["id"],
        "split": split,
        "taxonomy_class": case["taxonomy_class"],
        "paraphrase_group": case.get("paraphrase_group"),
        "query": case["query"],
        "expected_sources": list(case.get("expected_sources") or []),
        "required_facts": required_facts,
        "found_facts": found_facts,
        "forbidden_source_hits": forbidden_source_hits,
        "forbidden_version_hits": forbidden_version_hits,
        "first_expected_rank": first_rank,
        "selected_evidence_ids": [row["stable_id"] for row in selected],
        "projection": {
            "status": projection["status"],
            "kind": projection["kind"],
            "estimated_tokens": projection["estimated_tokens"],
            "source_evidence_ids": [
                row.get("evidence_id") for row in projection.get("sources") or []
            ],
            "source_paths": [
                row.get("path_or_url") for row in projection_sources
            ],
            "source_content_hashes": [
                row.get("content_sha256") for row in projection_sources
            ],
        },
        "capabilities": {
            "lexical": "available",
            "dense": "not_requested",
            "sparse": "not_requested",
            "hybrid": "not_requested",
        },
        "metrics": metrics,
        "candidates": traces,
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    regular = [case for case in cases if case["expected_sources"]]
    metrics = [case["metrics"] for case in cases]
    def bool_rate(key: str) -> float | None:
        applicable = [row[key] for row in metrics if row[key] is not None]
        if not applicable:
            return None
        return _mean(1.0 if value else 0.0 for value in applicable)

    return {
        "cases": len(cases),
        "recall@1": _mean(row["recall@1"] for row in (case["metrics"] for case in regular)),
        "recall@3": _mean(row["recall@3"] for row in (case["metrics"] for case in regular)),
        "recall@5": _mean(row["recall@5"] for row in (case["metrics"] for case in regular)),
        "recall@20": _mean(row["recall@20"] for row in (case["metrics"] for case in regular)),
        "mrr": _mean(row["reciprocal_rank"] for row in (case["metrics"] for case in regular)),
        "ndcg@20": _mean(row["ndcg@20"] for row in (case["metrics"] for case in regular)),
        "required_fact_pass_rate": bool_rate("required_fact_pass"),
        "forbidden_source_violation_rate": bool_rate("forbidden_source_violation"),
        "forbidden_version_violation_rate": bool_rate("forbidden_version_violation"),
        "unknown_version_rate": _mean(row["unknown_version_rate"] for row in metrics),
        "authoritative_source_at_1_rate": bool_rate("authoritative_source_at_1"),
        "exact_identifier_at_1_rate": bool_rate("exact_identifier_at_1"),
        "snippet_required_pass_rate": bool_rate("snippet_required_pass"),
        "unique_sources@5_avg": _mean(row["unique_sources@5"] for row in metrics),
        "duplicate_rate@5_avg": _mean(row["duplicate_rate@5"] for row in metrics),
        "candidate_tokens_avg": _mean(row["candidate_tokens"] for row in metrics),
        "selected_evidence_tokens_avg": _mean(row["selected_evidence_tokens"] for row in metrics),
        "model_visible_tokens_avg": _mean(row["model_visible_tokens"] for row in metrics),
        "model_visible_tokens_max": max(
            (row["model_visible_tokens"] for row in metrics), default=0
        ),
        "required_facts_per_1000_model_visible_tokens": _mean(
            row["required_facts_per_1000_model_visible_tokens"] for row in metrics
        ),
        "retrieval_latency_ms_p50": _percentile([row["latency_ms"] for row in metrics], 0.50),
        "retrieval_latency_ms_p95": _percentile([row["latency_ms"] for row in metrics], 0.95),
        "degraded_mode_rate": bool_rate("degraded_mode"),
        "insufficient_evidence_pass_rate": bool_rate("insufficient_evidence_pass"),
    }


def _stable_case_result(case: dict[str, Any]) -> dict[str, Any]:
    stable = json.loads(json.dumps(case))
    stable["metrics"].pop("latency_ms", None)
    return stable


def _case_gate(case: dict[str, Any]) -> dict[str, Any]:
    metrics = case["metrics"]
    return {
        "recall@5": metrics["recall@5"],
        "reciprocal_rank": metrics["reciprocal_rank"],
        "ndcg@20": metrics["ndcg@20"],
        "required_fact_pass": metrics["required_fact_pass"],
        "forbidden_source_violation": metrics["forbidden_source_violation"],
        "forbidden_version_violation": metrics["forbidden_version_violation"],
        "authoritative_source_at_1": metrics["authoritative_source_at_1"],
        "exact_identifier_at_1": metrics["exact_identifier_at_1"],
        "snippet_required_pass": metrics["snippet_required_pass"],
        "insufficient_evidence_pass": metrics["insufficient_evidence_pass"],
        "model_visible_tokens": metrics["model_visible_tokens"],
        "projection_status": case["projection"]["status"],
    }


def _paraphrase_group_gates(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        group = str(case.get("paraphrase_group") or "").strip()
        if group:
            grouped.setdefault(group, []).append(case)
    return {
        group: {
            "case_ids": sorted(f"{case['split']}:{case['id']}" for case in rows),
            "minimum_recall@5": min(case["metrics"]["recall@5"] for case in rows),
            "minimum_reciprocal_rank": min(
                case["metrics"]["reciprocal_rank"] for case in rows
            ),
            "all_required_facts_pass": all(
                case["metrics"]["required_fact_pass"] is not False for case in rows
            ),
            "forbidden_source_violations": sum(
                bool(case["metrics"]["forbidden_source_violation"]) for case in rows
            ),
            "forbidden_version_violations": sum(
                bool(case["metrics"]["forbidden_version_violation"]) for case in rows
            ),
        }
        for group, rows in sorted(grouped.items())
        if len(rows) >= 2
    }


def run_baseline(output_dir: Path) -> dict[str, Any]:
    code_revision = _code_revision()
    corpus_path = DATA_ROOT / "corpus.json"
    corpus = _load_json(corpus_path)
    dataset_digests = {split: _file_digest(DATA_ROOT / f"{split}.json") for split in SPLITS}
    expected_digests = _load_json(DATA_ROOT / "digests.json")
    if dataset_digests != expected_digests.get("datasets") or _file_digest(corpus_path) != expected_digests.get("corpus"):
        raise ValueError("retrieval-quality dataset digest mismatch; freeze new data intentionally")

    case_dir = output_dir / "cases"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="docatlas-retrieval-quality-") as temporary:
        root = Path(temporary)
        store = SQLiteStore(root / "index.db", root / "extracted")
        documents = [
            Document(
                source=row["source"], content=row["content"],
                metadata={
                    "title": row["title"], "authority": row["authority"],
                    "version": row["version"], "corpus_id": corpus["corpus_id"],
                },
            )
            for row in corpus["documents"]
        ]
        index_result = store.add_documents(documents, recreate=True)
        by_split: dict[str, list[dict[str, Any]]] = {}
        all_cases: list[dict[str, Any]] = []
        for split in SPLITS:
            dataset = _load_json(DATA_ROOT / f"{split}.json")
            cases = [_run_case(store, split, case) for case in dataset["cases"]]
            by_split[split] = cases
            all_cases.extend(cases)
            for case in cases:
                (case_dir / f"{split}__{case['id']}.json").write_text(
                    json.dumps(case, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

    stable_digest = _digest_bytes(_canonical_bytes([_stable_case_result(case) for case in all_cases]))
    summary = {
        "schema_version": "retrieval-quality-baseline-v1",
        "provider_free": True,
        "fixture_backed_datasets_executed": [
            f"eval/retrieval_quality/{split}.json" for split in SPLITS
        ],
        "legacy_golden_inventory": _legacy_golden_inventory(),
        "code_revision": code_revision,
        "code_revision_kind": "source-content-sha256",
        "code_revision_files": [
            path.relative_to(ROOT).as_posix() for path in CODE_REVISION_PATHS
        ],
        "corpus_id": corpus["corpus_id"],
        "corpus_digest": _file_digest(corpus_path),
        "dataset_digests": dataset_digests,
        "index_revision": _digest_bytes(
            _canonical_bytes({"corpus": _file_digest(corpus_path), "schema": INDEX_SCHEMA_VERSION})
        ),
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "retrieval_config": RETRIEVAL_CONFIG,
        "retrieval_config_hash": _digest_bytes(_canonical_bytes(RETRIEVAL_CONFIG)),
        "indexed_sources": index_result.sources,
        "indexed_sections": index_result.sections,
        "deterministic_result_digest": stable_digest,
        "case_gates": {
            f"{case['split']}:{case['id']}": _case_gate(case)
            for case in all_cases
        },
        "paraphrase_group_gates": _paraphrase_group_gates(all_cases),
        "splits": {split: _aggregate(cases) for split, cases in by_split.items()},
        "overall": _aggregate(all_cases),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def compare_to_baseline(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in (
        "corpus_digest", "dataset_digests", "index_revision",
        "index_schema_version", "retrieval_config_hash",
    ):
        if summary.get(field) != baseline.get(field):
            errors.append(f"binding:{field}_mismatch")

    baseline_cases = baseline.get("case_gates") or {}
    current_cases = summary.get("case_gates") or {}
    if not baseline_cases:
        errors.append("baseline:missing_case_gates")
    for case_id, frozen in baseline_cases.items():
        current = current_cases.get(case_id)
        if current is None:
            errors.append(f"{case_id}:missing_case")
            continue
        if current["recall@5"] < frozen["recall@5"]:
            errors.append(f"{case_id}:recall@5_regressed")
        if current["reciprocal_rank"] < frozen["reciprocal_rank"]:
            errors.append(f"{case_id}:reciprocal_rank_regressed")
        if current["ndcg@20"] < frozen["ndcg@20"]:
            errors.append(f"{case_id}:ndcg@20_regressed")
        if frozen["required_fact_pass"] is True and current["required_fact_pass"] is not True:
            errors.append(f"{case_id}:required_fact_regressed")
        if not frozen["forbidden_source_violation"] and current["forbidden_source_violation"]:
            errors.append(f"{case_id}:forbidden_source_regressed")
        if not frozen["forbidden_version_violation"] and current["forbidden_version_violation"]:
            errors.append(f"{case_id}:forbidden_version_regressed")
        for field in (
            "authoritative_source_at_1", "exact_identifier_at_1",
            "snippet_required_pass", "insufficient_evidence_pass",
        ):
            if frozen.get(field) is True and current.get(field) is not True:
                errors.append(f"{case_id}:{field}_regressed")
        if current.get("projection_status") != frozen.get("projection_status"):
            errors.append(f"{case_id}:projection_status_regressed")
        if current["model_visible_tokens"] > RETRIEVAL_CONFIG["projection_budget"]:
            errors.append(f"{case_id}:model_visible_budget_exceeded")
        if current["model_visible_tokens"] > frozen["model_visible_tokens"]:
            errors.append(f"{case_id}:model_visible_tokens_regressed")

    for split in SPLITS:
        current = summary["splits"][split]
        frozen = baseline["splits"][split]
        for metric in (
            "recall@5", "mrr", "ndcg@20", "required_fact_pass_rate",
            "authoritative_source_at_1_rate", "exact_identifier_at_1_rate",
            "snippet_required_pass_rate", "insufficient_evidence_pass_rate",
        ):
            if frozen.get(metric) is None:
                continue
            if current.get(metric) is None:
                errors.append(f"{split}:{metric}_regressed")
                continue
            if current[metric] < frozen[metric]:
                errors.append(f"{split}:{metric}_regressed")
        for metric in ("forbidden_source_violation_rate", "forbidden_version_violation_rate"):
            if current[metric] > frozen[metric]:
                errors.append(f"{split}:{metric}_regressed")
    baseline_groups = baseline.get("paraphrase_group_gates") or {}
    current_groups = summary.get("paraphrase_group_gates") or {}
    for group, frozen in baseline_groups.items():
        current = current_groups.get(group)
        if current is None:
            errors.append(f"paraphrase:{group}:missing_group")
            continue
        if current.get("case_ids") != frozen.get("case_ids"):
            errors.append(f"paraphrase:{group}:case_ids_mismatch")
        for metric in ("minimum_recall@5", "minimum_reciprocal_rank"):
            if current[metric] < frozen[metric]:
                errors.append(f"paraphrase:{group}:{metric}_regressed")
        if frozen["all_required_facts_pass"] and not current["all_required_facts_pass"]:
            errors.append(f"paraphrase:{group}:required_facts_regressed")
        for metric in (
            "forbidden_source_violations", "forbidden_version_violations",
        ):
            if current[metric] > frozen[metric]:
                errors.append(f"paraphrase:{group}:{metric}_regressed")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args(argv)
    summary = run_baseline(args.output_dir)
    errors = compare_to_baseline(summary, _load_json(args.baseline)) if args.baseline else []
    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "summary": str(args.output_dir / "summary.json"),
        "deterministic_result_digest": summary["deterministic_result_digest"],
        "errors": errors,
    }, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
