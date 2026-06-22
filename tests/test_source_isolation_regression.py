from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


class RecordingAgent:
    def __init__(self, chunks=None):
        self.chunks = chunks or []
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[str] = []
        self.config = None

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if self.config is not None:
            marker = Path(self.config.index.extracted_dir) / "chunk.md"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("indexed chunk", encoding="utf-8")
        return 1

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append(text)
        return self.chunks


def _service(tmp_path, monkeypatch, agent: RecordingAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    agent = agent or RecordingAgent()
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def agent_factory(**kwargs):
        agent.config = kwargs.get("config")
        return agent

    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent,
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )


def _register(service: LibraryDocsService, *, library: str, ecosystem: str | None = None, version: str | None = None, docs_url: str, source_type: str | None = "api", indexed: bool = True):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library=library,
        ecosystem=ecosystem,
        version=version,
        source_type=source_type,
        docs_url=docs_url,
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    if indexed:
        config = service._index_config_for(record)
        marker = Path(config.index.extracted_dir) / "chunk.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("indexed chunk", encoding="utf-8")
    return record


def _chunk(text: str, source: str, metadata: dict):
    return RetrievedChunk(source=source, chunk_index=0, text=text, score=1.0, metadata=metadata)


def test_click_query_does_not_return_fastapi_or_flutter(tmp_path, monkeypatch):
    agent = RecordingAgent(
        [
            _chunk(
                "Click command docs.",
                "https://click.palletsprojects.com/en/8.1.x/commands/",
                {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "python", "version": "8.1.7"},
            ),
            _chunk("FastAPI docs.", "https://fastapi.tiangolo.com/tutorial/", {"library_id": "python:fastapi@0.110.0:api"}),
            _chunk("Flutter docs.", "https://api.flutter.dev/widgets/widgets-library.html", {"library_id": "flutter:flutter-api@stable:api"}),
            _chunk("Project README.", "/repo/README.md", {"project_path": "/repo"}),
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "success"
    assert [chunk.content for chunk in result.results] == ["Click command docs."]


def test_flutter_bloc_query_does_not_return_unrelated_project_docs(tmp_path, monkeypatch):
    agent = RecordingAgent(
        [
            _chunk(
                "BlocBuilder docs.",
                "https://pub.dev/documentation/flutter_bloc/9.1.1/flutter_bloc/BlocBuilder-class.html",
                {"library_id": "pub:flutter_bloc@9.1.1:api", "canonical_id": "pub:flutter_bloc@9.1.1:api", "ecosystem": "pub", "version": "9.1.1"},
            ),
            _chunk("Smart glasses architecture.", "/home/viadmin/StudioProjects/smart_glasses/ARCHITECTURE.md", {"project_path": "/home/viadmin/StudioProjects/smart_glasses"}),
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="flutter_bloc", ecosystem="pub", version="9.1.1", docs_url="https://pub.dev/documentation/flutter_bloc/9.1.1/")

    result = service.get_docs("flutter_bloc", ecosystem="pub", version="9.1.1", source_type="api", topic="BlocBuilder")

    assert [chunk.content for chunk in result.results] == ["BlocBuilder docs."]
    assert all("smart_glasses" not in (chunk.source or "") for chunk in result.results)


def test_empty_library_index_returns_controlled_error(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("Project README.", "/repo/README.md", {"project_path": "/repo"})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/", indexed=False)

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.decision == "stop"
    assert result.diagnostics["reason_code"] == "missing_chunks"
    assert result.next_actions == ["Call refresh_library_docs to ingest this library's docs."]
    assert result.results == []
    assert agent.query_calls == []


def test_project_query_then_library_query_uses_per_library_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    default_agent = RecordingAgent([_chunk("Project README.", "/repo/README.md", {"project_path": "/repo"})])
    library_agent = RecordingAgent(
        [_chunk("Click command docs.", "https://click.palletsprojects.com/en/8.1.x/commands/", {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "python", "version": "8.1.7"})]
    )
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def agent_factory(**kwargs):
        library_agent.config = kwargs.get("config")
        return library_agent

    service = LibraryDocsService(config=config, registry=LibraryRegistry(config.index.db_path), agent=default_agent, agent_factory=agent_factory, job_tracker=DocsJobTracker())
    service._agent_instance().query("project query")
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "success"
    assert [chunk.content for chunk in result.results] == ["Click command docs."]
    assert default_agent.query_calls == ["project query"]
    assert library_agent.query_calls == ["click commands"]


def test_chunks_without_library_id_are_filtered_out(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("Unlabeled chunk.", "https://click.palletsprojects.com/en/8.1.x/commands/", {})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_project_path_in_get_library_docs_does_not_leak_project_docs(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    agent = RecordingAgent(
        [
            _chunk("Click command docs.", "https://click.palletsprojects.com/en/8.1.x/commands/", {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "python", "version": "8.1.7"}),
            _chunk("Project README.", str(project / "README.md"), {"library_id": "python:click@8.1.7:api", "project_path": str(project)}),
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands", project_path=str(project))

    assert [chunk.content for chunk in result.results] == ["Click command docs."]


def test_post_retrieval_guard_drops_wrong_ecosystem(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("Pub Click docs.", "https://click.palletsprojects.com/en/8.1.x/commands/", {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "pub", "version": "8.1.7"})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_all_chunks_filtered_returns_controlled_error(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("FastAPI docs.", "https://fastapi.tiangolo.com/tutorial/", {"library_id": "python:fastapi@0.110.0:api"})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.decision == "stop"
    assert result.diagnostics["reason_code"] == "missing_chunks"


def test_local_path_with_matching_library_id_is_filtered_out(tmp_path, monkeypatch):
    agent = RecordingAgent(
        [
            _chunk(
                "unrelated local README",
                "/home/viadmin/StudioProjects/smart_glasses/README.md",
                {"library_id": "python:click@8.1.7:api"},
            )
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []
    assert {"code": "wrong_docset_root", "blocking": False, "dropped": 1} in result.diagnostics["warnings"]
