from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.evidence_selection import (
    build_requirements,
    library_docs_selection_config,
    select_evidence,
)
from docmancer.docs.application.library_docs_service import LibraryDocsApplicationService
from docmancer.docs.application.model_visible_projection import (
    decode_support_envelope,
    project_docs_answer,
)
from docmancer.docs.infrastructure.agent_index_gateway import LibraryWitnessProbe
from docmancer.docs.models import LibraryInfo
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


FIXTURES = Path(__file__).parent / "fixtures" / "library_docs"


def _load_manifest(ecosystem: str, name: str) -> dict[str, Any]:
    path = FIXTURES / ecosystem / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))






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
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
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







