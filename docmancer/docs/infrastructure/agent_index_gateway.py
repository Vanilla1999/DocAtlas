from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Sequence

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.evidence_selection import (
    EvidenceRequirementSet,
    requirement_probe_query,
)
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import normalize_library_name
from docmancer.mcp import paths
from docmancer.retrieval.dispatch import RetrievalDispatcher


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
    ):
        if agent_factory is None:
            from docmancer.agent import DocmancerAgent

            agent_factory = DocmancerAgent
        self.config = config
        self._default_agent = default_agent
        self._agents: dict[str, Any] = {}
        self._agent_factory = agent_factory

    def index_config_for(self, record: LibraryRecord) -> DocmancerConfig:
        config = self.config.model_copy(deep=True)
        root = paths.docmancer_home() / "docs-indexes"
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
        dispatch_args: dict[str, Any] = {
            "mode": "lexical",
            "budget": budget,
            "filters": filters,
        }
        if requirements is not None:
            dispatch_args["requirements"] = requirements
        return RetrievalDispatcher(store=agent.store, config=agent.config).run(topic, **dispatch_args)

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
            self._agents.pop(record_or_library_id.canonical_id or record_or_library_id.library_id, None)
            self._agents.pop(record_or_library_id.library_id, None)
            return

        self._agents.pop(record_or_library_id, None)
