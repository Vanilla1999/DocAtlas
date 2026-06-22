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


def _record(library_id="/pub/riverpod/2.0/api", canonical_id=None):
    return LibraryRecord(
        library_id=library_id,
        source_id="pub:riverpod:api",
        canonical_id=canonical_id or library_id,
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


def _record_with_canonical_id(library_id, canonical_id):
    return _record(library_id, canonical_id=canonical_id)


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


def test_project_query_uses_default_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    default = FakeAgent(config=DocmancerConfig())
    gateway = AgentIndexGateway(DocmancerConfig(), default_agent=default, agent_factory=FakeAgent)

    assert gateway.agent_instance() is default


def test_library_query_uses_per_library_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    default = FakeAgent(config=DocmancerConfig())
    gateway = AgentIndexGateway(DocmancerConfig(), default_agent=default, agent_factory=FakeAgent)

    library_agent = gateway.agent_instance(_record())

    assert library_agent is not default
    assert Path(library_agent.config.index.db_path) == tmp_path / "home" / "docs-indexes" / "pub-riverpod-2-0-api.db"


def test_default_agent_created_by_project_does_not_hijack_library_query(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)

    default = gateway.agent_instance()
    library_agent = gateway.agent_instance(_record())

    assert library_agent is not default
    assert Path(default.config.index.db_path) != Path(library_agent.config.index.db_path)


def test_agent_key_based_on_canonical_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)

    first = gateway.agent_instance(_record_with_canonical_id("/python/click", "python:click:8.1"))
    second = gateway.agent_instance(_record_with_canonical_id("/python/click", "python:click:8.2"))

    assert first is not second


def test_drop_library_agent_accepts_record_with_canonical_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record_with_canonical_id("/python/click", "python:click:8.1")

    first = gateway.agent_instance(record)
    gateway.drop_library_agent(record)
    second = gateway.agent_instance(record)

    assert second is not first
