from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.model_visible_projection import (
    decode_support_envelope,
    project_docs_answer,
)
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


FIXTURES = Path(__file__).parent / "fixtures" / "library_docs"


def _load_manifest(ecosystem: str, name: str) -> dict[str, Any]:
    path = FIXTURES / ecosystem / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_kotlin_gap_and_complete_corpora_share_identity_but_not_coverage():
    gap = _load_manifest("kotlinx_coroutines", "corpus_gap")
    complete = _load_manifest("kotlinx_coroutines", "corpus_complete")

    assert gap["library"] == complete["library"] == "kotlinx.coroutines"
    assert gap["version"] == complete["version"] == "1.8.1"
    assert gap["source_root"] == complete["source_root"]
    assert set(gap["documents"]) < set(complete["documents"])
    assert "composing-suspending-functions.md" not in gap["documents"]
    assert "composing-suspending-functions.md" in complete["documents"]


def test_non_kotlin_fixture_has_comparison_result_and_partial_distractor():
    corpus = _load_manifest("python_asyncio", "corpus_complete")

    requirements = corpus["requirements"]
    assert requirements["entities"] == ["create_task", "gather"]
    assert requirements["facets"] == ["comparison", "result_access"]
    assert corpus["distractor"] == "task-cancellation.md"
    assert corpus["authoritative"] == "task-results.md"


class RecordScopedGateway:
    """Provider-free stand-in for the record-specific lexical query boundary."""

    def __init__(self, root: Path, corpus: dict[str, Any]):
        self.root = root
        self.corpus = corpus
        self.library_id = ""
        self.queries: list[str] = []
        self.config: Any = None

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.queries.append(text)
        chunks = []
        for index, name in enumerate(self.corpus["documents"]):
            chunks.append(
                RetrievedChunk(
                    source=f"{self.corpus['source_root']}/{name}",
                    chunk_index=index,
                    text=(self.root / name).read_text(encoding="utf-8"),
                    score=1.0 - index / 100,
                    metadata={
                        "title": name,
                        "path": name,
                        "stable_chunk_id": name,
                        "library_id": self.library_id,
                        "canonical_id": self.library_id,
                        "version": self.corpus["version"],
                    },
                )
            )
        return chunks


def _retrieve(tmp_path: Path, monkeypatch, ecosystem: str, corpus_name: str, question: str):
    corpus = _load_manifest(ecosystem, corpus_name)
    root = FIXTURES / ecosystem
    gateway = RecordScopedGateway(root, corpus)
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "registry.sqlite3")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def gateway_factory(**kwargs):
        gateway.config = kwargs["config"]
        return gateway

    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent_factory=gateway_factory,
        job_tracker=DocsJobTracker(),
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library=corpus["library"],
        ecosystem="python" if ecosystem == "python_asyncio" else "kotlin",
        version=corpus["version"],
        source_type="web",
        docs_url=corpus["source_root"],
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    gateway.library_id = record.library_id
    marker = Path(service._index_config_for(record).index.extracted_dir) / "fixture.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("fixture index", encoding="utf-8")

    result = service.get_docs(
        corpus["library"],
        ecosystem=record.ecosystem,
        version=corpus["version"],
        source_type="web",
        topic=question,
        library_requirement_contract=corpus["requirements"],
    )
    projection, _ = project_docs_answer(
        question=question,
        retrieval={
            "status": result.status,
            "context_available": bool(result.results),
            "answer_available": bool(result.results),
            "context_pack": [
                {
                    "source": chunk.source,
                    "path": chunk.metadata.get("path"),
                    "content": chunk.content,
                    "version": result.resolved_version,
                    "docs_exactness": "exact",
                    "stable_chunk_id": chunk.metadata.get("stable_chunk_id"),
                    "parent_logical_id": f"fixture:{chunk.metadata.get('stable_chunk_id')}",
                    "display_content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    "authority": "official",
                }
                for chunk in result.results
            ],
            "selection_profile": "library_docs_answer",
            "selection_decision": result.selection_decision,
            "library_requirement_contract": corpus["requirements"],
            "requested_version": corpus["version"],
            "docs_exactness": "exact",
        },
    )
    return projection, result, gateway, corpus


def _support_payload(projection: dict[str, Any]) -> dict[str, Any]:
    envelope = projection.get("support_envelope")
    return decode_support_envelope(envelope) if envelope else projection


ASYNC_RESULT = "When should I use async instead of launch, and how do I obtain its result?"
LAUNCH_ONLY = "How do I launch a coroutine for work that does not return a result?"


def test_raw_topic_reaches_record_scoped_gateway_unprefixed(tmp_path, monkeypatch):
    _, result, gateway, corpus = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_complete", ASYNC_RESULT)
    assert result.status == "success"
    assert gateway.queries == [ASYNC_RESULT]
    assert gateway.queries[0] != f"{corpus['library']} {ASYNC_RESULT}"


def test_gap_is_operational_success_but_support_is_insufficient(tmp_path, monkeypatch):
    result, operational, _, _ = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_gap", ASYNC_RESULT)
    support = _support_payload(result)
    assert operational.status == result["operational_status"] == "success"
    assert result["context_available"] is True
    assert support["answer_supported"] is False
    assert support["support_status"] == "insufficient_evidence"
    assert any(value.startswith("facet:comparison:") for value in support["missing_requirement_ids"])
    assert any(value.startswith("facet:result_access:") for value in support["missing_requirement_ids"])


@pytest.mark.parametrize("corpus_name", ["corpus_gap", "corpus_complete"])
def test_launch_only_control_is_executably_answerable_on_both_corpora(tmp_path, monkeypatch, corpus_name):
    result, _, _, _ = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", corpus_name, LAUNCH_ONLY)
    assert result["answer_supported"] is True
    assert result["support_status"] == "supported"


@pytest.mark.parametrize("question", [
    "When should I use `async` instead of `launch`, and how do I obtain its result?",
    "Compare asynchronous result-producing work with fire-and-forget coroutine work and explain how the result is retrieved.",
])
def test_complete_english_queries_expose_complete_mandatory_support(tmp_path, monkeypatch, question):
    result, _, _, _ = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_complete", question)
    support = _support_payload(result)
    assert support["answer_supported"] is True
    assert support["support_status"] == "supported"
    assert support["missing_requirement_ids"] == []
    assert {"entity:async", "entity:launch", "facet:comparison:async:launch"} <= set(support["satisfied_requirement_ids"])
    assert any(value.startswith("facet:result_access:") for value in support["satisfied_requirement_ids"])
    assert support["selected_evidence_ids"]


def test_python_lowercase_comparison_and_result_query_is_executable(tmp_path, monkeypatch):
    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    result, operational, gateway, _ = _retrieve(tmp_path, monkeypatch, "python_asyncio", "corpus_complete", question)
    assert operational.status == "success"
    assert gateway.queries == [question]
    support = _support_payload(result)
    assert support["answer_supported"] is True
    assert {"entity:create_task", "entity:gather", "facet:comparison:create_task:gather"} <= set(support["satisfied_requirement_ids"])
    assert any(value.startswith("facet:result_access:") for value in support["satisfied_requirement_ids"])


def test_partial_overlap_cannot_authorize_answer_and_failure_is_bounded(tmp_path, monkeypatch):
    result, operational, _, _ = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_gap", "Compare async with launch and show how to obtain the async result")
    support = _support_payload(result)
    assert support["answer_supported"] is False
    assert support["missing_requirement_ids"]
    assert "rejected_candidates" not in result
    assert len(operational.selection_decision.omissions) <= 20


def test_complete_code_support_is_one_source_version_and_code_block(tmp_path, monkeypatch):
    _, operational, _, _ = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_complete", "Show code comparing async and launch and awaiting the async result")
    groups = [item for item in operational.requirements if item.kind == "code_group"]
    assert len(groups) == 1
    assert groups[0].requirement_id in operational.satisfied_requirement_ids


def test_exact_source_and_version_contamination_is_zero(tmp_path, monkeypatch):
    _, operational, _, corpus = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_complete", "Compare async and launch and explain await")
    assert operational.results
    assert all((chunk.source or "").startswith(corpus["source_root"]) for chunk in operational.results)
    assert all(chunk.metadata["version"] == corpus["version"] for chunk in operational.results)


def test_russian_lexical_query_is_honestly_unsupported(tmp_path, monkeypatch):
    result, _, _, _ = _retrieve(tmp_path, monkeypatch, "kotlinx_coroutines", "corpus_complete", "Сравни запуск корутины с получением результата и объясни как получить результат")
    assert result["answer_supported"] is False
    assert result["support_status"] == "insufficient_evidence"
