"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_get_project_docs_reports_stale_project_docs(tmp_path, monkeypatch):
    from tests._fixture_member_transaction import indexed_fixture_member_service

    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal ProjectStaleAnswer.", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored project overview fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md",),
    )

    before = service.get_project_docs(str(project), "ProjectStaleAnswer", tokens=1200, limit=3)
    assert before.results
    assert {chunk.path for chunk in before.results} == {"README.md"}
    assert {chunk.source for chunk in before.results} == {str(readme)}
    assert {chunk.content_hash for chunk in before.results} == {
        "sha256:" + hashlib.sha256(readme.read_bytes()).hexdigest(),
    }
    assert any("ProjectStaleAnswer" in chunk.content for chunk in before.results)

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
    from tests._fixture_member_transaction import indexed_fixture_member_service

    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal ProjectStaleContextAnswer.", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored project overview fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md",),
    )

    before = service.get_project_docs(str(project), "ProjectStaleContextAnswer", tokens=1200, limit=3)
    assert before.results
    assert {chunk.path for chunk in before.results} == {"README.md"}
    assert {chunk.source for chunk in before.results} == {str(readme)}
    assert {chunk.content_hash for chunk in before.results} == {
        "sha256:" + hashlib.sha256(readme.read_bytes()).hexdigest(),
    }
    assert any("ProjectStaleContextAnswer" in chunk.content for chunk in before.results)

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










def test_exact_version_with_unversioned_url_is_not_exact(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch)

    result = service.resolve_library("pytest", version="8.3.4", docs_url="https://docs.pytest.org/")

    assert result.library_id == "pytest@8.3.4"
    assert result.docs_snapshot_exact is False


