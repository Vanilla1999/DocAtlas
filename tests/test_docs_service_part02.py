"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_incremental_sync_handles_rename_and_deletion_without_pruning_unrelated_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    old = docs / "old.md"
    deleted = docs / "deleted.md"
    keep = docs / "keep.md"
    old.write_text("# Old\n\nRenameOldNeedle.", encoding="utf-8")
    deleted.write_text("# Deleted\n\nDeleteNeedle.", encoding="utf-8")
    keep.write_text("# Keep\n\nKeepNeedle.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)
    new = docs / "new.md"
    old.rename(new)
    deleted.unlink()

    result = service.sync_project_docs(
        str(project),
        with_vectors=False,
        deleted_paths=["docs/deleted.md"],
        renamed_paths=[{"old_path": "docs/old.md", "new_path": "docs/new.md"}],
    )

    assert result.status == "success"
    assert {item["path"] for item in result.tombstones} == {
        "docs/deleted.md", "docs/old.md",
    }
    assert next(item for item in result.tombstones if item["path"] == "docs/old.md")["renamed_to"] == "docs/new.md"
    assert service.get_project_docs(str(project), "DeleteNeedle").results == []
    assert service.get_project_docs(str(project), "RenameOldNeedle").results[0].source.endswith("docs/new.md")
    assert "KeepNeedle" in service.get_project_docs(str(project), "KeepNeedle").results[0].content


def test_deletion_only_incremental_sync_prunes_only_deleted_vector_chunks(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    removed = docs / "removed.md"
    removed.write_text("# Removed\n\nVectorDeleteNeedle.\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)
    removed.unlink()
    removed_ids = set(service._agent_instance().store.section_ids_for_source(
        next(
            item["source"]
            for item in service._indexed_project_doc_sources(str(project))
            if item["path"] == "docs/removed.md"
        )
    ))
    prune_vectors = MagicMock(return_value=len(removed_ids))
    sync_vectors = MagicMock()
    service._agent_instance().prune_vector_chunks = prune_vectors
    service._agent_instance().sync_vectors = sync_vectors

    result = service.sync_project_docs(
        str(project), with_vectors=False, deleted_paths=["docs/removed.md"]
    )

    assert result.status == "success"
    assert result.diagnostics["metrics"]["files_reprocessed"] == 0
    prune_vectors.assert_called_once_with(removed_ids)
    sync_vectors.assert_not_called()
    assert result.diagnostics["metrics"]["vector_chunks_pruned"] == len(removed_ids)


def test_incremental_vector_sync_is_scoped_to_changed_document(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    docs = project / "docs"
    docs.mkdir()
    changed = docs / "changed.md"
    unchanged = docs / "unchanged.md"
    changed.write_text("# Changed\n\nOld vector content.\n", encoding="utf-8")
    unchanged.write_text("# Unchanged\n\nKeep vector content.\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)
    changed.write_text("# Changed\n\nNew vector content.\n", encoding="utf-8")
    def record_vector_sync(_section_ids):
        service._agent_instance().last_vector_sync_metrics = {
            "status": "success",
            "embedded": 1,
            "upserted": 1,
            "skipped_cache": 0,
            "skipped_unchanged": 0,
            "pruned": 0,
            "duration_ms": 12,
            "backend_setup_ms": 2,
            "collection": "project_vectors",
            "requested": True,
            "retrieval_mode": "lexical",
        }
        return object()

    sync_chunks = MagicMock(side_effect=record_vector_sync)
    sync_all = MagicMock()
    service._agent_instance().sync_vector_chunks = sync_chunks
    service._agent_instance().sync_vectors = sync_all

    result = service.sync_project_docs(
        str(project), with_vectors=True, changed_paths=["docs/changed.md"]
    )

    changed_source = next(
        item["source"]
        for item in service._indexed_project_doc_sources(str(project))
        if item["path"] == "docs/changed.md"
    )
    expected_ids = set(service._agent_instance().store.section_ids_for_source(changed_source))
    sync_chunks.assert_called_once_with(expected_ids)
    sync_all.assert_not_called()
    assert result.diagnostics["vector_sync"] == {
        "status": "success",
        "embedded": 1,
        "upserted": 1,
        "skipped_cache": 0,
        "skipped_unchanged": 0,
        "pruned": 0,
        "duration_ms": 12,
        "backend_setup_ms": 2,
        "collection": "project_vectors",
        "requested": True,
        "retrieval_mode": "lexical",
    }
    assert result.diagnostics["metrics"]["unrelated_files_reprocessed"] == 0
    budgets = json.loads(
        (Path(__file__).resolve().parents[1] / "eval" / "change_aware" / "maintenance_eval.json")
        .read_text(encoding="utf-8")
    )["budgets"]
    assert result.diagnostics["metrics"]["unrelated_files_reprocessed"] <= budgets[
        "maximum_unrelated_files_reprocessed"
    ]
    assert result.diagnostics["metrics"]["unchanged_derived_writes"] <= budgets[
        "maximum_unchanged_derived_writes"
    ]


def test_incremental_sync_rejects_paths_outside_project(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="escapes project_path"):
        service.sync_project_docs(
            str(project), with_vectors=False, deleted_paths=["../outside.md"]
        )


def test_incremental_sync_rejects_deletion_while_document_still_exists(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nStill accepted.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    with pytest.raises(ValueError, match="still exist as project documentation candidates"):
        service.sync_project_docs(
            str(project), with_vectors=False, deleted_paths=["README.md"]
        )

    assert "Still accepted" in service.get_project_docs(
        str(project), "Still accepted"
    ).results[0].content


def test_sync_project_docs_prunes_orphaned_sources_when_all_docs_removed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nRemoveAllNeedle should be pruned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.unlink()

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.candidate_count == 0
    assert result.orphaned_count == 1
    assert result.orphaned_removed == 1
    assert result.current_count == 0
    assert result.indexed_sources == []
    assert {item["path"] for item in result.removed_sources} == {"README.md"}
    with service._agent_instance().store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 0


def test_inspect_project_docs_reports_needs_sync_for_orphaned_sources(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOrphaned inspect source.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.unlink()

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.ignored_sources[0]["path"] == "README.md"
    assert result.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.diagnostics["preflight"]["base_reason_code"] == "project_docs_stale"
    assert {risk["code"] for risk in result.diagnostics["preflight"]["risks"]} == {"orphaned_project_doc_sources"}


def test_mcp_get_project_docs_returns_compact_response_unless_details_requested(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCompactNeedle project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    compact = handle_project_tool(
        "get_project_docs",
        {"project_path": str(project), "query": "CompactNeedle", "tokens": 1200, "limit": 5},
        service,
    )
    detailed = handle_project_tool(
        "get_project_docs",
        {"project_path": str(project), "query": "CompactNeedle", "tokens": 1200, "limit": 5, "details": True},
        service,
    )

    assert compact is not None
    assert detailed is not None
    assert compact["answer_available"] is True
    assert compact["source_summary"] == {"candidates": 1, "indexed": 1, "stale": 0, "ignored": 0}
    assert "CompactNeedle project docs." in compact["results"][0]["content"]
    assert "candidate_sources" not in compact
    assert "source_state_guidance" not in compact
    assert "candidate_sources" in detailed
    assert "source_state_guidance" in detailed


def test_mcp_project_lifecycle_tools_return_compact_response_unless_details_requested(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nLifecycle compact docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    inspect_compact = handle_project_tool("inspect_project_docs", {"project_path": str(project)}, service)
    inspect_detailed = handle_project_tool("inspect_project_docs", {"project_path": str(project), "details": True}, service)
    sync_compact = handle_project_tool("sync_project_docs", {"project_path": str(project), "with_vectors": False}, service)
    sync_detailed = handle_project_tool("sync_project_docs", {"project_path": str(project), "with_vectors": False, "details": True}, service)
    ingest_compact = handle_project_tool("ingest_project_docs", {"project_path": str(project), "with_vectors": False}, service)
    ingest_detailed = handle_project_tool("ingest_project_docs", {"project_path": str(project), "with_vectors": False, "details": True}, service)
    bootstrap_compact = handle_project_tool("bootstrap_project_docs", {"project_path": str(project), "question": "Lifecycle"}, service)
    bootstrap_detailed = handle_project_tool("bootstrap_project_docs", {"project_path": str(project), "question": "Lifecycle", "details": True}, service)

    assert inspect_compact is not None
    assert inspect_detailed is not None
    assert inspect_compact["source_summary"] == {"candidates": 1, "indexed": 0, "stale": 0, "ignored": 0}
    assert "candidate_sources" not in inspect_compact
    assert "candidate_sources" in inspect_detailed

    assert sync_compact is not None
    assert sync_detailed is not None
    assert sync_compact["summary"]["current"] == 1
    assert "indexed_sources" not in sync_compact
    assert "indexed_sources" in sync_detailed

    assert ingest_compact is not None
    assert ingest_detailed is not None
    assert ingest_compact["source_summary"]["indexed"] == 1
    assert "indexed_sources" not in ingest_compact
    assert "indexed_sources" in ingest_detailed

    assert bootstrap_compact is not None
    assert bootstrap_detailed is not None
    assert bootstrap_compact["status"] == "ready"
    assert "inspect_result" not in bootstrap_compact
    assert "inspect_result" in bootstrap_detailed


def test_project_docs_lifecycle_diagnostics_expose_active_index_and_shadowed_project_config(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nDiagnostics compact docs.", encoding="utf-8")
    (project / "docmancer.yaml").write_text(
        """
index:
  db_path: .docmancer/project-local.db
vector_store:
  api_key_env: SUPER_SECRET_DOCMANCER_TOKEN
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("SUPER_SECRET_DOCMANCER_TOKEN", "super-secret-token-value")
    monkeypatch.setenv("HOME", str(tmp_path / "user-home"))
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "docmancer-home"))
    monkeypatch.delenv("DOCMANCER_INDEX_DB_PATH", raising=False)
    service = LibraryDocsService(job_tracker=DocsJobTracker())

    inspect = service.inspect_project_docs(str(project))
    inspect_compact = handle_project_tool("inspect_project_docs", {"project_path": str(project)}, service)
    sync = service.sync_project_docs(str(project), with_vectors=False)
    sync_compact = handle_project_tool("sync_project_docs", {"project_path": str(project), "with_vectors": False}, service)

    expected_active_db = str((tmp_path / "docmancer-home" / "docmancer.db").resolve())
    expected_project_db = str((project / ".docmancer" / "project-local.db").resolve())
    assert inspect.diagnostics["active_index"]["db_path"] == expected_active_db
    assert inspect.diagnostics["active_index"]["project_path"] == str(project.resolve())
    assert inspect.diagnostics["active_index"]["config_source"] == "defaults"
    assert inspect.diagnostics["active_index"]["project_local_config"] == {
        "present": True,
        "path": str((project / "docmancer.yaml").resolve()),
        "db_path": expected_project_db,
    }
    assert any(
        warning["code"] == "project_local_config_shadowed"
        for warning in inspect.diagnostics["active_index"]["warnings"]
    )
    assert sync.diagnostics["active_index"]["index_counts"]["sources"] == 1
    assert sync.diagnostics["active_index"]["index_counts"]["sections"] >= 1
    assert inspect_compact["diagnostics"]["active_index"]["db_path"] == expected_active_db
    assert sync_compact["diagnostics"]["active_index"]["db_path"] == expected_active_db
    assert "super-secret-token-value" not in json.dumps(inspect_compact)
    assert "SUPER_SECRET_DOCMANCER_TOKEN" not in json.dumps(inspect_compact)


def test_get_project_context_diagnostics_preserve_query_intent_and_active_index(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nContextDiagnosticsNeedle project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(
        str(project),
        "Where is ContextDiagnosticsNeedle documented?",
        tokens=1200,
        limit=5,
    )
    compact = handle_project_tool(
        "get_project_context",
        {"project_path": str(project), "question": "Where is ContextDiagnosticsNeedle documented?", "tokens": 1200, "limit": 5},
        service,
    )

    assert result.answer_available is False
    assert result.context_pack
    assert result.reason == "partial_navigational_context"
    assert result.diagnostics["query_intent"]
    assert result.diagnostics["active_index"]["project_path"] == str(project.resolve())
    assert result.diagnostics["active_index"]["db_path"] == str((tmp_path / "docmancer.db").resolve())
    assert compact is not None
    assert compact["diagnostics"]["query_intent"] == result.diagnostics["query_intent"]
    assert compact["diagnostics"]["active_index"]["db_path"] == str((tmp_path / "docmancer.db").resolve())


def test_get_project_context_answers_dart_symbol_docs_with_snippet_evidence(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "lib" / "src").mkdir(parents=True)
    (project / "lib" / "src" / "help_request_module.dart").write_text(
        """
class HelpRequestModule {
  void init(Object config, String mode) {}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    (project / "ARCHITECTURE.md").write_text(
        """
# Architecture

## Integration

File: `lib/src/help_request_module.dart`.

```text
Host Flutter App
  -> HelpRequestModule.init(config, mode)
  -> HelpRequestNavigator / exported screens
```

Main class: `HelpRequestModule`.
""".strip(),
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(
        str(project),
        "HelpRequestModule init",
        tokens=1200,
        limit=5,
        response_style="snippet-first",
    )

    assert result.answer_available is False
    assert result.reason == "insufficient_code_symbol_evidence"
    assert result.primary_snippet is not None
    assert "HelpRequestModule.init" in result.primary_snippet["code"]
    assert any(item.get("source_class") == "source_evidence" and item.get("path") == "lib/src/help_request_module.dart" for item in result.context_pack)
    assert not any(action.get("tool") == "code_search" for action in result.next_actions)


def test_ingest_project_docs_no_candidates_returns_no_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service(tmp_path, monkeypatch)

    result = service.ingest_project_docs(str(project), with_vectors=False)

    assert result.status == "no_project_docs"
    assert result.candidate_count == 0
    assert result.sections_indexed == 0
    assert "No project-owned docs candidates" in (result.message or "")


def test_inspect_project_docs_recommends_architecture_bootstrap_when_no_docs(tmp_path, monkeypatch):
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
    assert "No reviewable project docs" in (result.agent_message or "")
    assert "ARCHITECTURE.md" in (result.user_message or "")
    action = result.recommended_next_actions[-1]
    assert action["action"] == "create_reviewable_project_doc"
    assert action["requires_confirmation"] is True
    assert action["preferred_path"] == "ARCHITECTURE.md"
    assert "ARCHITECTURE.md" in action["suggested_paths"]
    assert [item["tool"] for item in action["after"]] == ["prepare_docs", "get_docs_context"]
    assert "reviewable ARCHITECTURE.md" in (result.agent_guidance or "")


def test_inspect_project_docs_recommends_architecture_when_docs_lack_overview(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "runbooks").mkdir()
    (project / "runbooks" / "deploy.md").write_text("# Deploy\n\nDeployment steps only.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "architecture_doc_creation_recommended"
    assert result.project_docs["high_level_overview_found"] is False
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert "high-level project architecture document" in (result.user_message or "")
    action = result.recommended_next_actions[-1]
    assert action["action"] == "create_reviewable_project_doc"
    assert action["preferred_path"] == "ARCHITECTURE.md"
    assert "no high-level architecture or overview" in action["reason"]


def test_project_context_returns_source_grounded_public_docs_handoff(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "runbooks").mkdir()
    (project / "runbooks" / "deploy.md").write_text("# Deploy\n\nDeployment steps only.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "Explain the architecture", mode="project-only")

    action = next(item for item in result.next_actions if item.get("action") == "create_reviewable_project_doc")
    assert result.next_action is action
    assert result.requires_confirmation is True
    gap = action["documentation_gap"]
    assert gap["evidence_complete"] is False
    sections = {section["name"]: section for section in gap["required_sections"]}
    assert sections["purpose"]["state"] == "partial"
    assert sections["runtime flow"]["state"] == "missing"
    assert sections["runtime flow"]["missing_evidence"]
    assert sections["runtime flow"]["discovery_suggestions"]
    assert any("pubspec.yaml" in item["paths"] for item in gap["evidence_to_collect"])
    assert [item["tool"] for item in action["after"]] == ["prepare_docs", "get_docs_context"]

    public = service.get_docs_context(
        "Explain the architecture",
        project_path=str(project),
        mode="project",
    )
    assert public.next_action["action"] == "create_reviewable_project_doc"
    assert public.next_action["documentation_gap"]["evidence_complete"] is False
    assert [item["tool"] for item in public.next_action["after"]] == ["prepare_docs", "get_docs_context"]


def test_inspect_project_docs_treats_readme_as_high_level_overview(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_ready"
    assert result.project_docs["high_level_overview_found"] is True


def test_inspect_project_docs_reports_prefetched_dependency_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    now = service._now()
    for package in ("go_router", "riverpod"):
        version = "14.8.1" if package == "go_router" else "2.6.1"
        service.registry.upsert(
            library=package,
            ecosystem="pub",
            version=version,
            source_type="api",
            docs_url=f"https://pub.dev/documentation/{package}/{version}/",
            now=now,
            status="available",
            last_refreshed_at=now,
        )

    result = service.inspect_project_docs(str(project))

    assert result.dependency_sources["dependency_docs_available"] is True
    assert result.dependency_sources["dependency_docs_prefetched"] is True
    assert result.dependency_sources["dependency_docs_prefetched_count"] == 2
    assert result.dependency_sources["dependency_docs_missing_count"] == 0
    assert result.dependency_sources["dependency_docs_stale_count"] == 0
    assert result.dependency_sources["missing"] == []
    assert result.dependency_sources["stale"] == []
    assert result.dependency_sources["dependency_next_action"] == {}

    service.registry.upsert(
        library="riverpod",
        ecosystem="pub",
        version="2.6.1",
        source_type="api",
        docs_url="https://pub.dev/documentation/riverpod/2.6.1/",
        now=now,
        status="available",
        last_refreshed_at="2000-01-01T00:00:00+00:00",
    )
    stale_result = service.inspect_project_docs(str(project))
    assert stale_result.dependency_sources["dependency_docs_prefetched"] is False
    assert stale_result.dependency_sources["stale"] == ["riverpod"]
    assert stale_result.dependency_sources["dependency_next_action"]["arguments_patch"]["include_packages"] == ["riverpod"]


def test_bootstrap_project_docs_ingests_existing_docs_and_returns_ready(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nBootstrap ready overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="How is the app organized?")

    assert result.status == "ready"
    assert result.reason_code == "project_docs_ready"
    assert [action["tool"] for action in result.actions_taken] == [
        "inspect_project_docs",
        "sync_project_docs",
        "inspect_project_docs",
    ]
    assert result.ingest_result is None
    assert result.sync_result is not None
    assert result.sync_result.status == "success"
    assert result.next_action == {"type": "get_project_context", "tool": "get_project_context"}
    assert result.requires_confirmation is False
    assert result.arguments_patch == {"project_path": str(project.resolve()), "question": "How is the app organized?"}


def test_bootstrap_project_docs_stops_before_placeholder_preflight_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# TODO\n\nPlaceholder docs coming soon.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="How is the app organized?")

    assert result.status == "confirmation_required"
    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.sync_result is None
    assert [action["tool"] for action in result.actions_taken] == ["inspect_project_docs"]


def test_bootstrap_project_docs_stops_before_repo_write(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="Explain the architecture")

    assert result.status == "confirmation_required"
    assert result.reason_code == "no_project_docs"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert [action["tool"] for action in result.actions_taken] == ["inspect_project_docs"]


def test_bootstrap_project_docs_stops_before_dependency_network_fetch(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nBootstrap ready overview.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.bootstrap_project_docs(str(project), question="How should we use go_router?")

    assert result.status == "confirmation_required"
    assert result.reason_code == "dependency_docs_prefetch_confirmation_required"
    assert result.next_action["type"] == "ask_user_to_prefetch_dependency_docs"
    assert result.next_action["tool_after_confirmation"] == "prepare_docs"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "network_fetch"


def test_query_project_docs_filters_by_project_path_and_source_class(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    project_a = _flutter_project(tmp_path / "a")
    project_b = _flutter_project(tmp_path / "b")
    (project_a / "README.md").write_text("# Runbook\n\nSharedTopic alpha migration uses blue toggles.", encoding="utf-8")
    (project_b / "README.md").write_text("# Runbook\n\nSharedTopic beta migration uses red toggles.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project_a), with_vectors=False)
    service.ingest_project_docs(str(project_b), with_vectors=False)

    chunks = service.query_project_docs(str(project_a), "SharedTopic migration toggles", tokens=1200, limit=5)

    assert chunks
    assert all(chunk.metadata["project_path"] == str(project_a.resolve()) for chunk in chunks)
    assert all(chunk.metadata["source_class"] == SOURCE_CLASS_PROJECT_FILE for chunk in chunks)
    assert all(chunk.metadata["project_docs"] is True for chunk in chunks)
    assert any("alpha migration" in chunk.text for chunk in chunks)
    assert not any("beta migration" in chunk.text for chunk in chunks)


def test_query_project_docs_skips_oversized_first_authoritative_page(tmp_path):
    project = tmp_path / "app"
    project.mkdir()

    class Agent:
        config = SimpleNamespace(query=SimpleNamespace(default_limit=5))

        def query(self, query, *, limit, budget, expand, filters):
            assert filters["project_path"] == str(project.resolve())
            if filters.get("authority") == "source_of_truth":
                return [
                    RetrievedChunk(
                        source="large-runbook.md",
                        chunk_index=0,
                        text="large authoritative page",
                        score=1.0,
                        metadata={"token_estimate": 900},
                    ),
                    RetrievedChunk(
                        source="docs/PATROL_TESTING.md",
                        chunk_index=0,
                        text="start_patrol_develop is READY after PASS or FAIL.",
                        score=0.9,
                        metadata={"token_estimate": 100},
                    ),
                ]
            return []

    class Facade:
        def _agent_instance(self):
            return Agent()

    chunks = ProjectDocsService(Facade()).query_project_docs(
        str(project), "When is start_patrol_develop READY?", tokens=800, limit=5,
    )

    assert [chunk.source for chunk in chunks] == ["docs/PATROL_TESTING.md"]
    assert sum(chunk.metadata["token_estimate"] for chunk in chunks) <= 800


def test_query_project_docs_runs_lookup_queries_as_retrieval_only_supplements(tmp_path):
    project = tmp_path / "lookup"
    project.mkdir()
    observed: list[str] = []

    class Agent:
        config = SimpleNamespace(query=SimpleNamespace(default_limit=5))

        def query(self, query, *, limit, budget, expand, filters):
            observed.append(query)
            return [RetrievedChunk(
                source="docs/architecture.md",
                chunk_index=0,
                text="Request routing and retrieval lifecycle share one bounded architecture.",
                score=1.0,
                metadata={
                    "token_estimate": 20,
                    "lexical_match": {"qualified": True, "mode": "and"},
                },
            )]

    class Facade:
        def _agent_instance(self):
            return Agent()

    chunks = ProjectDocsService(Facade()).query_project_docs(
        str(project),
        "How does it work?",
        lookup_queries=("request routing architecture", "retrieval lifecycle"),
    )

    assert observed.count("How does it work?") == 2
    assert observed.count("request routing architecture") == 1
    assert observed.count("retrieval lifecycle") == 1
    assert len(chunks) == 1
    assert chunks[0].metadata["retrieval_query_ids"] == (
        "query-lookup-1", "query-lookup-2", "query-original",
    )


def test_query_project_docs_does_not_qualify_trace_less_candidates(tmp_path):
    project = tmp_path / "trace-less"
    project.mkdir()

    class Agent:
        config = SimpleNamespace(query=SimpleNamespace(default_limit=5))

        def query(self, query, *, limit, budget, expand, filters):
            return [RetrievedChunk(
                source="docs/generic.md",
                chunk_index=0,
                text="Generic candidate without a relevance trace.",
                score=0.9,
                metadata={"token_estimate": 20},
            )]

    class Facade:
        def _agent_instance(self):
            return Agent()

    chunks = ProjectDocsService(Facade()).query_project_docs(
        str(project), "Telegram notifications", limit=3,
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["retrieval_query_ids"] == ()
    assert chunks[0].metadata["retrieval_query_matches"]["query-original"]["qualified"] is False


def test_query_project_docs_keeps_best_duplicate_score(tmp_path):
    project = tmp_path / "scores"
    project.mkdir()

    class Agent:
        config = SimpleNamespace(query=SimpleNamespace(default_limit=5))

        def query(self, query, *, limit, budget, expand, filters):
            score = 0.95 if filters.get("authority") == "source_of_truth" else 0.4
            return [RetrievedChunk(
                source="docs/architecture.md",
                chunk_index=0,
                text="Qualified architecture evidence.",
                score=score,
                metadata={
                    "token_estimate": 20,
                    "lexical_match": {"qualified": True, "mode": "and"},
                },
            )]

    class Facade:
        def _agent_instance(self):
            return Agent()

    chunks = ProjectDocsService(Facade()).query_project_docs(
        str(project), "Architecture evidence", limit=3,
    )

    assert len(chunks) == 1
    assert chunks[0].score == 0.95
