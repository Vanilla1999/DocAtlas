from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.core._sqlite_store_shared import _stable_source_identity
from eval.multilingual_retrieval_matrix_adapter import (
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
        "revision": "c9d009dffba11a3a19a4afe9b31b5061d09409d9",
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
    development[0]["multi_concept_gold_spans"] = ["concept-a", "concept-b"]
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


def test_protocol_lock_and_corpus_shape_are_validated():
    validate_protocol_lock()
    inventory = validate_corpus(_corpus())
    assert inventory == {"case_count": 15, "project_count": 1, "self_hosting_only": True}


def test_corpus_rejects_external_project_evidence():
    rows = _corpus()
    rows[0]["project_id"] = "external-project"
    rows[0]["self_hosting_control"] = False
    with pytest.raises(ValueError, match="project_count, self_hosting_only"):
        validate_corpus(rows)


def test_passing_candidate_must_beat_baseline_without_fallback():
    report = evaluate_results(_result_rows(), _result_rows(candidate=False))
    assert report["verdict"] == "PASS"
    assert report["metrics"]["recall_at_5_overall"] == 1.0
    assert report["metrics"]["degraded_or_fallback_runs"] == 0


def test_lexical_fallback_cannot_count_as_hybrid_success():
    candidate = _result_rows()
    candidate[0]["mode_used"] = "lexical"
    candidate[0]["fallback_used"] = True
    report = evaluate_results(candidate, _result_rows(candidate=False))
    assert report["verdict"] == "FAIL"
    assert report["checks"]["no_degraded_or_fallback_runs"] is False


def test_wrong_project_evidence_fails_closed():
    candidate = _result_rows()
    candidate[0]["wrong_project_evidence_accepted"] = 1
    report = evaluate_results(candidate, _result_rows(candidate=False))
    assert report["checks"]["wrong_project_free"] is False


def test_missing_source_provenance_fails_gate():
    candidate = _result_rows()
    candidate[0]["visible_sources"] = [{"project_identity": "project-0"}]
    report = evaluate_results(candidate, _result_rows(candidate=False))
    assert report["checks"]["source_provenance_complete"] is False


def test_retrieved_sources_require_visible_provenance():
    candidate = _result_rows()
    candidate[0]["visible_sources"] = []
    report = evaluate_results(candidate, _result_rows(candidate=False))
    assert report["checks"]["source_provenance_complete"] is False


def test_absent_fact_retrieval_is_scored_separately_from_recall():
    candidate = _result_rows()
    absent = next(row for row in candidate if row.get("absent_fact"))
    absent["retrieved_source_spans"] = ["misleading:1"]
    report = evaluate_results(candidate, _result_rows(candidate=False))
    assert report["metrics"]["recall_at_5_overall"] == 1.0
    assert report["metrics"]["absent_fact_candidate_source_spans"] == 1


def test_every_retrieved_span_requires_visible_provenance():
    candidate = _result_rows()
    candidate[0]["retrieved_source_spans"].append("hidden:span")  # type: ignore[union-attr]
    report = evaluate_results(candidate, _result_rows(candidate=False))
    assert report["checks"]["source_provenance_complete"] is False


def test_frozen_corpus_binds_all_files_and_source_spans(tmp_path):
    _write_frozen_corpus(tmp_path)
    corpus = load_frozen_corpus(tmp_path)
    assert len(corpus.projects) == 1
    assert len(corpus.cases) == 45

    (tmp_path / "holdout.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch: holdout.json"):
        load_frozen_corpus(tmp_path)


def test_matrix_documents_have_unique_identity_for_spans_from_the_same_path():
    corpus = load_frozen_corpus()
    documents = _matrix_documents(corpus)
    identities = [_stable_source_identity(document) for document in documents]
    assert len(identities) == len(set(identities))


def test_matrix_executes_locked_systems_without_changing_default(tmp_path):
    _write_frozen_corpus(tmp_path)

    def adapter(system, case, corpus):
        assert "expected_source_spans" not in case
        assert "absent_fact" not in case
        assert "split" not in case
        assert not corpus.cases
        retrieved = [] if system["id"] == "open-lexical" or "Unknown fact" in case["query"] else [
            corpus.projects[0]["documents"][0]["span_id"]
        ]
        document = corpus.projects[0]["documents"][0]
        return {
            "id": case["id"],
            "retrieved_source_spans": retrieved,
            "mode_used": system["requested_mode"],
            "fallback_used": False,
            "answer_kind": "docs_context",
            "wrong_project_evidence_accepted": 0,
            "visible_sources": [] if not retrieved else [{
                "project_identity": corpus.projects[0]["project_identity"],
                "content_sha256": document["content_sha256"],
                "line_start": document["line_start"],
                "line_end": document["line_end"],
                "span_id": document["span_id"],
                "path": document["path"],
                "section": document["section"],
            }],
        }

    report = run_matrix(adapter, tmp_path)
    assert report["default_retrieval_changed"] is False
    assert report["external_generalization_claimed"] is False
    assert set(report["systems"]) == {
        "open-lexical", "open-multilingual-dense", "open-hybrid-rrf",
    }
    assert all(
        result["verdict"] == "PASS"
        for result in report["evaluations_against_open_lexical"].values()
    )
    assert all(
        result["verdict"] == "PASS"
        for result in report["holdout_evaluations_against_open_lexical"].values()
    )
    assert report["corpus_bound_to_protocol"] is False
    assert report["profile_activation_eligible"] is False


def test_activation_requires_full_and_holdout_verdicts():
    passing = {"dense": {"verdict": "PASS"}}
    failing = {"dense": {"verdict": "FAIL"}}

    assert _profile_activation_eligible(True, passing, passing) is True
    assert _profile_activation_eligible(True, failing, passing) is False
    assert _profile_activation_eligible(True, passing, failing) is False
    assert _profile_activation_eligible(False, passing, passing) is False


def test_production_adapter_serializes_real_chunks_and_provenance():
    class Result:
        mode_used = "dense"
        failures = {}
        chunks = [RetrievedChunk(
            source="docatlas::span-1",
            chunk_index=0,
            text="Bounded documentation evidence.",
            score=0.9,
            metadata={
                "span_id": "span-1",
                "project_identity": "project-1",
                "content_sha256": "a" * 64,
                "line_start": 3,
                "line_end": 7,
                "project_doc_path": "docs/guide.md",
                "section": "Guide",
            },
        )]

    row = _matrix_result({"id": "case-1"}, Result())
    assert row["retrieved_source_spans"] == ["span-1"]
    assert row["retrieved_chunks"][0]["text"] == "Bounded documentation evidence."
    assert row["visible_sources"] == [{
        "span_id": "span-1",
        "project_identity": "project-1",
        "content_sha256": "a" * 64,
        "line_start": 3,
        "line_end": 7,
        "path": "docs/guide.md",
        "section": "Guide",
    }]


def test_protocol_freezes_supported_multilingual_mpnet_model():
    model = validate_protocol_lock()["model_configuration"]
    assert model["dense_model"] == "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    assert model["dense_dimensions"] == 768


def test_dense_model_preflight_rejects_unsupported_registry_entry(monkeypatch, tmp_path):
    class FakeEmbedding:
        @staticmethod
        def list_supported_models():
            return [{"model": "some/other-model"}]

    import fastembed
    monkeypatch.setattr(fastembed, "TextEmbedding", FakeEmbedding)

    with pytest.raises(ValueError, match="not supported"):
        _preflight_dense_model("missing/model", 768, str(tmp_path))
