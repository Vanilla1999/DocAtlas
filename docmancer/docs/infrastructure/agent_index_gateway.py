from __future__ import annotations

from typing import Any, Callable

from docmancer.agent import DocmancerAgent
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
        agent_factory: Callable[..., Any] = DocmancerAgent,
    ):
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
        if self._default_agent is None:
            if record is None:
                self._default_agent = self._agent_factory(config=self.config)
            else:
                if record.library_id not in self._agents:
                    self._agents[record.library_id] = self._agent_factory(config=self.index_config_for(record))
                return self._agents[record.library_id]
        return self._default_agent

    def drop_library_agent(self, library_id: str) -> None:
        self._agents.pop(library_id, None)
