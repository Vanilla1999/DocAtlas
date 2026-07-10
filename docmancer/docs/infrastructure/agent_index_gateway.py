from __future__ import annotations

from typing import Any, Callable

from docmancer.core.config import DocmancerConfig
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import normalize_library_name
from docmancer.mcp import paths


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

    def drop_library_agent(self, record_or_library_id: LibraryRecord | str) -> None:
        if isinstance(record_or_library_id, LibraryRecord):
            self._agents.pop(record_or_library_id.canonical_id or record_or_library_id.library_id, None)
            self._agents.pop(record_or_library_id.library_id, None)
            return

        self._agents.pop(record_or_library_id, None)
