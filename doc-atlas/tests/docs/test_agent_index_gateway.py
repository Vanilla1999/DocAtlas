from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
from docmancer.docs.registry import LibraryRecord


class FakeAgent:
    def __init__(self, *, config):
        self.config = config
        self.add_calls = []
        self.query_calls = []

    def add(self, url, **kwargs):
        self.add_calls.append((url, kwargs))
        return 1

    def query(self, query, **kwargs):
        self.query_calls.append((query, kwargs))
        return []


def _record(library_id="/pub/riverpod/2.0/api"):
    return LibraryRecord(
        library_id=library_id,
        source_id="pub:riverpod:api",
        canonical_id=library_id,
        name="riverpod",
        normalized_name="riverpod",
        ecosystem="pub",
        version="2.0",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/2.0/",
        docs_url_template=None,
        aliases=[],
        status="available",
        added_at="2024-01-01T00:00:00+00:00",
        last_checked_at=None,
        last_refreshed_at=None,
        last_error=None,
    )


def test_index_config_for_preserves_library_specific_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    gateway = AgentIndexGateway(config, agent_factory=FakeAgent)

    index_config = gateway.index_config_for(_record())

    assert Path(index_config.index.db_path) == tmp_path / "home" / "docs-indexes" / "pub-riverpod-2-0-api.db"
    assert Path(index_config.index.extracted_dir) == tmp_path / "home" / "docs-indexes" / "pub-riverpod-2-0-api" / "extracted"
    assert config.index.db_path != index_config.index.db_path


def test_agent_instance_caches_per_library_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record()

    first = gateway.agent_instance(record)
    second = gateway.agent_instance(record)
    other = gateway.agent_instance(_record("/pub/flutter/stable/api"))

    assert first is second
    assert other is not first
    first.add("https://example.com", recreate=False, max_pages=2)
    first.query("widgets", budget=100)
    assert first.add_calls == [("https://example.com", {"recreate": False, "max_pages": 2})]
    assert first.query_calls == [("widgets", {"budget": 100})]


def test_agent_instance_uses_injected_default_agent_for_all_records(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    default = FakeAgent(config=DocmancerConfig())
    gateway = AgentIndexGateway(DocmancerConfig(), default_agent=default, agent_factory=FakeAgent)

    assert gateway.agent_instance() is default
    assert gateway.agent_instance(_record()) is default
