"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_get_project_docs_drops_placeholder_license_search_results(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nKnown project docs topic.", encoding="utf-8")
    (project / "LICENSE").write_text("TODO: Put a short description of the license here.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "TODO license", tokens=1200, limit=3)

    assert result.status == "no_results"
    assert result.answer_available is False
    assert result.results == []
    assert not any("TODO: Put a short description" in chunk.content for chunk in result.results)


def test_get_project_docs_reports_stale_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal ProjectStaleAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    readme.write_text("# Architecture\n\nUpdated ProjectStaleAnswer.", encoding="utf-8")
    result = service.get_project_docs(str(project), "ProjectStaleAnswer", tokens=1200, limit=3)

    assert result.status == "stale"
    assert result.reason == "project_docs_stale"
    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_action["tool_after_confirmation"] == "sync_project_docs"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.stale_sources[0]["path"] == "README.md"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_actions[0]["requires_confirmation"] is True


def test_get_project_context_requires_preflight_for_stale_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal ProjectStaleContextAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    readme.write_text("# Architecture\n\nUpdated ProjectStaleContextAnswer.", encoding="utf-8")
    result = service.get_project_context(str(project), "ProjectStaleContextAnswer", tokens=1200, limit=3)

    assert result.status == "stale"
    assert result.answer_available is False
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"


def test_get_project_docs_returns_no_project_docs_next_action(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "Architecture", tokens=1200, limit=3)

    assert result.status == "no_project_docs"
    assert result.answer_available is False
    assert result.reason == "no_project_docs"
    assert result.reason_code == "no_project_docs"
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.results == []
    assert result.candidate_sources == []
    assert result.next_actions[0]["action"] == "create_reviewable_project_doc"
    assert result.next_actions[0]["preferred_path"] == "ARCHITECTURE.md"
    assert result.next_actions[0]["requires_confirmation"] is True
    assert [item["tool"] for item in result.next_actions[0]["after"]] == ["prepare_docs", "get_docs_context"]
    assert "ARCHITECTURE.md" in (result.message or "")


def test_architecture_bootstrap_file_is_discovered_indexed_and_queryable(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    empty = service.inspect_project_docs(str(project))
    assert empty.candidate_sources == []
    assert empty.recommended_next_actions[-1]["preferred_path"] == "ARCHITECTURE.md"

    (project / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nBootstrapArchitectureAnswer uses repository-local reviewable docs.",
        encoding="utf-8",
    )
    discovered = service.inspect_project_docs(str(project))
    assert discovered.candidate_sources[0]["path"] == "ARCHITECTURE.md"
    assert discovered.candidate_sources[0]["reason"] == "architecture"

    ingest = service.ingest_project_docs(str(project), with_vectors=False)
    assert ingest.status == "success"
    assert ingest.indexed_sources[0]["path"] == "ARCHITECTURE.md"

    answer = service.get_project_docs(str(project), "BootstrapArchitectureAnswer", tokens=1200, limit=3)
    assert answer.status == "success"
    assert answer.results[0].path == "ARCHITECTURE.md"
    assert "BootstrapArchitectureAnswer" in answer.results[0].content


def test_resolve_unknown_without_url_needs_docs_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("missing-lib")

    assert result.status == "needs_docs_url"
    assert result.library_id is None
    assert result.local is False


def test_unknown_with_url_creates_metadata(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    assert result.library_id == "pytest"
    assert result.docs_url == "https://docs.pytest.org/"
    assert result.status == "available"


def test_versioned_library_uses_canonical_id(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
    )

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert result.source_id == "dart:go_router:api"
    assert result.canonical_id == "dart:go_router@14.8.1:api"
    assert result.version == "14.8.1"
    assert result.requested_version == "14.8.1"
    assert result.resolved_version == "14.8.1"
    assert result.version_source == "explicit"
    assert result.version_confidence == "high"
    assert result.version_inferred is False
    assert result.docs_url_resolved == "https://pub.dev/documentation/go_router/14.8.1/"
    assert result.docs_snapshot_exact is True


def test_registry_backfills_identity_for_existing_rows(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        source_type="api",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
    )

    record = service.registry.get("pub:go_router@latest:api")

    assert record is not None
    assert record.source_id == "pub:go_router:api"
    assert record.canonical_id == "pub:go_router@latest:api"
    assert record.requested_version == "latest"
    assert record.resolved_version == "latest"
    assert record.docs_url_resolved == "https://pub.dev/documentation/go_router/latest/"
    assert record.docs_snapshot_exact is False


def test_hyphen_alias_resolves_to_underscore_package_record(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="14.8.1",
        docs_url="https://pub.dev/documentation/go_router/14.8.1/",
    )

    result = service.resolve_library("go-router", ecosystem="pub", version="14.8.1")

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert result.library == "go_router"


def test_docs_url_template_registers_version_url(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library(
        "go_router",
        ecosystem="pub",
        version="16.2.0",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.library_id == "dart:go_router@16.2.0:api"
    assert result.docs_url == "https://pub.dev/documentation/go_router/16.2.0/"


def test_refresh_multiple_versions_from_template(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.refresh_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "15.0.0", "latest"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.status == "updated"
    assert agent.add_calls == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/15.0.0/",
        "https://pub.dev/documentation/go_router/latest/",
    ]
    assert service.registry.get("go_router", "pub", "15.0.0").library_id == "dart:go_router@15.0.0:api"


def test_prefetch_docs_delegates_to_batch_refresh(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        versions=["14.8.1", "latest"],
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.status == "updated"
    assert agent.add_calls == [
        "https://pub.dev/documentation/go_router/14.8.1/",
        "https://pub.dev/documentation/go_router/latest/",
    ]


def test_prefetch_docs_defaults_missing_versions_to_latest_with_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.prefetch_docs(
        "go_router",
        ecosystem="pub",
        docs_url_template="https://pub.dev/documentation/{library}/{version}/",
    )

    assert result.status == "updated"
    assert "defaulted to latest" in result.message
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/latest/"]


def test_library_prefetch_reports_retryable_network_failure_category(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    monkeypatch.setattr(agent, "add", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("network unavailable")))

    result = service.prefetch_docs(
        "example-docs",
        ecosystem="web",
        docs_url="https://example.com/docs/",
    )

    assert result.status == "failed"
    assert "reason_code=network_unreachable" in result.message
    assert result.preindex["reason_code"] == "network_unreachable"
    record = service.registry.get("example-docs", "web", "latest")
    assert record is not None
    assert record.status == "available"
    assert record.last_error is None


def test_missing_version_falls_back_to_latest_with_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="go_router",
        ecosystem="pub",
        version="latest",
        docs_url="https://pub.dev/documentation/go_router/latest/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _mark_library_indexed(service, record)

    result = service.get_docs("go_router", ecosystem="pub", topic="ShellRoute")

    assert result.library_id == "pub:go_router@latest:api"
    assert result.version == "latest"
    assert result.warning == "No version was provided; using latest/default docs."


def test_get_docs_ingests_missing_library_with_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("pytest", topic="parametrize", docs_url="https://docs.pytest.org/")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.refreshed is True
    assert result.results[0].title == "Parametrize"


def test_get_docs_unknown_without_url_asks_for_library_docs_source(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("missing-lib", topic="usage")

    assert result.library_id == ""
    assert result.results == []
    assert result.warning == "library_docs_source_required"
    assert result.warnings == ["library_docs_source_required"]
    assert result.status == "needs_input"
    assert result.decision == "retry_same_tool"
    assert result.reason_code == "library_docs_source_required"
    assert result.diagnostics["legacy_reason_code"] == "needs_docs_url"
    assert "needs_docs_url" in result.diagnostics["reason_aliases"]
    assert result.requires_confirmation is True
    assert result.message
    assert result.next_actions[0]["type"] == "ask_user_for_library_docs_source"
    assert any(option["id"] == "manual_docs_url" for option in result.diagnostics["source_options"])
    assert any(option["id"] == "registry_metadata_discovery" and option["quality_guarantee"] is False for option in result.diagnostics["source_options"])
    assert result.next_actions[-1]["tool"] == "prepare_docs"
    assert result.next_actions[-1]["arguments_patch"]["action"] == "discover_library_docs"
    assert result.policy["direct_webfetch"] == "discovery_only"
    assert result.next_actions
    assert agent.add_calls == []


def test_get_docs_source_required_returns_retry_contract_with_discovery_candidate(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("mcp", ecosystem="python", topic="tools")

    assert result.status == "needs_input"
    assert result.reason_code == "library_docs_source_required"
    assert result.diagnostics["legacy_reason_code"] == "needs_docs_url"
    assert result.arguments_patch == {
        "docs_url": "https://github.com/modelcontextprotocol/python-sdk",
        "ecosystem": "python",
    }
    assert result.discovery_candidates == result.candidates
    assert result.diagnostics["discovery_candidates"] == result.candidates
    assert result.requires_confirmation is True
    assert result.next_actions[0]["type"] == "ask_user_for_library_docs_source"
    assert result.next_actions[1]["requires_confirmation"] is True
    assert agent.add_calls == []


def test_get_docs_uses_registered_docs_url_without_argument(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="parametrize")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.library_id == "pytest"
    assert result.warning is None
    assert "needs_docs_url" not in result.warnings


def test_registered_web_docs_without_docs_url_returns_success(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("flutter-adaptive-responsive", docs_url="https://pub.dev/documentation/flutter_adaptive_responsive/latest/")

    result = service.get_docs("flutter-adaptive-responsive", topic="breakpoints")

    assert result.status == "success"
    assert result.tool == "get_library_docs"
    assert result.schema_version == "2.1-mvp"
    assert result.decision == "answer_returned"
    assert result.result is None
    assert result.library_id == "flutter-adaptive-responsive"
    assert result.identity["docs_url"] == "https://pub.dev/documentation/flutter_adaptive_responsive/latest/"
    assert result.identity["docs_url_source"] == "registry"
    assert result.policy["direct_webfetch"] == "forbidden"
    assert result.policy["reason_code"] == "registered_source_exists"


def test_registered_web_docs_does_not_emit_needs_docs_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    warning_codes = [item["code"] for item in result.diagnostics["warnings"]]

    assert "needs_docs_url" not in result.warnings
    assert "needs_docs_url" not in warning_codes


def test_registered_web_docs_uses_registry_docs_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert result.request["effective"]["docs_url"] == "https://docs.pytest.org/"
    assert result.identity["docs_url_source"] == "registry"


def test_registered_web_docs_reports_resolver_diagnostics(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    assert result.diagnostics["resolver"] == {
        "status": "available",
        "selected_by": "registry",
        "stored_locator": "https://docs.pytest.org/",
        "candidate_count": 0,
    }


def test_library_docs_exposes_lexical_dispatch_diagnostics(tmp_path, monkeypatch):
    service = _service_with_real_agent(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="fastapi",
        ecosystem="python",
        docs_url="https://fastapi.tiangolo.com/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record, "# Depends\nUse Depends for callable injection.")

    result = service.get_docs("fastapi", ecosystem="python", topic="Depends")

    retrieval = result.diagnostics["retrieval"]
    assert retrieval["requested"] == {
        "mode": "lexical",
        "raw_topic_sha256": retrieval["requested"]["raw_topic_sha256"],
        "filters": {
            "library_id": record.library_id,
            **({"resolved_version": record.resolved_version or record.version}
               if record.resolved_version or record.version else {}),
        },
        "record": {
            "library_id": record.library_id,
            "canonical_id": record.canonical_id,
            "resolved_version": record.resolved_version or record.version,
            "docs_snapshot_exact": record.docs_snapshot_exact,
        },
    }
    assert retrieval["used"] == {
        "mode": "lexical",
        "candidate_counts": {"lexical": 1},
        "failures": {},
        "query_plan_hash": retrieval["used"]["query_plan_hash"],
        "component_ranks": retrieval["used"]["component_ranks"],
    }
    assert retrieval["requested"]["raw_topic_sha256"]
    assert retrieval["used"]["query_plan_hash"]
    assert len(retrieval["used"]["component_ranks"]) == 1
    assert retrieval["post_guard"] == {"before": 1, "accepted": 1, "rejected": {}, "low_value_dropped": 0}


def test_code_example_blocks_detected_and_ranked_first(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="fastapi",
        ecosystem="python",
        docs_url="https://fastapi.tiangolo.com/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)
    chunks = [
        _library_chunk(record, "Dependency injection overview.", "concepts", 0.9),
        _library_chunk(record, "Use Depends.\n```python\ndef get_db():\n    return Depends(callable)\n```", "depends", 0.8),
    ]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = StaticChunksAgent(chunks)

    result = service.get_docs("fastapi", ecosystem="python", topic="Depends callable injection")

    assert result.results[0].source.endswith("/depends")
    assert result.results[0].metadata["code_snippets"] == [
        {"language": "python", "code": "def get_db():\n    return Depends(callable)"}
    ]
    assert result.results[0].metadata["code_snippet_count"] == 1
    assert result.diagnostics["code_snippets"] == 1


def test_noise_cleaned_from_output_and_anchor_links_stripped(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="click",
        ecosystem="python",
        docs_url="https://click.palletsprojects.com/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)
    chunks = [_library_chunk(record, "Options [¶]\nCopy code\nUse @click.option() ", "options")]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = StaticChunksAgent(chunks)

    result = service.get_docs("click", ecosystem="python", topic="option")

    assert "[¶]" not in result.results[0].content
    assert "Copy code" not in result.results[0].content
    assert "@click.option()" in result.results[0].content


def test_max_chunks_per_source_enforced_and_unique_sources_reported(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="riverpod",
        ecosystem="pub",
        version="3.0.0",
        docs_url="https://pub.dev/documentation/riverpod/3.0.0/",
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    _write_library_index(service, record)
    root = record.docs_url.rstrip("/")
    chunks = [
        RetrievedChunk(source=f"{root}/provider", chunk_index=i, text=f"ref.watch example {i}", score=1.0 - i * 0.01, metadata={"title": f"provider {i}", "library_id": record.library_id, "canonical_id": record.canonical_id})
        for i in range(4)
    ] + [
        _library_chunk(record, "ref.listen example", "listener", 0.7),
        _library_chunk(record, "AsyncValue example", "async-value", 0.6),
    ]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = StaticChunksAgent(chunks)

    result = service.get_docs("riverpod", ecosystem="pub", version="3.0.0", topic="ref watch listen")

    assert sum(1 for item in result.results if item.source == f"{root}/provider") == 2
    assert result.diagnostics["chunks_dropped_for_diversity"] == 2
    assert result.diagnostics["unique_sources@5"] == 3


def test_stale_docs_include_freshness_warning_and_chunk_metadata(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    old = _old_iso(45)
    service = _service(tmp_path, monkeypatch)
    record = service.registry.upsert(
        library="pytest",
        ecosystem="python",
        docs_url="https://docs.pytest.org/",
        now=now,
        status="available",
        last_refreshed_at=old,
    )
    _write_library_index(service, record)
    chunks = [_library_chunk(record, "Use fixtures.", "fixtures")]
    service.agent_gateway.drop_library_agent(record)
    service.agent_gateway._agents[record.canonical_id] = FailingRefreshStaticChunksAgent(chunks)

    result = service.get_docs("pytest", ecosystem="python", topic="fixtures")

    assert result.status == "success"
    assert any("stale after" in warning for warning in result.warnings)
    assert result.diagnostics["freshness"]["stale"] is True
    assert result.diagnostics["freshness"]["age_days"] >= 45
    assert result.results[0].metadata["stale"] is True


def test_registered_web_docs_conflicting_input_url_blocks_without_mutation(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures", docs_url="https://example.com/pytest/")

    assert result.status == "needs_input"
    assert result.decision == "retry_same_tool"
    assert result.warning == "docs_url_conflict"
    assert {"code": "docs_url_conflict", "blocking": True} in result.diagnostics["warnings"]
    assert result.policy["direct_webfetch"] == "forbidden"
    assert result.identity["docs_url"] == "https://docs.pytest.org/"
    assert agent.add_calls == []
    assert service.registry.get("pytest").docs_url == "https://docs.pytest.org/"


def test_registered_docs_without_locator_can_accept_input_url(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.registry.upsert(
        library="pytest",
        ecosystem=None,
        docs_url=None,
        now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        status="available",
    )

    result = service.get_docs("pytest", topic="fixtures", docs_url="https://docs.pytest.org/")

    assert result.status == "success"
    assert agent.add_calls == ["https://docs.pytest.org/"]
    assert service.registry.get("pytest").docs_url == "https://docs.pytest.org/"


def test_success_response_includes_effective_identity(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", version="8.3.4", topic="fixtures")

    assert result.request["input"]["library"] == "pytest"
    assert result.request["effective"]["version"] == "8.3.4"
    assert result.identity["canonical_id"] == "pytest@8.3.4"
    assert result.identity["library"] == "pytest"
    assert result.identity["version"] == "8.3.4"


def test_success_with_registry_docs_url_has_non_blocking_warning(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", topic="fixtures")

    assert {"code": "used_registry_docs_url", "blocking": False} in result.diagnostics["warnings"]


def test_ambiguous_versions_return_candidates(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("go_router", ecosystem="pub", version="14.8.1", docs_url="https://pub.dev/documentation/go_router/14.8.1/")
    service.resolve_library("go_router", ecosystem="pub", version="16.2.0", docs_url="https://pub.dev/documentation/go_router/16.2.0/")

    result = service.get_docs("go-router", ecosystem="pub", topic="ShellRoute")

    assert result.status == "ambiguous"
    assert result.decision == "choose_candidate"
    assert len(result.candidates) == 2
    assert {candidate["canonical_id"] for candidate in result.candidates} == {
        "dart:go_router@14.8.1:api",
        "dart:go_router@16.2.0:api",
    }
    assert result.policy["direct_webfetch"] == "forbidden"
    assert result.diagnostics["resolver"]["candidate_count"] == 2
    assert agent.add_calls == []


def test_ambiguous_versions_include_retry_patches(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("go_router", ecosystem="pub", version="14.8.1", docs_url="https://pub.dev/documentation/go_router/14.8.1/")
    service.resolve_library("go_router", ecosystem="pub", version="16.2.0", docs_url="https://pub.dev/documentation/go_router/16.2.0/")

    result = service.get_docs("go-router", ecosystem="pub", topic="ShellRoute")

    assert all(candidate["arguments_patch"] for candidate in result.candidates)
    assert result.candidates[0]["arguments_patch"]["library"].startswith("dart:go_router@")


def test_exact_version_with_unversioned_url_is_not_exact(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    assert result.library_id == "pytest@8.3.4"
    assert result.docs_snapshot_exact is False


def test_get_docs_uses_registry_snapshot_metadata(tmp_path, monkeypatch):
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)
    service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    result = service.get_docs("pytest", version="8.3.4", topic="parametrize")

    assert result.library_id == "pytest@8.3.4"
    assert result.requested_version == "8.3.4"
    assert result.resolved_version == "8.3.4"
    assert result.version_source == "explicit"
    assert result.docs_snapshot_exact is False


def test_get_docs_uses_project_package_version_when_omitted(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    agent = FakeAgent()
    service = _service(tmp_path, monkeypatch, agent)

    result = service.get_docs("go_router", ecosystem="pub", topic="ShellRoute", project_path=str(project))

    assert result.library_id == "dart:go_router@14.8.1:api"
    assert result.version == "14.8.1"
    assert result.docs_snapshot_exact is True
    assert result.requested_version == "14.8.1"
    assert result.version_source == "lockfile_exact"
    assert result.docs_exactness == "exact_snapshot"
    assert result.docs_binding_source == "pub_dartdoc"
    assert result.confidence == "high"
    assert agent.add_calls == ["https://pub.dev/documentation/go_router/14.8.1/"]
    record = service.registry.get("dart:go_router@14.8.1:api")
    assert record is not None
    assert record.requested_version == "14.8.1"
    assert record.resolved_version == "14.8.1"
    assert record.version_source == "lockfile_exact"
    assert record.version_inferred is True
