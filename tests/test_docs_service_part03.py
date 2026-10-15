"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_get_project_docs_returns_scoped_docs_result(tmp_path, monkeypatch):
    from tests._fixture_member_transaction import indexed_fixture_member_service
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectAnswer uses the local ADR flow.", encoding="utf-8")
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored project overview fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(tmp_path, monkeypatch, project, ("README.md",))

    result = service.get_project_docs(str(project), "ProjectAnswer ADR", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.tool == "get_project_docs"
    assert result.project_path == str(project.resolve())
    assert result.results
    assert result.results[0].source is not None
    assert result.results[0].source_class == SOURCE_CLASS_PROJECT_FILE
    assert result.results[0].path == "README.md"
    assert result.results[0].heading_path == "Architecture"
    assert result.results[0].content_hash is not None
    assert result.results[0].mtime_ns is not None
    assert result.results[0].mtime_ns == (project / "README.md").stat().st_mtime_ns
    assert "ProjectAnswer" in result.results[0].content
    assert result.indexed_sources[0]["path"] == "README.md"
    assert result.next_actions == []


def test_get_project_docs_can_filter_by_module_path(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    backend = project / "packages" / "backend"
    frontend = project / "packages" / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    (backend / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    (frontend / "README.md").write_text("# Frontend\n\nSharedNeedle FrontendOnlyAnswer.", encoding="utf-8")
    from tests._fixture_member_transaction import indexed_fixture_member_service
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: packages/backend/README.md\n"
        "    role: other\n"
        "    scope: module\n"
        "    module_path: packages/backend\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: packages/frontend/README.md\n"
        "    role: other\n"
        "    scope: module\n"
        "    module_path: packages/frontend\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md", "packages/backend/README.md", "packages/frontend/README.md"),
    )

    result = service.get_project_docs(str(project), "SharedNeedle", module_path="packages/backend", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.results
    assert all(item.module_path == "packages/backend" for item in result.results)
    assert all(item.doc_scope == "module" for item in result.results)
    assert any("BackendOnlyAnswer" in item.content for item in result.results)
    assert not any("FrontendOnlyAnswer" in item.content for item in result.results)


def test_get_project_docs_can_filter_by_module_name_exact_match(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    backend = project / "packages" / "backend"
    frontend = project / "packages" / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    (backend / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    (frontend / "README.md").write_text("# Frontend\n\nSharedNeedle FrontendOnlyAnswer.", encoding="utf-8")
    from tests._fixture_member_transaction import indexed_fixture_member_service
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: packages/backend/README.md\n"
        "    role: other\n"
        "    scope: module\n"
        "    module_path: packages/backend\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: packages/frontend/README.md\n"
        "    role: other\n"
        "    scope: module\n"
        "    module_path: packages/frontend\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md", "packages/backend/README.md", "packages/frontend/README.md"),
    )

    result = service.get_project_docs(str(project), "SharedNeedle", module="backend", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.results
    assert all(item.module_path == "packages/backend" for item in result.results)
    assert any("BackendOnlyAnswer" in item.content for item in result.results)
    assert not any("FrontendOnlyAnswer" in item.content for item in result.results)


def test_get_project_docs_returns_structured_module_not_found(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Backend", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "auth", module_path="services/auth", tokens=1200, limit=3)

    assert result.status == "module_not_found"
    assert result.reason_code == "module_not_found"
    assert result.answer_available is False
    assert result.next_action == {"type": "inspect_project_docs", "tool": "inspect_project_docs"}
    assert result.arguments_patch == {"project_path": str(project.resolve())}


def test_get_project_docs_project_scope_preserves_backward_compatibility(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nSharedNeedle RootProjectAnswer.", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    from tests._fixture_member_transaction import indexed_fixture_member_service
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: packages/backend/README.md\n"
        "    role: other\n"
        "    scope: module\n"
        "    module_path: packages/backend\n"
        "    description: Authored read isolation fixture.\n"
        "    authority: supporting\n"
        "    status: active\n"
        "    impact: track\n"
        "roots: []\n"
        "code_files: []\n",
        encoding="utf-8",
    )
    service, _ = indexed_fixture_member_service(
        tmp_path, monkeypatch, project, ("README.md", "packages/backend/README.md"),
    )

    result = service.get_project_docs(str(project), "SharedNeedle", scope="project", tokens=1200, limit=5)

    assert result.status == "success"
    assert result.results
    assert all(item.doc_scope == "project" for item in result.results)
    assert any("RootProjectAnswer" in item.content for item in result.results)
    assert not any("BackendOnlyAnswer" in item.content for item in result.results)










def test_get_project_docs_distinguishes_indexed_no_results_from_not_indexed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nKnown project docs topic.", encoding="utf-8")
    from tests._fixture_member_transaction import indexed_fixture_member_service
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Authored read isolation fixture.\n"
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

    result = service.get_project_docs(str(project), "UnrelatedNeedleThatDoesNotExist", tokens=1200, limit=3)

    assert result.status == "no_results"
    assert result.answer_available is False
    assert result.reason == "no_project_docs_results"
    assert result.reason_code == "no_project_docs_results"
    assert result.next_action == {"type": "inspect_project_docs", "tool": "inspect_project_docs"}
    assert result.requires_confirmation is False
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert result.indexed_sources[0]["path"] == "README.md"
    assert result.next_actions[0]["tool"] == "inspect_project_docs"
