"""Split test module; helpers live in _shared_test_docs_service.py."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_project_repository_identity_is_clone_stable_when_remote_is_available(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    remotes = (
        "https://secret-token@github.com/example/project.git",
        "git@github.com:example/project.git",
    )
    for root, remote in zip((first, second), remotes, strict=True):
        (root / ".git").mkdir(parents=True)
        (root / ".git" / "config").write_text(
            f'[remote "origin"]\n\turl = {remote}\n',
            encoding="utf-8",
        )

    identity = ProjectDocsService._repository_identity(first)
    assert identity == ProjectDocsService._repository_identity(second)
    assert identity == "git:github.com/example/project"
    assert "secret-token" not in identity


def test_project_repository_identity_isolates_unversioned_directories(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    assert ProjectDocsService._repository_identity(first) != ProjectDocsService._repository_identity(second)


def test_inspect_project_docs_returns_candidates_dependency_sources_and_next_actions(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.project_detected is True
    assert result.project_path == str(project.resolve())
    assert "flutter" in result.project_type
    assert result.project_docs["found"][0]["path"] == "README.md"
    assert result.reason_code == "project_docs_found_not_indexed"
    assert result.next_action == {"type": "sync_project_docs", "tool": "sync_project_docs"}
    assert result.requires_confirmation is False
    assert result.confirmation_reason is None
    assert result.arguments_patch["project_path"] == str(project.resolve())
    assert result.arguments_patch["with_vectors"] is False
    assert "not indexed" in (result.agent_message or "")
    assert result.user_message is None
    assert result.candidate_sources == result.project_docs["found"]
    assert result.project_docs["indexed"] == []
    assert result.project_docs["stale"] == []
    assert result.dependency_sources["manifests_found"] == ["pubspec.yaml"]
    assert result.dependency_sources["lockfiles_found"] == ["pubspec.lock"]
    assert result.dependency_sources["exact_versions_available"] is True
    assert result.dependency_sources["network_fetch_required"] is True
    assert result.dependency_sources["dependency_docs_available"] is True
    assert result.dependency_sources["dependency_docs_prefetched"] is False
    assert result.dependency_sources["dependency_docs_missing_count"] >= 2
    dependency_action = result.dependency_sources["dependency_next_action"]
    assert dependency_action["type"] == "ask_user_to_prefetch_dependency_docs"
    assert dependency_action["tool_after_confirmation"] == "prepare_docs"
    assert dependency_action["alias_tool_after_confirmation"] == "prefetch_project_dependency_docs"
    assert dependency_action["requires_confirmation"] is True
    assert dependency_action["confirmation_reason"] == "network_fetch"
    assert dependency_action["arguments_patch"] == {
        "action": "prefetch_project_dependency_docs",
        "project_path": str(project.resolve()),
        "include_packages": ["go_router", "riverpod"],
    }
    action_tools = [action["tool"] for action in result.recommended_next_actions]
    assert action_tools == ["sync_project_docs", "prefetch_project_docs"]
    assert result.recommended_next_actions[0]["requires_confirmation"] is False
    assert result.recommended_next_actions[1]["requires_confirmation"] is True
    assert "sync_project_docs" in (result.agent_guidance or "")


def test_inspect_project_docs_reports_node_manifest_and_selected_lockfile(tmp_path, monkeypatch):
    project = tmp_path / "node_app"
    project.mkdir()
    (project / "README.md").write_text("# Node app\n\nArchitecture overview.", encoding="utf-8")
    (project / "package.json").write_text(
        '{"packageManager":"pnpm@9.0.0","dependencies":{"react":"^18.0.0"}}',
        encoding="utf-8",
    )
    (project / "pnpm-lock.yaml").write_text(
        "lockfileVersion: '9.0'\nimporters:\n  .:\n    dependencies:\n      react:\n        specifier: ^18.0.0\n        version: 18.3.1\n",
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.dependency_sources["manifests_found"] == ["package.json"]
    assert result.dependency_sources["lockfiles_found"] == ["pnpm-lock.yaml"]
    assert result.dependency_sources["exact_versions_available"] is True
    assert result.project_type == ["npm"]
    assert result.dependency_sources["dependency_next_action"]["arguments_patch"] == {
        "action": "prefetch_project_dependency_docs",
        "project_path": str(project.resolve()),
        "include_packages": ["react"],
    }


def test_inspect_project_docs_requires_preflight_for_placeholder_readme_before_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# TODO\n\nPlaceholder docs coming soon.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_action["tool_after_confirmation"] == "sync_project_docs"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.recommended_next_actions[0]["requires_confirmation"] is True
    assert result.recommended_next_actions[0]["after_confirmation"]["tool"] == "sync_project_docs"
    preflight = result.diagnostics["preflight"]
    assert preflight["base_reason_code"] == "project_docs_found_not_indexed"
    assert preflight["requires_confirmation"] is True
    assert {risk["code"] for risk in preflight["risks"]} == {"placeholder_project_doc"}


def test_inspect_project_docs_requires_preflight_for_unsupported_root_doc_before_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    (project / "ARCHITECTURE.docx").write_text("Binary-ish architecture placeholder", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    preflight = result.diagnostics["preflight"]
    assert preflight["base_reason_code"] == "project_docs_found_not_indexed"
    assert preflight["safe_to_sync_without_confirmation"] is False
    assert {risk["code"] for risk in preflight["risks"]} == {"unsupported_project_doc_candidate"}
    assert preflight["risks"][0]["path"] == "ARCHITECTURE.docx"


def test_inspect_project_docs_reports_indexed_and_stale_sources(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginal project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    indexed = service.inspect_project_docs(str(project))

    assert indexed.reason_code == "project_docs_ready"
    assert indexed.next_action == {"type": "get_project_context", "tool": "get_project_context"}
    assert indexed.requires_confirmation is False
    assert indexed.project_docs["indexed"][0]["path"] == "README.md"
    assert indexed.project_docs["stale"] == []
    assert indexed.indexed_sources[0]["source_class"] == SOURCE_CLASS_PROJECT_FILE

    readme.write_text("# App\n\nUpdated project docs.", encoding="utf-8")
    stale = service.inspect_project_docs(str(project))

    assert stale.project_docs["stale"][0]["path"] == "README.md"
    assert stale.reason_code == "project_docs_preflight_confirmation_required"
    assert stale.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert stale.requires_confirmation is True
    assert stale.confirmation_reason == "project_docs_preflight"
    assert stale.arguments_patch == {"project_path": str(project.resolve())}
    assert "content_hash_changed" in stale.project_docs["stale"][0]["stale_reasons"]
    assert stale.recommended_next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert stale.diagnostics["preflight"]["base_reason_code"] == "project_docs_stale"
    assert {risk["code"] for risk in stale.diagnostics["preflight"]["risks"]} == {"stale_project_doc_sources"}


def test_inspect_project_docs_does_not_mark_mtime_only_change_stale(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nStable project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    original = readme.stat().st_mtime_ns
    os.utime(readme, ns=(original + 10_000_000, original + 10_000_000))

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "project_docs_ready"
    assert result.project_docs["stale"] == []
    assert result.project_docs["indexed"][0]["metadata_drift_reasons"] == ["mtime_changed"]


def test_ingest_project_docs_indexes_only_discovered_candidates_with_metadata(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text(
        "# App\n\n## Authentication\nUse `issue_token` from `lib/auth/token.dart`.\n",
        encoding="utf-8",
    )
    (project / "docs").mkdir()
    (project / "docs" / "testing.md").write_text("# Testing\n\nRun tests.", encoding="utf-8")
    (project / "lib").mkdir()
    (project / "lib" / "main.md").write_text("# Source docs should be ignored", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.ingest_project_docs(str(project), with_vectors=False)

    assert result.status == "success"

    assert result.candidate_count == 2
    assert result.sections_indexed == 3
    assert {item["path"] for item in result.indexed_sources} == {"README.md", "docs/testing.md"}
    assert result.skipped_sources == []
    assert "Indexed 2 project docs" in (result.message or "")

    with service._agent_instance().store._connect() as conn:
        rows = conn.execute("SELECT source, metadata_json FROM sources ORDER BY source").fetchall()
    sources = {Path(row["source"]).relative_to(project).as_posix(): row for row in rows}
    assert set(sources) == {"README.md", "docs/testing.md"}
    metadata = json.loads(sources["README.md"]["metadata_json"])
    assert metadata["source_class"] == "project_file"
    assert metadata["project_docs"] is True
    assert metadata["project_path"] == str(project.resolve())
    assert metadata["project_doc_path"] == "README.md"
    assert metadata["project_doc_reason"] == "root_readme"
    assert metadata["project_doc_sections_status"] == "parsed"
    assert metadata["project_doc_sections_reason"] == "section_metadata_parsed"
    assert metadata["project_doc_sections"] == [{
        "source_document_path": "README.md",
        "heading_path": ["App"],
        "mentioned_paths": [],
        "mentioned_symbols": [],
        "paths_truncated": False,
        "symbols_truncated": False,
        "fields_truncated": False,
        "document_sections_truncated": False,
        "content_hash": metadata["project_doc_sections"][0]["content_hash"],
    }, {
        "source_document_path": "README.md",
        "heading_path": ["App", "Authentication"],
        "mentioned_paths": ["lib/auth/token.dart"],
        "mentioned_symbols": ["issue_token"],
        "paths_truncated": False,
        "symbols_truncated": False,
        "fields_truncated": False,
        "document_sections_truncated": False,
        "content_hash": metadata["project_doc_sections"][1]["content_hash"],
    }]
    assert metadata["project_doc_sections"][0]["content_hash"].startswith("sha256:")


@pytest.mark.parametrize("retrieval_mode", ["dense", "sparse", "hybrid"])
def test_inspect_project_docs_enables_vector_sync_for_vector_retrieval(
    tmp_path, monkeypatch, retrieval_mode
):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.config.retrieval.default_mode = retrieval_mode

    result = service.inspect_project_docs(str(project))

    assert result.arguments_patch["with_vectors"] is True


def test_active_index_diagnostics_skips_vector_initialization_in_lexical_mode(
    tmp_path, monkeypatch
):
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.config.retrieval.default_mode = "lexical"
    monkeypatch.setattr(
        service.agent_gateway,
        "dispatcher_for",
        lambda *_args, **_kwargs: pytest.fail("lexical diagnostics initialized vectors"),
    )

    diagnostics = service.active_index_diagnostics()

    assert diagnostics["vector_readiness"] == {
        "status": "not_required",
        "mode": "lexical",
    }


def test_ingest_project_docs_reports_missing_candidates_after_verification(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nIntro", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "bad.md").write_bytes(b"# Bad\n\xff")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.ingest_project_docs(str(project), with_vectors=False)

    assert result.status == "partial"
    assert {item["path"] for item in result.indexed_sources} == {"README.md"}
    assert result.missing_sources[0]["path"] == "docs/bad.md"
    assert "Missing 1 project docs" in (result.message or "")


def test_ingest_project_docs_is_idempotent_with_skip_known(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    first = service.ingest_project_docs(str(project), with_vectors=False)
    second = service.ingest_project_docs(str(project), with_vectors=False)

    assert first.status == "success"
    assert first.sections_indexed == 1
    assert second.status == "success"
    assert second.sections_indexed == 0
    assert {item["path"] for item in second.indexed_sources} == {"README.md"}
    assert len(second.skipped_sources) == 1
    assert second.skipped_sources[0]["exception_type"] == "SkippedKnownFile"
    with service._agent_instance().store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0] == 1


def test_sync_project_docs_backfills_known_file_missing_project_doc_metadata(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nBackfillKnownNeedle project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    agent = service._agent_instance()
    agent.ingest(project, include_exact=("README.md",), with_vectors=False)

    before = service.inspect_project_docs(str(project))
    result = service.sync_project_docs(str(project), with_vectors=False)
    after = service.inspect_project_docs(str(project))

    assert before.reason_code == "project_docs_found_not_indexed"
    assert result.status == "success"
    assert result.current_count == 1
    assert result.missing_sources == []
    assert {item["path"] for item in result.indexed_sources} == {"README.md"}
    assert after.reason_code == "project_docs_ready"

    with agent.store._connect() as conn:
        row = conn.execute("SELECT metadata_json FROM sources WHERE source = ?", (str(project / "README.md"),)).fetchone()
    metadata = json.loads(row["metadata_json"] or "{}")
    assert metadata["project_docs"] is True
    assert metadata["project_doc_path"] == "README.md"


def test_get_project_docs_never_returns_deleted_orphaned_file_content(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    deleted = project / "docs" / "old.md"
    deleted.write_text("# Old\n\nOldNeedle should not be returned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    deleted.unlink()

    result = service.get_project_docs(str(project), "OldNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.results == []
    assert result.ignored_sources[0]["path"] == "docs/old.md"
    assert "OldNeedle" not in json.dumps([item.content for item in result.results])


def test_get_project_docs_never_returns_hash_mismatched_stale_content(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginalNeedle should not be returned after edits.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.write_text("# App\n\nCurrent docs without the old needle.", encoding="utf-8")

    result = service.get_project_docs(str(project), "OriginalNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.results == []
    assert result.stale_sources[0]["path"] == "README.md"
    assert result.stale_sources[0]["stale_reasons"] == ["content_hash_changed"]


def test_get_project_context_never_returns_deleted_orphaned_file_content(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    deleted = project / "docs" / "old.md"
    deleted.write_text("# Old\n\nOldContextNeedle should not be returned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    deleted.unlink()

    result = service.get_project_context(str(project), "OldContextNeedle", tokens=1200, limit=5)

    assert result.answer_available is False
    assert result.context_pack == []
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert "OldContextNeedle" not in json.dumps(result.trust_contract)


def test_get_project_context_requires_preflight_for_placeholder_readme_before_sync(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# TODO\n\nPlaceholder docs coming soon.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "What is the architecture?", tokens=1200, limit=3)

    assert result.status == "confirmation_required"
    assert result.answer_available is False
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.next_action["tool_after_confirmation"] == "sync_project_docs"
    assert result.project_docs is not None
    assert result.project_docs.requires_confirmation is True
    assert result.project_docs.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"
    assert not any(
        action.get("tool") == "sync_project_docs" and action.get("requires_confirmation") is False
        for action in result.next_actions
    )


def test_get_project_context_requires_preflight_for_unsupported_root_doc(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nProject overview.", encoding="utf-8")
    (project / "ARCHITECTURE.docx").write_text("Binary-ish architecture placeholder", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "What is the architecture?", tokens=1200, limit=3)

    assert result.status == "confirmation_required"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert result.project_docs is not None
    assert result.project_docs.next_actions[0]["risk_codes"] == ["unsupported_project_doc_candidate"]


def test_sync_project_docs_prunes_orphaned_sources_and_indexes_new_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    old = project / "docs" / "old.md"
    old.write_text("# Old\n\nOldSyncNeedle should be pruned.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    old.unlink()
    (project / "docs" / "new.md").write_text("# New\n\nNewSyncNeedle should be indexed.", encoding="utf-8")

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.new_count == 1
    assert result.orphaned_count == 1
    assert result.orphaned_removed == 1
    assert {item["path"] for item in result.indexed_sources} == {"README.md", "docs/new.md"}
    assert result.missing_sources == []
    assert {item["path"] for item in result.removed_sources} == {"docs/old.md"}

    old_query = service.get_project_docs(str(project), "OldSyncNeedle", tokens=1200, limit=5)
    new_query = service.get_project_docs(str(project), "NewSyncNeedle", tokens=1200, limit=5)

    assert old_query.results == []
    assert new_query.answer_available is True
    assert "NewSyncNeedle" in new_query.results[0].content


def test_sync_project_docs_removes_extracted_artifacts_for_deleted_source(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nCurrent docs.", encoding="utf-8")
    (project / "docs").mkdir()
    deleted = project / "docs" / "old.md"
    deleted.write_text(
        "# Old\n\nDeletedArtifactNeedle must not remain on disk.",
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    with service._agent_instance().store._connect() as conn:
        row = conn.execute(
            "SELECT markdown_path, json_path FROM sources WHERE source = ?",
            (str(deleted),),
        ).fetchone()
    assert row is not None
    extracted_artifacts = [Path(row["markdown_path"]), Path(row["json_path"])]
    assert all(path.exists() for path in extracted_artifacts)

    deleted.unlink()
    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.orphaned_removed == 1
    assert all(not path.exists() for path in extracted_artifacts)


def test_invalid_explicit_catalog_blocks_lifecycle_and_preserves_index(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nExisting indexed docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 9\n",
        encoding="utf-8",
    )

    inspect = service.inspect_project_docs(str(project))
    get_result = service.get_project_docs(str(project), "architecture")
    context = service.get_project_context(str(project), "architecture", mode="project-only")
    ingest = service.ingest_project_docs(str(project), with_vectors=False)
    sync = service.sync_project_docs(str(project), with_vectors=False)

    assert inspect.reason_code == "invalid_project_docs_catalog"
    assert inspect.next_action["type"] == "fix_project_docs_catalog"
    assert inspect.ignored_sources == []
    assert len(inspect.project_docs["preserved_indexed"]) == 1
    assert inspect.diagnostics["indexed_sources_preserved"] == 1
    assert [item["type"] for item in inspect.recommended_next_actions if "type" in item] == [
        "fix_project_docs_catalog"
    ]
    assert "Do not create docs, sync, or prune" in (inspect.agent_guidance or "")
    assert get_result.status == "invalid_project_docs_catalog"
    assert get_result.next_action["type"] == "fix_project_docs_catalog"
    assert context.answer_available is False
    assert context.next_action["type"] == "fix_project_docs_catalog"
    assert ingest.status == "invalid_project_docs_catalog"
    assert sync.status == "invalid_project_docs_catalog"
    assert sync.removed_sources == []
    assert sync.diagnostics["indexed_sources_preserved"] == 1
    with service._agent_instance().store._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1


def test_sync_project_docs_ingests_only_exact_discovered_candidates(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nRoot project overview.", encoding="utf-8")
    eval_readme = project / "eval" / "task_level" / "fixtures" / "README.md"
    eval_readme.parent.mkdir(parents=True)
    eval_readme.write_text("# Eval fixture\n\nShould not be indexed as project docs.", encoding="utf-8")
    example_readme = project / "example" / "README.md"
    example_readme.parent.mkdir()
    example_readme.write_text("# Example\n\nShould not be indexed as project docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.sync_project_docs(str(project), with_vectors=False)
    inspect = service.inspect_project_docs(str(project))

    assert result.status == "success"
    assert result.candidate_count == 1
    assert result.current_count == 1
    assert result.sections_indexed == 1
    assert result.missing_sources == []
    assert inspect.reason_code == "project_docs_ready"
    assert inspect.ignored_sources == []
    assert {item["path"] for item in inspect.indexed_sources} == {"README.md"}

    with service._agent_instance().store._connect() as conn:
        rows = conn.execute("SELECT source, metadata_json FROM sources ORDER BY source").fetchall()
    sources = {
        Path(row["source"]).relative_to(project).as_posix(): json.loads(row["metadata_json"] or "{}")
        for row in rows
    }
    assert set(sources) == {"README.md"}
    assert sources["README.md"]["project_doc_path"] == "README.md"


def test_sync_project_docs_converges_on_extensionless_license_candidate(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nRoot project overview.", encoding="utf-8")
    (project / "ARCHITECTURE.md").write_text("# Architecture\n\nSystem overview.", encoding="utf-8")
    (project / "CHANGELOG.md").write_text("# Changelog\n\nInitial release.", encoding="utf-8")
    (project / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    first = service.sync_project_docs(str(project), with_vectors=False)
    second = service.sync_project_docs(str(project), with_vectors=False)
    inspect = service.inspect_project_docs(str(project))

    assert first.status == "success"
    assert first.candidate_count == 4
    assert first.current_count == 4
    assert first.missing_sources == []
    assert second.status == "success"
    assert second.current_count == 4
    assert second.new_count == 0
    assert second.changed_count == 0
    assert second.missing_sources == []
    assert second.orphaned_removed == 0
    assert inspect.reason_code == "project_docs_ready"
    assert {item["path"] for item in inspect.indexed_sources} == {
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "LICENSE",
        "README.md",
    }


def test_sync_project_docs_reindexes_changed_sources_and_removes_stale_index(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOldChangedNeedle should disappear.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.write_text("# App\n\nNewChangedNeedle should appear.", encoding="utf-8")

    result = service.sync_project_docs(str(project), with_vectors=False)

    assert result.status == "success"
    assert result.changed_count == 1
    assert result.stale_removed == 1
    assert result.orphaned_removed == 0
    assert result.stale_sources == []

    old_query = service.get_project_docs(str(project), "OldChangedNeedle", tokens=1200, limit=5)
    new_query = service.get_project_docs(str(project), "NewChangedNeedle", tokens=1200, limit=5)

    assert old_query.results == []
    assert new_query.answer_available is True
    assert "NewChangedNeedle" in new_query.results[0].content


def test_incremental_sync_reindexes_only_accepted_changed_doc(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# App\n\nOriginal overview.", encoding="utf-8")
    docs = project / "docs"
    docs.mkdir()
    guide = docs / "guide.md"
    guide.write_text("# Guide\n\nOldIncrementalNeedle.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)
    readme_source_before = next(
        item for item in service._indexed_project_doc_sources(str(project))
        if item["path"] == "README.md"
    )
    guide.write_text("# Guide\n\nNewIncrementalNeedle.", encoding="utf-8")

    result = service.sync_project_docs(
        str(project), with_vectors=False, changed_paths=["docs/guide.md"]
    )
    readme_source_after = next(
        item for item in service._indexed_project_doc_sources(str(project))
        if item["path"] == "README.md"
    )

    assert result.status == "success"
    assert result.changed_count == 1
    assert result.diagnostics["mode"] == "incremental"
    assert result.diagnostics["metrics"]["files_reprocessed"] == 1
    assert result.diagnostics["metrics"]["derived_writes"] == 1
    assert readme_source_after["ingested_at"] == readme_source_before["ingested_at"]
    assert service.get_project_docs(str(project), "OldIncrementalNeedle").results == []
    assert "NewIncrementalNeedle" in service.get_project_docs(
        str(project), "NewIncrementalNeedle"
    ).results[0].content


def test_incremental_sync_is_idempotent_for_unchanged_save(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nStable docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    result = service.sync_project_docs(
        str(project), with_vectors=False, changed_paths=["README.md"]
    )

    assert result.status == "success"
    assert result.sections_indexed == 0
    assert result.removed_sources == []
    assert result.tombstones == []
    assert result.diagnostics["metrics"] | {"latency_ms": 0} == {
        "files_reprocessed": 0,
        "sections_reprocessed": 0,
        "unchanged_files": 1,
        "derived_deletes": 0,
        "derived_writes": 0,
        "vector_chunks_pruned": 0,
        "unrelated_files_reprocessed": 0,
        "unchanged_derived_writes": 0,
        "latency_ms": 0,
    }
    assert result.diagnostics["metrics"]["latency_ms"] >= 0


def test_unchanged_project_sync_with_vectors_runs_full_parity(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App\n\nStable vector docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)
    agent = service._agent_instance()
    calls = []

    def sync_vectors():
        calls.append("full")
        agent.last_vector_sync_metrics = {
            "status": "success",
            "verified": 1,
            "backfilled": 0,
            "skipped_unchanged": 1,
            "collection": "project-vectors",
        }
        return object()

    monkeypatch.setattr(agent, "sync_vectors", sync_vectors)

    result = service.sync_project_docs(
        str(project), with_vectors=True, changed_paths=["README.md"]
    )

    assert calls == ["full"]
    assert result.sections_indexed == 0
    assert result.diagnostics["vector_sync"] == {
        "status": "success",
        "verified": 1,
        "backfilled": 0,
        "skipped_unchanged": 1,
        "collection": "project-vectors",
        "requested": True,
        "retrieval_mode": "lexical",
    }
