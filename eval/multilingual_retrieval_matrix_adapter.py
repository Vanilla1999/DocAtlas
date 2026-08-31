"""Production retrieval adapter for the frozen multilingual matrix."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig, VectorStoreConfig
from docmancer.core.models import Document
from docmancer.retrieval.runtime import dispatcher_for_agent
from eval.multilingual_retrieval_quality_protocol import FrozenCorpus, validate_protocol_lock


class ProductionMultilingualMatrixAdapter:
    """Build one isolated production index and execute strict retrieval modes."""

    def __init__(self, *, qdrant_url: str | None = None, model_cache: str | None = None):
        self.qdrant_url = qdrant_url or os.environ.get("DOCATLAS_EVAL_QDRANT_URL")
        self.model_cache = model_cache or os.environ.get("DOCATLAS_EVAL_MODEL_CACHE")
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._dispatcher: Any = None
        self._agent: DocmancerAgent | None = None
        self._candidate_collection: str | None = None
        self._cleanup_error: Exception | None = None
        self._projects: dict[str, Mapping[str, Any]] = {}

    def __call__(
        self, system: Mapping[str, Any], case: Mapping[str, Any], corpus: FrozenCorpus,
    ) -> Mapping[str, Any]:
        if self._dispatcher is None:
            self._build(corpus)
        project = self._projects[str(case["project_id"])]
        result = self._dispatcher.run(
            str(case["query"]),
            mode=str(system["requested_mode"]),
            limit=5,
            expand="none",
            filters={"project_identity": project["project_identity"]},
            allow_degraded=False,
        )
        return _matrix_result(case, result)

    def _build(self, corpus: FrozenCorpus) -> None:
        if not self.qdrant_url:
            raise RuntimeError(
                "production multilingual matrix requires DOCATLAS_EVAL_QDRANT_URL"
            )
        lock = validate_protocol_lock()
        model = lock["model_configuration"]
        self._temporary = tempfile.TemporaryDirectory(prefix="docatlas-multilingual-matrix-")
        root = Path(self._temporary.name)
        self._projects = {str(project["id"]): project for project in corpus.projects}
        documents = _matrix_documents(corpus)
        previous_model_cache = os.environ.get("DOCATLAS_FASTEMBED_CACHE_DIR")
        previous_home = os.environ.get("DOCATLAS_HOME")
        os.environ["DOCATLAS_HOME"] = str(root / "home")
        effective_cache = self.model_cache or str(root / "models")
        os.environ["DOCATLAS_FASTEMBED_CACHE_DIR"] = effective_cache
        try:
            _preflight_dense_model(
                str(model["dense_model"]), int(model["dense_dimensions"]), effective_cache,
            )
            config = DocmancerConfig()
            config.index.db_path = str(root / "index.sqlite")
            config.index.extracted_dir = str(root / "extracted")
            config.retrieval.default_mode = "hybrid"
            config.retrieval.fusion.method = str(model["fusion"])
            config.retrieval.fusion.rrf_k = int(model["rrf_k"])
            config.embeddings.provider = str(model["dense_provider"])
            config.embeddings.model = str(model["dense_model"])
            config.embeddings.dimensions = int(model["dense_dimensions"])
            config.embeddings.sparse_model = str(model["sparse_model"])
            config.embeddings.cache = effective_cache
            config.vector_store = VectorStoreConfig(
                provider="qdrant",
                url=self.qdrant_url,
                collection=f"docatlas_multilingual_matrix_{uuid.uuid4().hex}",
            )
            agent = DocmancerAgent(config=config)
            self._agent = agent
            prepare_generation = agent.prepare_vector_generation

            def _capture_candidate(generation_id: str | None = None) -> str:
                collection = prepare_generation(generation_id)
                self._candidate_collection = collection
                return collection

            agent.prepare_vector_generation = _capture_candidate  # type: ignore[method-assign]
            agent.ingest_documents(documents, recreate=True, with_vectors=True)
            self._dispatcher = dispatcher_for_agent(agent, mode="hybrid")
        except Exception:
            self._cleanup_candidate(preserve_error=True)
            raise
        finally:
            if previous_home is None:
                os.environ.pop("DOCATLAS_HOME", None)
            else:
                os.environ["DOCATLAS_HOME"] = previous_home
            if previous_model_cache is None:
                os.environ.pop("DOCATLAS_FASTEMBED_CACHE_DIR", None)
            else:
                os.environ["DOCATLAS_FASTEMBED_CACHE_DIR"] = previous_model_cache

    def close(self) -> None:
        cleanup_error: Exception | None = None
        try:
            self._cleanup_candidate(preserve_error=False)
        except Exception as exc:
            cleanup_error = exc
        finally:
            self._agent = None
            self._dispatcher = None
            if self._temporary is not None:
                self._temporary.cleanup()
                self._temporary = None
        if cleanup_error is not None:
            raise cleanup_error

    def _cleanup_candidate(self, *, preserve_error: bool) -> None:
        if self._agent is not None and self._candidate_collection:
            from docmancer.stores.base import get_vector_store

            try:
                store = get_vector_store(
                    self._agent.config.vector_store,
                    embeddings_dim=self._agent.config.embeddings.dimensions,
                )
                store.delete_collection(self._candidate_collection)
                self._candidate_collection = None
            except Exception as exc:
                self._cleanup_error = exc
                if not preserve_error:
                    raise


def _preflight_dense_model(model: str, dimensions: int, cache_dir: str) -> None:
    from fastembed import TextEmbedding

    supported = {
        str(item.get("model") or item.get("model_name") or "")
        for item in TextEmbedding.list_supported_models()
        if isinstance(item, Mapping)
    }
    if model not in supported:
        raise ValueError(f"frozen FastEmbed model is not supported: {model}")
    embedding = TextEmbedding(model_name=model, cache_dir=cache_dir)
    vector = next(iter(embedding.embed(["dimension preflight"])))
    if len(vector) != dimensions:
        raise ValueError(
            f"frozen FastEmbed model dimension mismatch: expected {dimensions}, got {len(vector)}"
        )


def _matrix_documents(corpus: FrozenCorpus) -> list[Document]:
    return [
        Document(
            source=f"{project['id']}::{document['span_id']}",
            content=str(document["content"]),
            metadata={
                "source_identity": f"{project['id']}::{document['span_id']}",
                "format": "markdown",
                "span_id": str(document["span_id"]),
                "source_path": str(document["path"]),
                "project_doc_path": str(document["path"]),
                "project_identity": str(project["project_identity"]),
                "project_id": str(project["id"]),
                "revision": str(project["revision"]),
                "content_sha256": str(document["content_sha256"]),
                "line_start": int(document["line_start"]),
                "line_end": int(document["line_end"]),
                "section": str(document["section"]),
                "source_class": "project_file",
                "project_docs": True,
            },
        )
        for project in corpus.projects
        for document in project.get("documents") or ()
    ]


def _matrix_result(case: Mapping[str, Any], result: Any) -> dict[str, Any]:
    chunks = list(result.chunks)
    contributions = {
        str(section_id): dict(component_ranks)
        for section_id, component_ranks in result.contributions.items()
    }
    returned_contributions = {
        str(chunk.metadata.get("section_id")): contributions.get(
            str(chunk.metadata.get("section_id")), {}
        )
        for chunk in chunks
        if chunk.metadata.get("section_id") is not None
    }
    span_ids = list(dict.fromkeys(
        str(chunk.metadata.get("span_id") or "") for chunk in chunks
        if chunk.metadata.get("span_id")
    ))
    visible_sources = [
        {
            "span_id": str(chunk.metadata.get("span_id") or ""),
            "project_identity": str(chunk.metadata.get("project_identity") or ""),
            "content_sha256": str(chunk.metadata.get("content_sha256") or ""),
            "line_start": chunk.metadata.get("line_start"),
            "line_end": chunk.metadata.get("line_end"),
            "path": str(chunk.metadata.get("project_doc_path") or chunk.metadata.get("source_path") or ""),
            "section": str(chunk.metadata.get("section") or ""),
        }
        for chunk in chunks
    ]
    return {
        "id": case["id"],
        "retrieved_source_spans": span_ids,
        "retrieved_chunks": [chunk.model_dump(mode="json") for chunk in chunks],
        "mode_used": result.mode_used,
        "failures": dict(result.failures),
        "candidate_counts": dict(result.candidate_counts),
        "retrieval_contributions": returned_contributions,
        "dense_contributed": any(
            "dense" in component_ranks
            for component_ranks in returned_contributions.values()
        ),
        "visible_sources": visible_sources,
    }


__all__ = ["ProductionMultilingualMatrixAdapter"]
