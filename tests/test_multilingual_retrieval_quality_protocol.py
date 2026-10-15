from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.core.config import EmbeddingsConfig
from docmancer.core._sqlite_store_shared import _stable_source_identity
from docmancer.embeddings.fastembed_provider import FastEmbedProvider
from eval.multilingual_retrieval_matrix_adapter import (
    ProductionMultilingualMatrixAdapter,
    _matrix_documents,
    _matrix_result,
    _preflight_dense_model,
)
from eval.multilingual_retrieval_quality_protocol import (
    _profile_activation_eligible,
    evaluate_results,
    load_frozen_corpus,
    run_matrix,
    validate_corpus,
    validate_protocol_lock,
)


def _corpus() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for language_pair in ("en-en", "ru-en", "ru-ru"):
        for case_index in range(5):
            rows.append({
                "id": f"docatlas-{language_pair}-{case_index}",
                "project_id": "docatlas",
                "language_pair": language_pair,
                "split": ("development", "holdout", "adversarial")[case_index % 3],
                "taxonomy": "architecture",
                "semantic_family": f"{language_pair}-{case_index}",
                "self_hosting_control": True,
            })
    rows[0]["multi_concept_gold_spans"] = ["a:1-2", "b:3-4"]
    rows[0]["expected_source_spans"] = ["a:1-2", "b:3-4"]
    rows[1]["wrong_project_distractor"] = True
    rows[2]["absent_fact"] = True
    return rows


def _result_rows(*, candidate: bool = True) -> list[dict[str, object]]:
    rows = _corpus()
    for index, row in enumerate(rows):
        expected = f"source:{index}"
        absent = bool(row.get("absent_fact"))
        row.update({
            "expected_source_spans": [] if absent else [expected],
            "retrieved_source_spans": [expected] if candidate and not absent else [],
            "requested_mode": "hybrid",
            "mode_used": "hybrid",
            "fallback_used": False,
            "candidate_counts": {"dense": 5},
            "dense_contributed": True,
            "answer_kind": "insufficient_evidence" if row.get("absent_fact") else "docs_context",
            "wrong_project_evidence_accepted": 0,
            "visible_sources": [] if absent or not candidate else [{
                "project_identity": str(row["project_id"]),
                "content_sha256": "a" * 64,
                "line_start": 1,
                "line_end": 2,
                "span_id": expected,
                "path": "README.md",
                "section": "Fixture",
            }],
        })
    return rows


def _write_frozen_corpus(root: Path) -> None:
    content = "Frozen DocAtlas documentation."
    projects = [{
        "id": "docatlas",
        "project_identity": "git:github.com/Vanilla1999/DocAtlas",
        "revision": "5da60e24cacebf6350411087eb4983597774895a",
        "self_hosting_control": True,
        "documents": [
            {
                "span_id": f"docatlas:fixture-{index}.md:1-1",
                "path": f"fixture-{index}.md",
                "section": "Fixture",
                "content": content,
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "line_start": 1,
                "line_end": 1,
            }
            for index in range(6)
        ],
    }]
    payloads: dict[str, object] = {
        "corpus.json": {
            "schema_version": "multilingual-retrieval-quality-corpus-v1",
            "projects": projects,
        },
    }
    for split in ("development", "holdout", "adversarial"):
        cases = []
        for language_pair in ("en-en", "ru-en", "ru-ru"):
            for index in range(5):
                row: dict[str, object] = {
                    "id": f"{split}-{language_pair}-docatlas-{index}",
                    "project_id": "docatlas",
                    "language_pair": language_pair,
                    "query": f"Question about DocAtlas {index}",
                    "taxonomy": "architecture",
                    "semantic_family": f"{split}-{language_pair}-{index}",
                    "expected_source_spans": ["docatlas:fixture-0.md:1-1"],
                }
                cases.append(row)
        payloads[f"{split}.json"] = {
            "schema_version": "multilingual-retrieval-quality-cases-v1",
            "cases": cases,
        }
    development = payloads["development.json"]["cases"]  # type: ignore[index]
    development[0]["expected_source_spans"] = [
        "docatlas:fixture-0.md:1-1", "docatlas:fixture-1.md:1-1",
    ]
    development[0]["multi_concept_gold_spans"] = list(
        development[0]["expected_source_spans"]
    )
    development[1]["wrong_project_distractor"] = True
    development[2]["absent_fact"] = True
    development[2]["query"] = "Unknown fact that is absent"
    development[2]["expected_source_spans"] = []

    digests: dict[str, str] = {}
    for filename, payload in payloads.items():
        path = root / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        digests[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "digests.json").write_text(json.dumps({
        "schema_version": "multilingual-retrieval-quality-digests-v1",
        "files": digests,
    }, sort_keys=True), encoding="utf-8")





































