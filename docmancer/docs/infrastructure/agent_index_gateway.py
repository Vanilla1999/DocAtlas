from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Callable, Sequence

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.evidence_selection import (
    EvidenceRequirementSet,
    requirement_probe_query,
)
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import normalize_library_name
from docmancer.mcp import paths
from docmancer.retrieval.runtime import dispatcher_for_agent, effective_retrieval_mode
from docmancer.retrieval.contracts import canonical_hash


@dataclass(frozen=True, slots=True)
class LibraryWitnessProbe:
    """Bounded raw index evidence for classifying an insufficient answer."""

    status: str
    queried_requirement_ids: tuple[str, ...] = ()
    chunks: tuple[Any, ...] = ()
    failure_count: int = 0


class AgentIndexGateway:
    def __init__(
        self,
        config: DocmancerConfig,
        *,
        default_agent: Any | None = None,
        agent_factory: Callable[..., Any] | None = None,
        library_index_root: Path | str | None = None,
    ):
        if agent_factory is None:
            from docmancer.agent import DocmancerAgent

            agent_factory = DocmancerAgent
        self.config = config
        self._default_agent = default_agent
        self._agents: dict[str, Any] = {}
        self._retrieval_dispatchers: dict[int, tuple[tuple[Any, ...], Any]] = {}
        self._agent_factory = agent_factory
        self._library_index_root = Path(library_index_root).expanduser().resolve() if library_index_root else None

    def index_config_for(self, record: LibraryRecord) -> DocmancerConfig:
        config = self.config.model_copy(deep=True)
        root = self._library_index_root or paths.docmancer_home() / "docs-indexes"
        root.mkdir(parents=True, exist_ok=True)
        safe = normalize_library_name(record.library_id) or "library"
        config.index.db_path = str(root / f"{safe}.db")
        config.index.extracted_dir = str(root / safe / "extracted")
        return config

    def agent_instance(self, record: LibraryRecord | None = None) -> Any:
        if record is not None:
            key = record.canonical_id or record.library_id
            if key not in self._agents:
                self._agents[key] = self._agent_factory(config=self.index_config_for(record))
            return self._agents[key]

        if self._default_agent is None:
            self._default_agent = self._agent_factory(config=self.config)
        return self._default_agent

    def agent_for_config(self, config: DocmancerConfig) -> Any:
        """Create an uncached agent for an isolated staging index."""
        return self._agent_factory(config=config)

    def query_library(
        self,
        record: LibraryRecord,
        topic: str,
        *,
        budget: int | None = None,
        filters: dict[str, Any] | None = None,
        requirements: Any | None = None,
    ) -> Any:
        """Run the dispatcher against the isolated index for one library record."""
        agent = self.agent_instance(record)
        if not hasattr(agent, "store"):
            return agent.query(topic, budget=budget)
        mode = effective_retrieval_mode(agent.config)
        dispatch_args: dict[str, Any] = {
            "mode": mode,
            "budget": budget,
            "filters": filters,
        }
        if requirements is not None:
            dispatch_args["requirements"] = requirements
        return self.dispatcher_for(agent, mode=mode).run(topic, **dispatch_args)

    def dispatcher_for(self, agent: Any, *, mode: str | None = None) -> Any:
        """Return the mode-aware dispatcher used by public project-doc queries."""
        effective_mode = effective_retrieval_mode(agent.config, mode)
        collection_fn = getattr(agent, "_vector_collection_name", None)
        collection = collection_fn() if callable(collection_fn) else ""
        embeddings = getattr(agent.config, "embeddings", None)
        vector_store = getattr(agent.config, "vector_store", None)
        cache_key = (
            effective_mode,
            collection,
            getattr(embeddings, "provider", None),
            getattr(embeddings, "model", None),
            getattr(embeddings, "dimensions", None),
            getattr(vector_store, "provider", None),
            getattr(vector_store, "url", None),
            canonical_hash(getattr(vector_store, "options", {}) or {}),
        )
        cached = self._retrieval_dispatchers.get(id(agent))
        if cached is not None and cached[0] == cache_key:
            return cached[1]
        dispatcher = dispatcher_for_agent(agent, mode=effective_mode)
        self._retrieval_dispatchers[id(agent)] = (cache_key, dispatcher)
        return dispatcher

    def _drop_dispatcher_for_agent(self, agent: Any | None) -> None:
        if agent is not None:
            self._retrieval_dispatchers.pop(id(agent), None)

    def probe_library_requirements(
        self,
        record: LibraryRecord,
        requirements: EvidenceRequirementSet,
        *,
        missing_requirement_ids: Sequence[str],
        filters: dict[str, Any] | None = None,
        max_requirements: int = 4,
        max_results_per_requirement: int = 3,
        budget: int = 120,
    ) -> LibraryWitnessProbe:
        """Query the same isolated lexical index after a support miss.

        This deliberately bypasses dispatcher ranking only for diagnostics: it
        proves that a missing requirement exists in the bounded record index,
        never turns a witness into a user-facing answer.
        """

        agent = self.agent_instance(record)
        store = getattr(agent, "store", None)
        if store is None or not callable(getattr(store, "query", None)):
            return LibraryWitnessProbe(status="unavailable")
        missing = set(str(value) for value in missing_requirement_ids)
        ordered = [
            requirement for requirement in requirements
            if requirement.requirement_id in missing and requirement.mandatory
        ][:max(1, int(max_requirements))]
        queries = [
            (requirement.requirement_id, requirement_probe_query(requirement))
            for requirement in ordered
        ]
        queries = [(requirement_id, query) for requirement_id, query in queries if query]
        if not queries:
            return LibraryWitnessProbe(status="not_applicable")
        per_query_budget = max(1, int(budget) // len(queries))
        chunks: list[Any] = []
        seen: set[str] = set()
        failures = 0
        for _, query in queries:
            try:
                rows = store.query(
                    query,
                    limit=max(1, int(max_results_per_requirement)),
                    budget=per_query_budget,
                    filters=filters,
                )
            except Exception:
                failures += 1
                continue
            for chunk in rows or ():
                metadata = getattr(chunk, "metadata", None) or {}
                identity = str(
                    metadata.get("stable_chunk_id")
                    or metadata.get("section_id")
                    or hashlib.sha256(
                        f"{getattr(chunk, 'source', '')}\0{getattr(chunk, 'text', '')}".encode()
                    ).hexdigest()
                )
                if identity not in seen:
                    seen.add(identity)
                    chunks.append(chunk)
        status = (
            "ok" if chunks else
            "unavailable" if failures == len(queries) else
            "incomplete" if failures else
            "no_witness"
        )
        return LibraryWitnessProbe(
            status=status,
            queried_requirement_ids=tuple(requirement_id for requirement_id, _ in queries),
            chunks=tuple(chunks),
            failure_count=failures,
        )

    def drop_library_agent(self, record_or_library_id: LibraryRecord | str) -> None:
        if isinstance(record_or_library_id, LibraryRecord):
            first = self._agents.pop(
                record_or_library_id.canonical_id or record_or_library_id.library_id,
                None,
            )
            second = self._agents.pop(record_or_library_id.library_id, None)
            self._drop_dispatcher_for_agent(first)
            self._drop_dispatcher_for_agent(second)
            return

        self._drop_dispatcher_for_agent(self._agents.pop(record_or_library_id, None))
