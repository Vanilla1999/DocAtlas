from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.evidence_selection import SelectionDecision
from docmancer.docs.application.model_visible_projection import (
    estimate_projection_tokens,
    project_docs_answer,
    validate_model_visible_projection,
)
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


class RecordingAgent:
    def __init__(self, chunks=None):
        self.chunks = chunks or []
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[str] = []
        self.config = None

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if self.config is not None:
            marker = Path(self.config.index.extracted_dir) / "chunk.md"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("indexed chunk", encoding="utf-8")
        return 1

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append(text)
        return self.chunks


def _service(tmp_path, monkeypatch, agent: RecordingAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    agent = agent or RecordingAgent()
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def agent_factory(**kwargs):
        agent.config = kwargs.get("config")
        return agent

    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent,
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )


def _register(service: LibraryDocsService, *, library: str, ecosystem: str | None = None, version: str | None = None, docs_url: str, source_type: str | None = "api", indexed: bool = True):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library=library,
        ecosystem=ecosystem,
        version=version,
        source_type=source_type,
        docs_url=docs_url,
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    if indexed:
        config = service._index_config_for(record)
        marker = Path(config.index.extracted_dir) / "chunk.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("indexed chunk", encoding="utf-8")
    return record


def _chunk(text: str, source: str, metadata: dict):
    return RetrievedChunk(source=source, chunk_index=0, text=text, score=1.0, metadata=metadata)






ZLIB_EVIDENCE_QUESTION = (
    "How does Python 3.13 zlib.Decompress.decompress(data, max_length) limit returned output, "
    "and what do eof, unused_data, and unconsumed_tail mean? Return source-backed evidence only."
)

ZLIB_EVIDENCE_PARAPHRASES = (
    (
        "How does Python 3.13 zlib.Decompress.decompress(data, max_length) limit returned output? "
        "Explain eof plus unused_data and unconsumed_tail."
    ),
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), describe these "
        "Decompress attributes: eof, unused_data, and unconsumed_tail."
    ),
    (
        "In Python 3.13, explain max_length for zlib.Decompress.decompress(data, max_length); "
        "give the meaning of eof / unused_data / unconsumed_tail."
    ),
)

ZLIB_DELIMITER_PROSE_CONTROLS = (
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), explain output and data "
        "for this workflow.",
        {"output", "data"},
    ),
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), describe these fields: "
        "output, data.",
        {"output", "data"},
    ),
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), give the semantics of "
        "bytes / output.",
        {"bytes", "output"},
    ),
)


def _oversized_zlib_source() -> str:
    return "\n".join([
        "zlib — Compression compatible with gzip",
        "==========================================",
        "",
        ".. module:: zlib",
        "",
        *("General compression background that does not describe the requested API." for _ in range(900)),
        "",
        ".. attribute:: Decompress.unused_data",
        "",
        "   A bytes object which contains any bytes past the end of the compressed data.",
        "",
        ".. attribute:: Decompress.unconsumed_tail",
        "",
        "   A bytes object that contains compressed input not consumed because output was limited.",
        "",
        ".. attribute:: Decompress.eof",
        "",
        "   A boolean indicating whether the end of the compressed data stream has been reached.",
        "",
        ".. method:: Decompress.decompress(data, max_length=0)",
        "",
        "   If max_length is non-zero, the returned output is no longer than max_length.",
    ])


def _zlib_fixture_service(tmp_path, monkeypatch) -> LibraryDocsService:
    source_url = "https://docs.python.org/3.13/_sources/library/zlib.rst.txt"
    library_id = "python:python@3.13:api"
    chunk = _chunk(
        _oversized_zlib_source(),
        source_url,
        {
            "stable_chunk_id": "python-3.13-zlib-source",
            "library_id": library_id,
            "canonical_id": library_id,
            "ecosystem": "python",
            "version": "3.13",
            "source_type": "api",
            "docset_root": "https://docs.python.org",
        },
    )
    service = _service(tmp_path, monkeypatch, RecordingAgent([chunk]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        docs_url=source_url,
        target_spec={"seed_urls": [source_url]},
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    marker = Path(service._index_config_for(record).index.extracted_dir) / "chunk.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("indexed chunk", encoding="utf-8")
    return service


def _public_library_projection(question: str, result, *, max_tokens: int = 800):
    context_pack = [
        {
            "source": chunk.source,
            "content": chunk.content,
            "version": result.resolved_version,
            "docs_exactness": "exact",
            "stable_chunk_id": chunk.metadata.get("stable_chunk_id"),
            "parent_logical_id": chunk.metadata.get("parent_logical_id") or chunk.source,
            "display_content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
            "authority": "official",
        }
        for chunk in result.results
    ]
    return project_docs_answer(
        question=question,
        retrieval={
            "status": result.status,
            "context_available": bool(result.results),
            "answer_available": bool(result.results),
            "context_pack": context_pack,
            "selection_profile": "library_docs_answer",
            "selection_decision": result.selection_decision,
            "requested_version": "3.13",
            "docs_exactness": "exact",
        },
        canonical_selection=result.selection_decision,
        max_tokens=max_tokens,
    )[0]


def _python_direct_text_result(
    tmp_path,
    monkeypatch,
    metadata: dict,
    *,
    chunk_source: str = "https://docs.python.org/3.13/library/base64.html",
):
    source_url = "https://docs.python.org/3.13/library/base64.html"
    chunk = _chunk(
        "Python 3.13 base64.b64encode encodes bytes with the Base64 alphabet.",
        chunk_source,
        {"stable_chunk_id": "probe", **metadata},
    )
    service = _service(tmp_path, monkeypatch, RecordingAgent([chunk]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        docs_url=source_url,
        target_spec={"seed_urls": [source_url]},
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    marker = Path(service._index_config_for(record).index.extracted_dir) / "chunk.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("indexed chunk", encoding="utf-8")
    return service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic="base64 b64encode",
    )




























