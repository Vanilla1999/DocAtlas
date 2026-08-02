from __future__ import annotations

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig, VectorStoreConfig
from docmancer.core.models import Document
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
from docmancer.docs.registry import LibraryRecord
from docmancer.embeddings.base import EmbeddingsProvider


class _SemanticStubProvider(EmbeddingsProvider):
    name = "semantic-stub"
    model_name = "semantic-stub-v1"
    dimensions = 2
    max_batch_size = 8

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        if "automobile" in normalized or "car" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]

    def embed(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, query):
        return self._vector(query)


def test_public_project_docs_query_consumes_dense_vector_index(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "1")
    monkeypatch.setattr(
        "docmancer.embeddings.get_embeddings_provider",
        lambda _config: _SemanticStubProvider(),
    )

    project = tmp_path / "project"
    project.mkdir()
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.embeddings.cache = str(tmp_path / "cache")
    config.embeddings.dimensions = 2
    config.retrieval.default_mode = "dense"
    config.vector_store = VectorStoreConfig(
        provider="sqlite-vec",
        options={"db_path": str(tmp_path / "vectors.db")},
    )
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [
            Document(
                source=str(project / "architecture.md"),
                content="# Transport\n\nThe automobile transport contract is authoritative.\n",
                metadata={
                    "format": "markdown",
                    "project_path": str(project),
                    "project_doc_path": "architecture.md",
                    "project_doc_authority": "source_of_truth",
                    "source_class": "project_file",
                    "project_docs": True,
                },
            )
        ],
        with_vectors=True,
    )
    service = LibraryDocsService(config=config, agent=agent)

    chunks = service.project_docs.query_project_docs(
        str(project),
        "car",
        tokens=1000,
        limit=5,
    )

    assert chunks
    assert "automobile" in chunks[0].text
    trace = chunks[0].metadata["retrieval_trace"]
    assert trace["requested_mode"] == "dense"
    assert trace["mode_used"] == "dense"
    assert "dense" in trace["component_ranks"]


def test_public_library_query_consumes_dense_vector_index(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "1")
    monkeypatch.setattr(
        "docmancer.embeddings.get_embeddings_provider",
        lambda _config: _SemanticStubProvider(),
    )
    config = DocmancerConfig()
    config.embeddings.cache = str(tmp_path / "cache")
    config.embeddings.dimensions = 2
    config.retrieval.default_mode = "dense"
    config.vector_store = VectorStoreConfig(
        provider="sqlite-vec",
        options={"db_path": str(tmp_path / "library-vectors.db")},
    )
    record = LibraryRecord(
        library_id="/pub/example/2.0/api",
        canonical_id="/pub/example/2.0/api",
        source_id="pub:example:api",
        name="example",
        normalized_name="example",
        ecosystem="pub",
        version="2.0",
        source_type="api",
        docs_url="https://example.test/api/",
        docs_url_template=None,
        aliases=[],
        status="available",
        added_at="2026-08-02T00:00:00+00:00",
        last_checked_at=None,
        last_refreshed_at=None,
        last_error=None,
    )
    gateway = AgentIndexGateway(config)
    agent = gateway.agent_instance(record)
    agent.ingest_documents(
        [
            Document(
                source="https://example.test/api/transport.html",
                content="# Transport\n\nThe automobile API is available in version 2.0.\n",
                metadata={
                    "format": "markdown",
                    "library_id": record.library_id,
                    "resolved_version": "2.0",
                    "source_class": "library_docs",
                },
            )
        ],
        with_vectors=True,
    )

    result = gateway.query_library(
        record,
        "car",
        filters={"library_id": record.library_id, "resolved_version": "2.0"},
    )

    assert result.chunks
    assert "automobile" in result.chunks[0].text
    assert result.mode_used == "dense"
    assert result.candidate_counts["dense"] == 1
