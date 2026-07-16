"""Provider-free Task 40 chunk-size grid against the frozen Task 39 gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.embeddings.base import EmbeddingsProvider
from docmancer.embeddings.pipeline import sync_vector_store
from docmancer.stores.base import VectorHit, VectorPoint, VectorStore
from eval.retrieval_quality_baseline import (
    DATA_ROOT,
    RETRIEVAL_CONFIG,
    ROOT,
    SPLITS,
    _aggregate,
    _file_digest,
    _load_json,
    _paraphrase_group_gates,
    _run_case,
)


GRID = (160, 256, 384, 512)
TASK39_BASELINE = DATA_ROOT / "baseline_v1" / "summary.json"


class _GridProvider(EmbeddingsProvider):
    """Deterministic provider used to measure actual incremental sync work."""

    name = "task40-grid"
    model_name = "sha256-grid-v1"
    dimensions = 4

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [value / 255.0 for value in hashlib.sha256(text.encode()).digest()[:4]]
            for text in texts
        ]

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]


class _GridVectorStore(VectorStore):
    """In-memory vector backend; counts are real pipeline upserts/prunes."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, VectorPoint]] = {}

    def ensure_collection(
        self, name: str, dimensions: int, *, sparse: bool = False,
        options: dict | None = None,
    ) -> None:
        self.collections.setdefault(name, {})

    def upsert(
        self, collection: str, points: list[VectorPoint], *, bulk: bool = False
    ) -> None:
        target = self.collections.setdefault(collection, {})
        for point in points:
            target[str(point.id)] = point

    def search(
        self, collection: str, query_vector: list[float] | None, *,
        limit: int = 10, filters: dict | None = None,
        sparse_vector: dict[int, float] | None = None, mode: str = "dense",
    ) -> list[VectorHit]:
        return []

    def count(self, collection: str) -> int:
        return len(self.collections.get(collection, {}))

    def delete_points(self, collection: str, ids: list) -> int:
        target = self.collections.setdefault(collection, {})
        deleted = 0
        for point_id in ids:
            deleted += int(target.pop(str(point_id), None) is not None)
        return deleted

    def delete_collection(self, collection: str) -> None:
        self.collections.pop(collection, None)

    def health_check(self) -> bool:
        return True


def _stress_fixture() -> tuple[list[Document], list[dict[str, str]]]:
    filler = "Generic explanatory sentence without the requested identifier.\n" * 220
    code_lines = "\n".join(f"value_{index} = {index}" for index in range(220))
    table_rows = "\n".join(f"| key_{index} | value_{index} |" for index in range(180))
    list_rows = "\n".join(f"- policy item {index}" for index in range(220))
    documents = [
        Document(source="stress/long.md", content=f"# Long configuration\n\n{filler}LONG_SENTINEL=enabled\n"),
        Document(source="stress/headingless.md", content=f"{filler}HEADINGLESS_SENTINEL\n"),
        Document(source="stress/nested.md", content=f"# Same\n{filler}\n## Nested\nNESTED_SENTINEL\n\n# Same\nother version\n"),
        Document(source="stress/code.md", content=f"# Code\n\n```python\n{code_lines}\nCODE_SENTINEL = True\n```\n"),
        Document(source="stress/table.md", content=f"# Table\n\n| key | value |\n| --- | --- |\n{table_rows}\n| TABLE_SENTINEL | yes |\n"),
        Document(source="stress/list.md", content=f"# Policy\n\n{list_rows}\n- LIST_SENTINEL must hold\n"),
        Document(source="stress/unicode.md", content=f"Вводный русский текст.\n\n# Правила\n\n{filler}ЮНИКОД_МАРКЕР\n"),
        Document(
            source="stress/v1.md",
            content="# API\nShared duplicated API paragraph.\nVERSION_SENTINEL legacy forbidden\n",
            metadata={"version": "v1", "authority": "stale"},
        ),
        Document(
            source="stress/v2.md",
            content="# API\nShared duplicated API paragraph.\nVERSION_SENTINEL current required\n",
            metadata={"version": "v2", "authority": "official"},
        ),
    ]
    cases = [
        {"query": "LONG_SENTINEL", "source": "stress/long.md", "fact": "LONG_SENTINEL=enabled"},
        {"query": "HEADINGLESS_SENTINEL", "source": "stress/headingless.md", "fact": "HEADINGLESS_SENTINEL"},
        {"query": "NESTED_SENTINEL", "source": "stress/nested.md", "fact": "NESTED_SENTINEL"},
        {"query": "CODE_SENTINEL", "source": "stress/code.md", "fact": "CODE_SENTINEL = True"},
        {"query": "TABLE_SENTINEL", "source": "stress/table.md", "fact": "TABLE_SENTINEL"},
        {"query": "LIST_SENTINEL", "source": "stress/list.md", "fact": "LIST_SENTINEL"},
        {"query": "ЮНИКОД_МАРКЕР", "source": "stress/unicode.md", "fact": "ЮНИКОД_МАРКЕР"},
        {"query": "VERSION_SENTINEL current", "source": "stress/v2.md", "fact": "current required"},
    ]
    return documents, cases


def _stress_metrics(target: int | None) -> dict[str, Any]:
    documents, cases = _stress_fixture()
    if target is not None:
        documents = [
            document.model_copy(
                update={
                    "metadata": {
                        **document.metadata,
                        "format": "markdown",
                        "chunking_schema": "parent-child-v1",
                        "child_target_tokens": target,
                        "child_hard_max_tokens": max(512, target),
                    }
                }
            )
            for document in documents
        ]
    with tempfile.TemporaryDirectory(prefix="docatlas-task40-stress-") as temporary:
        store = SQLiteStore(Path(temporary) / "index.db")
        store.add_documents(documents, recreate=True)
        selected_tokens: list[int] = []
        failures: list[str] = []
        for case in cases:
            results = store.query(case["query"], limit=1, budget=20_000)
            if not results or results[0].source != case["source"] or case["fact"].casefold() not in results[0].text.casefold():
                failures.append(case["query"])
                continue
            selected_tokens.append(int(results[0].metadata["token_estimate"]))
        return {
            "cases": len(cases),
            "quality_pass": not failures and len(selected_tokens) == len(cases),
            "failures": failures,
            "selected_evidence_tokens_median": statistics.median(selected_tokens) if selected_tokens else None,
            "selected_evidence_tokens_mean": statistics.fmean(selected_tokens) if selected_tokens else None,
            "selected_evidence_tokens_max": max(selected_tokens, default=0),
        }


def _documents(corpus: dict[str, Any], target: int) -> list[Document]:
    return [
        Document(
            source=row["source"],
            content=row["content"],
            metadata={
                "title": row["title"],
                "authority": row["authority"],
                "version": row["version"],
                "corpus_id": corpus["corpus_id"],
                "format": "markdown",
                "chunking_schema": "parent-child-v1",
                "child_target_tokens": target,
                "child_hard_max_tokens": max(512, target),
            },
        )
        for row in corpus["documents"]
    ]


def compare_variant_to_task39(variant: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("corpus_digest", "dataset_digests", "retrieval_config_hash"):
        if variant.get(field) != baseline.get(field):
            errors.append(f"binding:{field}_mismatch")
    for case_id, frozen in (baseline.get("case_gates") or {}).items():
        current = (variant.get("case_gates") or {}).get(case_id)
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
        if current["model_visible_tokens"] > 800:
            errors.append(f"{case_id}:model_visible_budget_exceeded")
        if current["model_visible_tokens"] > frozen["model_visible_tokens"]:
            errors.append(f"{case_id}:model_visible_tokens_regressed")
    for split in SPLITS:
        current = variant["splits"][split]
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
    for group, frozen in (baseline.get("paraphrase_group_gates") or {}).items():
        current = (variant.get("paraphrase_group_gates") or {}).get(group)
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
        for metric in ("forbidden_source_violations", "forbidden_version_violations"):
            if current[metric] > frozen[metric]:
                errors.append(f"paraphrase:{group}:{metric}_regressed")
    return errors


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999) - 1))]


def _visible_overlap_duplicate_rate(rows: list[dict[str, Any]]) -> float:
    total_chars = 0
    duplicate_chars = 0
    by_source: dict[str, list[tuple[int, int]]] = {}
    for row in rows:
        start = int(row.get("char_start") or 0)
        end = int(row.get("char_end") or start)
        if end > start:
            by_source.setdefault(str(row["source"]), []).append((start, end))
            total_chars += end - start
    for spans in by_source.values():
        previous_end = -1
        for start, end in sorted(spans):
            if previous_end > start:
                duplicate_chars += min(previous_end, end) - start
            previous_end = max(previous_end, end)
    return duplicate_chars / total_chars if total_chars else 0.0


def _run_variant(target: int, corpus: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"docatlas-task40-{target}-") as temporary:
        root = Path(temporary)
        store = SQLiteStore(root / "index.db", root / "extracted")
        documents = _documents(corpus, target)
        config = DocmancerConfig()
        config.embeddings.cache = str(root / "embedding-cache")
        config.embeddings.dimensions = 4
        vector_store = _GridVectorStore()
        provider = _GridProvider()
        collection = f"task40_grid_{target}"
        started = time.perf_counter()
        indexed = store.add_documents(documents, recreate=True)
        initial_sync = sync_vector_store(
            store=store,
            config=config,
            provider=provider,
            vector_store=vector_store,
            collection=collection,
            generation_id=indexed.generation_id,
        )
        build_latency_ms = (time.perf_counter() - started) * 1_000
        rows = store.list_sections_for_embedding()
        token_sizes = [int(row["token_estimate"]) for row in rows]

        by_split: dict[str, list[dict[str, Any]]] = {}
        all_cases: list[dict[str, Any]] = []
        for split in SPLITS:
            dataset = _load_json(DATA_ROOT / f"{split}.json")
            cases = [_run_case(store, split, case) for case in dataset["cases"]]
            by_split[split] = cases
            all_cases.extend(cases)

        unchanged_generation = store.add_documents(
            documents, recreate=False, activate_generation=False
        )
        unchanged_sync = sync_vector_store(
            store=store,
            config=config,
            provider=provider,
            vector_store=vector_store,
            collection=collection,
            generation_id=unchanged_generation.generation_id,
            prune_stale=False,
        )
        store.activate_generation(str(unchanged_generation.generation_id))
        unchanged_prune = sync_vector_store(
            store=store,
            config=config,
            provider=provider,
            vector_store=vector_store,
            collection=collection,
            generation_id=unchanged_generation.generation_id,
            prune_stale=True,
        )
        unchanged = {
            int(row["section_id"]): str(row["content_hash"])
            for row in store.list_sections_for_embedding()
        }
        same_upserts = unchanged_sync.upserted

        edited = list(documents)
        first = edited[0]
        edited[0] = first.model_copy(update={"content": first.content + "\nLocal edit sentinel.\n"})
        before_ids = set(unchanged)
        edited_generation = store.add_documents(
            [edited[0]], recreate=False, activate_generation=False
        )
        edited_sync = sync_vector_store(
            store=store,
            config=config,
            provider=provider,
            vector_store=vector_store,
            collection=collection,
            generation_id=edited_generation.generation_id,
            prune_stale=False,
        )
        store.activate_generation(str(edited_generation.generation_id))
        edited_prune = sync_vector_store(
            store=store,
            config=config,
            provider=provider,
            vector_store=vector_store,
            collection=collection,
            generation_id=edited_generation.generation_id,
            prune_stale=True,
        )
        changed_rows = {
            int(row["section_id"]): str(row["content_hash"])
            for row in store.list_sections_for_embedding()
        }
        after_ids = set(changed_rows)
        changed_upserts = edited_sync.upserted

        variant = {
            "target_tokens": target,
            "hard_max_tokens": max(512, target),
            "corpus_digest": _file_digest(DATA_ROOT / "corpus.json"),
            "dataset_digests": {
                split: _file_digest(DATA_ROOT / f"{split}.json") for split in SPLITS
            },
            "retrieval_config_hash": hashlib.sha256(
                json.dumps(
                    RETRIEVAL_CONFIG,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "index_schema_version": "parent-child-v1",
            "indexed_sources": indexed.sources,
            "indexed_children": len(rows),
            "indexed_parents": store.collection_stats()["parent_sections_count"],
            "build_latency_ms": build_latency_ms,
            "index_bytes": (root / "index.db").stat().st_size,
            "chunk_stats": {
                "p50_tokens": statistics.median(token_sizes) if token_sizes else 0,
                "p95_tokens": _percentile(token_sizes, 0.95),
                "tiny_rate": sum(value < 40 for value in token_sizes) / len(token_sizes) if token_sizes else 0.0,
                "oversized_rate": sum(value > max(512, target) for value in token_sizes) / len(token_sizes) if token_sizes else 0.0,
                "visible_overlap_duplicate_rate": _visible_overlap_duplicate_rate(rows),
            },
            "incremental": {
                "initial_vector_upserts": initial_sync.upserted,
                "unchanged_reindex_upserts": same_upserts,
                "unchanged_reindex_pruned": unchanged_prune.pruned,
                "local_edit_retained": len(before_ids & after_ids),
                "local_edit_upserted": changed_upserts,
                "local_edit_pruned": edited_prune.pruned,
                "measured_by": "sync_vector_store",
            },
            "candidate_trace_hash": hashlib.sha256(
                json.dumps(
                    [
                        {
                            "case_id": f"{case['split']}:{case['id']}",
                            "candidates": case["candidates"],
                        }
                        for case in all_cases
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "case_gates": {
                f"{case['split']}:{case['id']}": {
                    "recall@5": case["metrics"]["recall@5"],
                    "reciprocal_rank": case["metrics"]["reciprocal_rank"],
                    "ndcg@20": case["metrics"]["ndcg@20"],
                    "required_fact_pass": case["metrics"]["required_fact_pass"],
                    "forbidden_source_violation": case["metrics"]["forbidden_source_violation"],
                    "forbidden_version_violation": case["metrics"]["forbidden_version_violation"],
                    "authoritative_source_at_1": case["metrics"]["authoritative_source_at_1"],
                    "exact_identifier_at_1": case["metrics"]["exact_identifier_at_1"],
                    "snippet_required_pass": case["metrics"]["snippet_required_pass"],
                    "insufficient_evidence_pass": case["metrics"]["insufficient_evidence_pass"],
                    "model_visible_tokens": case["metrics"]["model_visible_tokens"],
                    "projection_status": case["projection"]["status"],
                }
                for case in all_cases
            },
            "paraphrase_group_gates": _paraphrase_group_gates(all_cases),
            "splits": {split: _aggregate(cases) for split, cases in by_split.items()},
            "overall": _aggregate(all_cases),
            "stress_corpus": _stress_metrics(target),
        }
        errors = compare_variant_to_task39(variant, baseline)
        variant["quality_gate"] = {"status": "PASS" if not errors else "FAIL", "errors": errors}
        return variant


def run_grid(output_path: Path) -> dict[str, Any]:
    corpus = _load_json(DATA_ROOT / "corpus.json")
    baseline = _load_json(TASK39_BASELINE)
    stress_baseline = _stress_metrics(None)
    previous_home = os.environ.get("DOCMANCER_HOME")
    with tempfile.TemporaryDirectory(prefix="docatlas-task40-meta-") as metadata_home:
        os.environ["DOCMANCER_HOME"] = metadata_home
        try:
            variants = [_run_variant(target, corpus, baseline) for target in GRID]
        finally:
            if previous_home is None:
                os.environ.pop("DOCMANCER_HOME", None)
            else:
                os.environ["DOCMANCER_HOME"] = previous_home
    eligible = [
        row for row in variants
        if row["quality_gate"]["status"] == "PASS"
        and row["incremental"]["unchanged_reindex_upserts"] == 0
        and row["chunk_stats"]["oversized_rate"] == 0.0
        and row["chunk_stats"]["visible_overlap_duplicate_rate"] == 0.0
        and row["stress_corpus"]["quality_pass"]
        and row["stress_corpus"]["selected_evidence_tokens_median"]
            < stress_baseline["selected_evidence_tokens_median"]
    ]
    selected = min(
        eligible,
        key=lambda row: (
            row["stress_corpus"]["selected_evidence_tokens_mean"],
            row["stress_corpus"]["selected_evidence_tokens_max"],
            row["target_tokens"],
        ),
        default=None,
    )
    report = {
        "schema_version": "parent-child-grid-v1",
        "provider_free": True,
        "task39_baseline": TASK39_BASELINE.relative_to(ROOT).as_posix(),
        "stress_baseline": stress_baseline,
        "variants": variants,
        "selected_target_tokens": selected["target_tokens"] if selected else None,
        "selection_objective": [
            "task39_quality_gate_pass",
            "incremental_and_oversized_gate_pass",
            "stress_selected_evidence_tokens_mean_min",
            "stress_selected_evidence_tokens_max_min",
            "target_tokens_min",
        ],
        "status": "PASS" if selected else "INCONCLUSIVE",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_grid(args.output)
    print(json.dumps({"status": report["status"], "selected_target_tokens": report["selected_target_tokens"]}))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
