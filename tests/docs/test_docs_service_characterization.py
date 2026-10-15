from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


class FakeAgent:
    def __init__(self):
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[tuple[str, int | None]] = []
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
        self.query_calls.append((text, budget))
        metadata = dict((self.add_kwargs[-1].get("metadata") if self.add_kwargs else None) or {})
        metadata.setdefault("title", "Guide")
        return [
            RetrievedChunk(
                source=(self.add_calls[-1].rstrip("/") + "/guide") if self.add_calls else "https://docs.example.com/guide",
                chunk_index=0,
                text="Use the registered docs source.",
                score=1.0,
                metadata=metadata,
            )
        ]


def _service(tmp_path, monkeypatch, agent: FakeAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    agent = agent or FakeAgent()
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


def _service_with_real_agent(tmp_path, monkeypatch) -> LibraryDocsService:
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def _flutter_project(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / ".fvmrc").write_text("stable", encoding="utf-8")
    (project / "pubspec.yaml").write_text(
        """
name: app
dependencies:
  flutter:
    sdk: flutter
  go_router: ^14.0.0
""",
        encoding="utf-8",
    )
    (project / "pubspec.lock").write_text(
        """
packages:
  go_router:
    dependency: direct main
    source: hosted
    version: "14.8.1"
sdks:
  dart: ">=3.0.0 <4.0.0"
""",
        encoding="utf-8",
    )
    return project


def test_characterization_ambiguous_library_returns_candidates_and_retry_guidance(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.resolve_library("go_router", ecosystem="pub", version="14.8.1", docs_url="https://pub.dev/documentation/go_router/14.8.1/")
    service.resolve_library("go_router", ecosystem="pub", version="16.2.0", docs_url="https://pub.dev/documentation/go_router/16.2.0/")

    result = service.get_docs("go-router", ecosystem="pub", topic="ShellRoute")

    assert result.status == "ambiguous"
    assert result.decision == "choose_candidate"
    assert result.warning == "ambiguous_library"
    assert len(result.candidates) == 2
    assert all(candidate["arguments_patch"] for candidate in result.candidates)
    assert result.next_actions == ["Choose one candidate and retry get_library_docs with its arguments_patch."]
    assert result.policy["direct_webfetch"] == "forbidden"


def test_characterization_unknown_library_without_url_returns_needs_input_shape(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("missing-lib", topic="usage")

    assert result.status == "needs_input"
    assert result.decision == "retry_same_tool"
    assert result.warning == "library_docs_source_required"
    assert result.warnings == ["library_docs_source_required"]
    assert result.library_id == ""
    assert result.results == []
    assert result.policy["direct_webfetch"] == "discovery_only"
    assert result.reason_code == "library_docs_source_required"
    assert result.diagnostics["legacy_reason_code"] == "needs_docs_url"
    assert result.requires_confirmation is True
    assert result.next_actions[0]["type"] == "ask_user_for_library_docs_source"
    assert result.next_actions
    assert agent.add_calls == []


def test_characterization_no_project_docs_returns_architecture_remediation(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "no_project_docs"
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.recommended_next_actions[-1]["preferred_path"] == "ARCHITECTURE.md"


def test_characterization_target_url_security_rejects_localhost_private_networks(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.prefetch_docs_targets([
        {"library": "unsafe", "docs_url": "http://127.0.0.1:8000/docs/", "allowed_domains": ["127.0.0.1"]},
    ])

    assert result.status == "failed"
    assert result.targets_failed == 1
    assert result.results[0].message == "private network URLs are not allowed"


def test_characterization_manifest_validation_errors_remain_stable(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    manifest = tmp_path / "docatlas.docs.yaml"
    manifest.write_text("version: 2\ntargets:\n  - id: bad\n    identity: {kind: product, ecosystem: web, name: bad}\n    version: {requested: rolling, policy: rolling}\n    source: {type: reference, url: https://example.com/outside, authority: official_product, version_binding: rolling, format: html}\n    scope:\n      allowed_domains: [example.com]\n      path_prefixes: [/docs/]\n      coverage: bounded\n", encoding="utf-8")

    result = service.validate_docs_manifest(str(manifest))

    assert result.valid is False
    assert result.manifest_path == str(manifest.resolve())
    assert result.targets == []
    assert any("URL path is outside path_prefixes" in error for error in result.errors)

