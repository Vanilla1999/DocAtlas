from __future__ import annotations

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig, VectorStoreConfig
from docmancer.core.models import Document
from docmancer.docs.service import LibraryDocsService
from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
from docmancer.docs.registry import LibraryRecord
from docmancer.embeddings.base import EmbeddingsProvider
from docmancer.retrieval.dispatch import RetrievalDispatcher


class _SemanticStubProvider(EmbeddingsProvider):
    name = "semantic-stub"
    model_name = "semantic-stub-v1"
    dimensions = 2
    max_batch_size = 8

    def __init__(self):
        self.query_calls = 0

    @staticmethod
    def _vector(text: str) -> list[float]:
        normalized = text.casefold()
        if "automobile" in normalized or "car" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]

    def embed(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, query):
        self.query_calls += 1
        return self._vector(query)


def test_public_project_docs_query_consumes_dense_vector_index(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DOCMANCER_AUTO_VECTORS", "1")
    provider = _SemanticStubProvider()
    monkeypatch.setattr(
        "docmancer.embeddings.get_embeddings_provider",
        lambda _config: provider,
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
                source=str(project / "guide.md"),
                content="# Guide\n\nA car guide is useful but only supporting.\n",
                metadata={
                    "format": "markdown",
                    "project_path": str(project),
                    "project_doc_path": "guide.md",
                    "project_doc_authority": "supporting",
                    "source_class": "project_file",
                    "project_docs": True,
                },
            ),
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
    assert chunks[0].source.endswith("architecture.md")
    assert provider.query_calls == 1
    trace = chunks[0].metadata["retrieval_trace"]
    assert trace["requested_mode"] == "dense"
    assert trace["mode_used"] == "dense"
    assert "dense" in trace["component_ranks"]

    authoritative = service.agent_gateway.dispatcher_for(agent, mode="dense").run(
        "car",
        mode="dense",
        filters={
            "project_path": str(project),
            "source_class": "project_file",
            "authority": "source_of_truth",
        },
    )
    assert len(authoritative.chunks) == 1
    assert authoritative.chunks[0].source.endswith("architecture.md")
    assert provider.query_calls == 1


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


def test_lexical_vector_readiness_is_bounded_and_does_not_touch_vectors(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    agent = DocmancerAgent(config=config)
    dispatcher = RetrievalDispatcher(store=agent.store, config=config)

    assert dispatcher.vector_readiness("lexical") == {
        "schema_version": "vector-readiness-v1",
        "status": "not_required",
        "mode": "lexical",
    }


def test_vector_readiness_does_not_expose_collection_or_point_ids(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.retrieval.default_mode = "dense"
    agent = DocmancerAgent(config=config)
    dispatcher = RetrievalDispatcher(
        store=agent.store, config=config, vector_store=object(),
        provider=_SemanticStubProvider(), collection="secret-collection-id",
    )

    diagnostic = dispatcher.vector_readiness()

    assert diagnostic == {
        "schema_version": "vector-readiness-v1",
        "status": "not_ready",
        "mode": "dense",
        "reason_code": "metadata_unverified",
        "collection_id": "sha256:63f3b22128229bc0",
    }
    assert "secret-collection-id" not in str(diagnostic)


def test_legacy_empty_backend_identity_fails_closed(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.retrieval.default_mode = "dense"
    agent = DocmancerAgent(config=config)
    agent.store.add_documents([Document(
        source="old", content="# Old\n\nalpha",
        metadata={"format": "markdown", "chunking_schema": "parent-child-v1"},
    )])
    collection = str(agent.store.generation_info()["vector_collection"])

    diagnostic = RetrievalDispatcher(
        store=agent.store, config=config, vector_store=object(),
        provider=_SemanticStubProvider(), collection=collection,
    ).vector_readiness()

    assert diagnostic["reason_code"] == "unverified_backend_identity"


def test_vector_activation_failure_preserves_old_generation(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    agent = DocmancerAgent(config=config)
    agent.store.add_documents([Document(
        source="old", content="# Old\n\nqueryable marker",
        metadata={"format": "markdown", "chunking_schema": "parent-child-v1"},
    )])
    active = agent.store.active_generation_id()
    candidate = agent.store.add_documents(
        [Document(source="new", content="# New\n\nreplacement")],
        activate_generation=False,
    )

    try:
        agent.store.activate_generation(candidate.generation_id, require_vector_witness=True)
    except ValueError:
        pass
    else:
        raise AssertionError("activation without parity witness succeeded")

    assert agent.store.active_generation_id() == active
    assert agent.store.query("queryable marker", limit=1, budget=1000)
