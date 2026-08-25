from pathlib import Path

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.core.models import RetrievedChunk
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


class RecordingDispatcher:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run(self, query, **kwargs):
        self.calls.append((self.kwargs, query, kwargs))
        return "dispatch-result"


class WitnessStore:
    def __init__(self):
        self.calls = []

    def query(self, query, *, limit, budget, filters):
        self.calls.append((query, limit, budget, filters))
        return [
            RetrievedChunk(
                source="https://docs.example.test/api.md",
                chunk_index=1,
                text="async returns Deferred and await obtains the result",
                score=1.0,
                metadata={"stable_chunk_id": "async-result"},
            )
        ]


class FailingWitnessStore:
    def query(self, query, *, limit, budget, filters):
        raise RuntimeError("index temporarily unavailable")


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
    monkeypatch.delenv("DOCATLAS_HOME", raising=False)
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
    monkeypatch.delenv("DOCATLAS_HOME", raising=False)
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    default = FakeAgent(config=DocmancerConfig())
    gateway = AgentIndexGateway(DocmancerConfig(), default_agent=default, agent_factory=FakeAgent)

    library_agent = gateway.agent_instance(_record())

    assert library_agent is not default
    assert Path(library_agent.config.index.db_path) == tmp_path / "home" / "docs-indexes" / "pub-riverpod-2-0-api.db"


def test_query_library_dispatches_raw_topic_in_lexical_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        "docmancer.docs.infrastructure.agent_index_gateway.dispatcher_for_agent",
        lambda agent, mode: RecordingDispatcher(store=agent.store, config=agent.config),
        raising=False,
    )
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record()
    agent = gateway.agent_instance(record)
    agent.store = object()
    RecordingDispatcher.calls.clear()

    filters = {"library_id": record.library_id, "resolved_version": "2.0"}
    assert gateway.query_library(record, "Provider", budget=120, filters=filters) == "dispatch-result"
    dispatcher_args, query, run_args = RecordingDispatcher.calls[0]
    assert query == "Provider"
    assert dispatcher_args == {"store": agent.store, "config": agent.config}
    assert run_args == {"mode": "lexical", "budget": 120, "filters": filters}


def test_query_library_uses_configured_vector_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.retrieval.default_mode = "hybrid"
    resolved_modes = []

    def build_dispatcher(agent, *, mode):
        resolved_modes.append(mode)
        return RecordingDispatcher(store=agent.store, config=agent.config)

    monkeypatch.setattr(
        "docmancer.docs.infrastructure.agent_index_gateway.dispatcher_for_agent",
        build_dispatcher,
    )
    gateway = AgentIndexGateway(config, agent_factory=FakeAgent)
    record = _record()
    gateway.agent_instance(record).store = object()
    RecordingDispatcher.calls.clear()

    gateway.query_library(record, "Provider")

    assert resolved_modes == ["hybrid"]
    assert RecordingDispatcher.calls[0][2]["mode"] == "hybrid"


def test_dispatcher_is_reused_until_library_agent_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    builds = []

    def build_dispatcher(agent, *, mode):
        builds.append((agent, mode))
        return RecordingDispatcher(store=agent.store, config=agent.config)

    monkeypatch.setattr(
        "docmancer.docs.infrastructure.agent_index_gateway.dispatcher_for_agent",
        build_dispatcher,
    )
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record()
    agent = gateway.agent_instance(record)
    agent.store = object()

    first = gateway.dispatcher_for(agent)
    second = gateway.dispatcher_for(agent)
    agent.config.vector_store.options = {"db_path": str(tmp_path / "changed-vectors.db")}
    reconfigured = gateway.dispatcher_for(agent)
    gateway.drop_library_agent(record)
    replacement = gateway.agent_instance(record)
    replacement.store = object()
    third = gateway.dispatcher_for(replacement)

    assert first is second
    assert reconfigured is not first
    assert third is not first
    assert len(builds) == 3


def test_dispatcher_cache_tracks_store_and_generation_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    builds = []

    def build_dispatcher(agent, *, mode):
        builds.append((agent.store, mode))
        return object()

    class Store:
        generation = "one"

        def generation_info(self):
            return {"generation_id": self.generation, "vector_collection": self.generation}

    monkeypatch.setattr(
        "docmancer.docs.infrastructure.agent_index_gateway.dispatcher_for_agent", build_dispatcher,
    )
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    agent = gateway.agent_instance(_record())
    first_store = Store()
    agent.store = first_store

    first = gateway.dispatcher_for(agent)
    first_store.generation = "two"
    second = gateway.dispatcher_for(agent)
    agent.store = Store()
    third = gateway.dispatcher_for(agent)

    assert first is not second
    assert second is not third
    assert len(builds) == 3


def test_query_library_preserves_the_canonical_requirement_set_for_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        "docmancer.docs.infrastructure.agent_index_gateway.dispatcher_for_agent",
        lambda agent, mode: RecordingDispatcher(store=agent.store, config=agent.config),
        raising=False,
    )
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record()
    agent = gateway.agent_instance(record)
    agent.store = object()
    requirements = build_requirements(
        "Compare create_task with gather and explain how the scheduled task result is obtained",
        profile="library_docs_answer",
        exact_snapshot_required=True,
        project_identity="project:example",
        module_id="runtime",
    )
    RecordingDispatcher.calls.clear()

    gateway.query_library(record, "Compare create_task with gather", requirements=requirements)

    _, _, run_args = RecordingDispatcher.calls[0]
    assert run_args["requirements"] is requirements
    assert run_args["requirements"].requirements_hash == requirements.requirements_hash
    assert run_args["requirements"].query_requirement_spans == requirements.query_requirement_spans


def test_library_witness_probe_is_bounded_and_uses_the_record_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record()
    agent = gateway.agent_instance(record)
    agent.store = WitnessStore()
    requirements = build_requirements(
        "When should I use async instead of launch, and how do I obtain its result?",
        profile="library_docs_answer",
    )
    missing = [item.requirement_id for item in requirements if item.kind in {"entity", "facet"}]
    filters = {"library_id": record.library_id, "resolved_version": "2.0"}

    probe = gateway.probe_library_requirements(
        record,
        requirements,
        missing_requirement_ids=missing,
        filters=filters,
        max_requirements=2,
        max_results_per_requirement=2,
        budget=80,
    )

    assert probe.status == "ok"
    assert len(probe.chunks) <= 4
    assert len(agent.store.calls) <= 2
    assert all(call[1:] == (2, 40, filters) for call in agent.store.calls)
    assert probe.queried_requirement_ids == tuple(missing[:2])


def test_library_witness_probe_is_fail_closed_when_every_store_query_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    gateway = AgentIndexGateway(DocmancerConfig(), agent_factory=FakeAgent)
    record = _record()
    agent = gateway.agent_instance(record)
    agent.store = FailingWitnessStore()
    requirements = build_requirements(
        "When should I use async instead of launch, and how do I obtain its result?",
        profile="library_docs_answer",
    )
    missing = [item.requirement_id for item in requirements if item.kind in {"entity", "facet"}]

    probe = gateway.probe_library_requirements(
        record,
        requirements,
        missing_requirement_ids=missing,
    )

    assert probe.status == "unavailable"
    assert probe.failure_count == len(probe.queried_requirement_ids)


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
