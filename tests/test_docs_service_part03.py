"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_project_query_does_not_return_non_project_docs_with_same_terms(tmp_path, monkeypatch):
    project = tmp_path / "app"
    project.mkdir()
    docs = project / "docs"
    docs.mkdir()
    distractor = (
        "# Presentation plan notes\n\n"
        "Phase 2.3 presentation-only snippets mention EvidenceRequirementSet, "
        "SupportDecision, and decision_hash, but this supporting note does not "
        "define the acceptance contract.\n"
    )
    for index in range(24):
        (docs / f"note-{index:02d}.md").write_text(distractor, encoding="utf-8")
    (project / "zz-authoritative-plan.md").write_text(
        """# Approved retrieval plan

## Phase 2.3: presentation-only snippets

EvidenceRequirementSet and SupportDecision are canonical selector inputs.
Presentation cannot determine support or drop a mandatory-facet witness.
Every public mode preserves the same decision_hash and selected evidence IDs.

## Phase 3.1: dispatcher reuse

Library lexical retrieval invokes RetrievalDispatcher with the raw topic unchanged.
EvidenceRequirementSet supplies recall hints but never a second support decision.
The first production mode remains lexical and must not call vectors or embeddings.

## Phase 3.1: index-witness retrieval-miss classification

Files:

- docmancer/docs/application/library_docs_service.py
- docmancer/docs/infrastructure/agent_index_gateway.py

Classify retrieval_miss only when the complete same-library, exact-version corpus
contains mandatory-requirement witnesses confirmed by a bounded index-level probe
outside the selected candidates. Never infer retrieval_miss from an empty candidate
list. Keep the default lexical path provider-free: it makes no vector, embedding,
or provider calls.
""",
        encoding="utf-8",
    )
    (project / "README.md").write_text(
        "# Project overview\n\nThis repository owns the approved retrieval plan.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        """schema_version: 1
documents:
  - path: zz-authoritative-plan.md
    role: development
    scope: project
    description: Approved implementation plan and acceptance contract.
    authority: source_of_truth
    status: active
    impact: track
  - path: README.md
    role: overview
    scope: project
    description: Project overview.
    authority: supporting
    status: active
    impact: track
roots:
  - path: docs
    scope: project
    authority: supporting
""",
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)
    ingest = service.ingest_project_docs(str(project), with_vectors=False)
    assert ingest.status == "success", ingest.message

    question = (
        "What exact Phase 2.3 presentation-only snippet contract governs "
        "EvidenceRequirementSet, SupportDecision, and decision_hash?"
    )
    payload = handle_context_tool(
        "get_docs_context",
        {
            "question": question,
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
        },
        service,
    )

    assert payload is not None
    assert payload["status"] == "ok", payload.get("missing")
    assert any(source["path_or_url"].endswith("zz-authoritative-plan.md") for source in payload["sources"])
    assert any(
        "cannot determine support" in source["snippet"]
        and "mandatory-facet witness" in source["snippet"]
        for source in payload["sources"]
    )

    dispatcher_payload = handle_context_tool(
        "get_docs_context",
        {
            "question": (
                "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, "
                "EvidenceRequirementSet hints, and vector or embedding calls?"
            ),
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
        },
        service,
    )
    assert dispatcher_payload is not None
    assert dispatcher_payload["status"] == "insufficient_evidence"
    assert (
        "unresolved:0:legacy_unresolved:requirement_items"
        in dispatcher_payload.get("missing", [])
    )

    index_witness_question = (
        "Fix library_docs_service.py Phase 3.1 retrieval_miss classification for the "
        "complete same-library exact-version corpus using a bounded index witness probe, "
        "without forbidden calls."
    )
    index_witness_payload = handle_context_tool(
        "get_docs_context",
        {
            "question": index_witness_question,
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
        },
        service,
    )
    assert index_witness_payload is not None
    assert index_witness_payload["status"] == "insufficient_evidence"
    assert index_witness_payload["kind"] == "patch_context"
    assert index_witness_payload["edit_ready"] is True
    assert index_witness_payload["recommended_next_action"]["tool"] == "code_search"
    assert "library_docs_service.py" in index_witness_payload["recommended_next_action"]["suggested_doc_paths"]


    novel_index_witness_payload = handle_context_tool(
        "get_docs_context",
        {
            "question": (
                "Implement in library_docs_service.py candidate-omission retrieval_miss handling "
                "for one pinned library release: require its evidence proof and preserve local "
                "retrieval restrictions."
            ),
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
        },
        service,
    )
    assert novel_index_witness_payload is not None
    assert novel_index_witness_payload["status"] == "insufficient_evidence"
    assert novel_index_witness_payload["kind"] == "patch_context"
    assert novel_index_witness_payload["edit_ready"] is True
    assert novel_index_witness_payload["recommended_next_action"]["tool"] == "code_search"
    assert "library_docs_service.py" in novel_index_witness_payload["recommended_next_action"]["suggested_doc_paths"]


    absent = handle_context_tool(
        "get_docs_context",
        {
            "question": question.replace("decision_hash", "missing_decision_audit_symbol"),
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
        },
        service,
    )
    assert absent is not None
    assert absent["status"] == "insufficient_evidence"

    foreign_root = tmp_path / "foreign"
    foreign_root.mkdir()
    foreign = foreign_root / "app"
    foreign.mkdir()
    (foreign / "README.md").write_text(
        "# Foreign plan\n\nmissing_decision_audit_symbol is defined only here.\n",
        encoding="utf-8",
    )
    foreign_ingest = service.ingest_project_docs(str(foreign), with_vectors=False)
    assert foreign_ingest.status == "success", foreign_ingest.message
    isolated = handle_context_tool(
        "get_docs_context",
        {
            "question": "Where is missing_decision_audit_symbol defined?",
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
        },
        service,
    )
    assert isolated is not None
    assert isolated["status"] == "insufficient_evidence"
    assert all(
        not source.get("path_or_url", "").startswith(str(foreign))
        for source in isolated.get("sources", [])
    )


def test_get_project_docs_returns_scoped_docs_result(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectAnswer uses the local ADR flow.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

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
    assert "ProjectAnswer" in result.results[0].content
    assert result.indexed_sources[0]["path"] == "README.md"
    assert result.next_actions == []


def test_inspect_project_docs_lists_discovered_modules(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# App", encoding="utf-8")
    module_docs = project / "packages" / "backend" / "docs"
    module_docs.mkdir(parents=True)
    (project / "packages" / "backend" / "README.md").write_text("# Backend", encoding="utf-8")
    (module_docs / "architecture.md").write_text("# Backend architecture", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    modules = result.project_docs["modules"]
    assert modules == [{
        "module_id": "packages/backend",
        "module_name": "backend",
        "module_path": "packages/backend",
        "module_type": "package",
        "doc_count": 2,
        "docs": ["packages/backend/README.md", "packages/backend/docs/architecture.md"],
    }]


def test_get_project_docs_can_filter_by_module_path(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    backend = project / "packages" / "backend"
    frontend = project / "packages" / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    (backend / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    (frontend / "README.md").write_text("# Frontend\n\nSharedNeedle FrontendOnlyAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "SharedNeedle", module_path="packages/backend", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.results
    assert all(item.module_path == "packages/backend" for item in result.results)
    assert all(item.doc_scope == "module" for item in result.results)
    assert any("BackendOnlyAnswer" in item.content for item in result.results)
    assert not any("FrontendOnlyAnswer" in item.content for item in result.results)


def test_ingested_module_metadata_roundtrips_to_inspect_and_results(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    module = project / "services" / "auth"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Auth service\n\nAuthRoundtripNeedle module docs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    ingest = service.ingest_project_docs(str(project), with_vectors=False)
    inspect = service.inspect_project_docs(str(project))
    result = service.get_project_docs(str(project), "AuthRoundtripNeedle", module="auth", tokens=1200, limit=3)

    assert ingest.status == "success"
    assert inspect.project_docs["indexed_modules"] == [{
        "module_id": "services/auth",
        "module_name": "auth",
        "module_path": "services/auth",
        "module_type": "service",
        "doc_count": 1,
        "docs": ["services/auth/README.md"],
    }]
    assert result.status == "success"
    assert result.results
    assert result.results[0].module_id == "services/auth"
    assert result.results[0].module_name == "auth"
    assert result.results[0].module_path == "services/auth"
    assert result.results[0].module_type == "service"
    assert result.indexed_sources[0]["doc_scope"] == "module"
    assert result.indexed_sources[0]["module_path"] == "services/auth"


def test_get_project_docs_can_filter_by_module_name_exact_match(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    backend = project / "packages" / "backend"
    frontend = project / "packages" / "frontend"
    backend.mkdir(parents=True)
    frontend.mkdir(parents=True)
    (backend / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    (frontend / "README.md").write_text("# Frontend\n\nSharedNeedle FrontendOnlyAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "SharedNeedle", module="backend", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.results
    assert all(item.module_path == "packages/backend" for item in result.results)
    assert any("BackendOnlyAnswer" in item.content for item in result.results)
    assert not any("FrontendOnlyAnswer" in item.content for item in result.results)


def test_get_project_docs_returns_structured_module_ambiguity(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    for parent in ("packages", "services"):
        module = project / parent / "auth"
        module.mkdir(parents=True)
        (module / "README.md").write_text(f"# {parent} auth", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "auth", module="auth", tokens=1200, limit=3)

    assert result.status == "module_ambiguous"
    assert result.reason_code == "module_ambiguous"
    assert result.answer_available is False
    assert result.next_actions[0]["arguments_patch"] == {"project_path": str(project.resolve())}


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


def test_get_project_docs_reports_stale_module_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    doc = module / "README.md"
    doc.write_text("# Backend\n\nStaleNeedle first version.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    time.sleep(0.01)
    doc.write_text("# Backend\n\nStaleNeedle changed version.", encoding="utf-8")

    result = service.get_project_docs(str(project), "StaleNeedle", module_path="packages/backend", tokens=1200, limit=3)

    assert result.status == "stale"
    assert result.reason_code == "project_docs_preflight_confirmation_required"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "project_docs_preflight"
    assert result.stale_sources
    assert result.stale_sources[0]["candidate"]["module_path"] == "packages/backend"
    assert result.next_actions[0]["action"] == "ask_user_to_update_or_confirm_project_docs"


def test_get_project_docs_project_scope_preserves_backward_compatibility(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nSharedNeedle RootProjectAnswer.", encoding="utf-8")
    module = project / "packages" / "backend"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Backend\n\nSharedNeedle BackendOnlyAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_docs(str(project), "SharedNeedle", scope="project", tokens=1200, limit=5)

    assert result.status == "success"
    assert result.results
    assert all(item.doc_scope == "project" for item in result.results)
    assert any("RootProjectAnswer" in item.content for item in result.results)
    assert not any("BackendOnlyAnswer" in item.content for item in result.results)


def test_get_project_context_returns_trust_contract_for_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectContextAnswer uses local ADRs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "ProjectContextAnswer ADR", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.tool == "get_project_context"
    assert result.project_docs is not None
    assert result.project_docs.results
    assert result.context_pack[0]["source_class"] == "project_doc"
    assert result.context_pack[0]["token_estimate"] > 0
    assert result.metrics["project_result_count"] == 1
    selected = result.trust_contract["sources"]["selected"]
    assert selected[0]["source_class"] == "project_file"
    assert selected[0]["trust_level"] == "provenance_verified_non_instructional"
    assert "trusted_sources" not in result.trust_contract
    assert result.trust_contract["policy"]["direct_webfetch"] == "forbidden"


def test_get_project_context_low_signal_single_token_query_returns_no_results(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProjectContextAnswer uses local ADRs.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "test", tokens=1200, limit=3)

    assert result.status == "no_results"
    assert result.answer_available is False
    assert result.reason == "no_reliable_context"


def test_get_project_context_preserves_module_metadata_in_pack_and_trust_contract(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nRootProjectAnswer only.", encoding="utf-8")
    module = project / "services" / "auth"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Auth\n\nContextModuleNeedle AuthContextAnswer.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

    result = service.get_project_context(str(project), "ContextModuleNeedle", module_path="services/auth", scope="module", mode="project-only", tokens=1200, limit=3)

    assert result.status == "success"
    assert result.project_docs is not None
    assert result.project_docs.results[0].module_path == "services/auth"
    assert result.context_pack[0]["doc_scope"] == "module"
    assert result.context_pack[0]["module_id"] == "services/auth"
    assert result.context_pack[0]["module_name"] == "auth"
    assert result.context_pack[0]["module_path"] == "services/auth"
    assert result.context_pack[0]["module_type"] == "service"
    selected = result.trust_contract["sources"]["selected"]
    assert selected[0]["doc_scope"] == "module"
    assert selected[0]["module_path"] == "services/auth"


def test_get_project_context_before_ingest_returns_actionable_remediation(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProject docs exist but are not indexed.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "Architecture", tokens=1200, limit=3)

    assert result.status == "not_indexed"
    assert result.answer_available is False
    assert result.project_docs is not None
    assert result.project_docs.reason_code == "project_docs_found_not_indexed"
    assert result.next_actions[0]["tool"] == "sync_project_docs"
    assert result.next_actions[0]["arguments_patch"] == {"project_path": str(project.resolve()), "with_vectors": False}
    assert result.trust_contract["next_actions"][0]["tool"] == "sync_project_docs"
    assert "not indexed" in (result.message or "")


def test_bootstrap_project_docs_requires_confirmation_before_refreshing_stale_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    readme = project / "README.md"
    readme.write_text("# Architecture\n\nOriginal stale acceptance text.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    readme.write_text("# Architecture\n\nFreshAcceptanceNeedle text.", encoding="utf-8")

    bootstrap = service.bootstrap_project_docs(str(project), question="FreshAcceptanceNeedle")

    assert bootstrap.status == "confirmation_required"
    assert bootstrap.reason_code == "project_docs_preflight_confirmation_required"
    assert bootstrap.next_action["type"] == "ask_user_to_update_or_confirm_project_docs"
    assert bootstrap.sync_result is None
    assert [action["tool"] for action in bootstrap.actions_taken] == ["inspect_project_docs"]

    sync = service.sync_project_docs(str(project), with_vectors=False)
    context = service.get_project_context(str(project), "FreshAcceptanceNeedle", tokens=1200, limit=3)

    assert sync.status == "success"
    assert context.answer_available is False
    assert context.reason == "partial_navigational_context"
    assert context.project_docs is not None
    assert context.project_docs.results
    assert "FreshAcceptanceNeedle" in context.project_docs.results[0].content


def test_get_project_context_can_return_project_and_dependency_context(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Routing\n\nUse AppRouter wrappers with GoRouter.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    monkeypatch.setattr(
        service,
        "get_docs",
        lambda *args, **kwargs: DocsResult(
            library_id="pub:go_router@14.8.1:api",
            library="go_router",
            version="14.8.1",
            topic=kwargs.get("topic"),
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at=None,
            results=[DocsChunk(title="GoRouter", content="Use GoRouter ShellRoute APIs.", source="https://pub.dev/documentation/go_router/14.8.1/", url="https://pub.dev/documentation/go_router/14.8.1/")],
            requested_version="project-version",
            resolved_version="14.8.1",
            version_source="lockfile_exact",
            docs_exactness="exact_version_url",
            docs_binding_source="pub_dartdoc_template",
            confidence="very_high",
        ),
    )

    result = service.get_project_context(str(project), "How should AppRouter use go_router?", tokens=1200, limit=3, allow_network=True)

    assert result.answer_available is True
    assert result.project_docs is not None
    assert result.dependency_docs is not None
    context_source_classes = {item["source_class"] for item in result.context_pack}
    assert {"project_doc", "dependency_doc"}.issubset(context_source_classes)
    assert not any(item.get("source_class") in {"source_evidence", "repo_map", "code_graph"} for item in result.context_pack)
    assert result.diagnostics["retrieval_routing"]["stages"]["source_evidence"]["status"] == "skipped"
    assert result.metrics["project_result_count"] >= 1
    assert result.metrics["dependency_result_count"] >= 1
    selected_classes = {item["source_class"] for item in result.trust_contract["sources"]["selected"]}
    assert selected_classes == {"project_file", "dependency_docs"}


def test_public_context_fails_closed_when_flutter_dependency_docs_are_missing(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path, fvmrc='{"flutter": "3.27.1"}')
    (project / "README.md").write_text(
        "# Dogfood Flutter app\n\nThe app uses GoRouter for navigation and Riverpod for state management.\n",
        encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.sync_project_docs(str(project), with_vectors=False)

    payload = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "How should GoRouter redirects and Riverpod providers be implemented?",
            "project_path": str(project),
        },
        service,
    )

    assert payload["status"] == "insufficient_evidence"
    assert "answer" not in payload
    assert payload["missing"]


def test_get_project_context_includes_snippet_object_when_metadata_has_code(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Routing\n\nUse AppRouter wrappers.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)
    monkeypatch.setattr(
        service,
        "get_docs",
        lambda *args, **kwargs: DocsResult(
            library_id="pub:go_router@14.8.1:api",
            library="go_router",
            version="14.8.1",
            topic=kwargs.get("topic"),
            refreshed=False,
            stale_before_refresh=False,
            warning=None,
            last_refreshed_at=None,
            results=[
                DocsChunk(
                    title="GoRouter example",
                    content="Example prose plus code.",
                    source="https://pub.dev/documentation/go_router/14.8.1/",
                    url="https://pub.dev/documentation/go_router/14.8.1/",
                    metadata={"code_snippets": [{"language": "dart", "code": "final router = GoRouter(routes: []);"}]},
                )
            ],
            requested_version="project-version",
            resolved_version="14.8.1",
            version_source="lockfile_exact",
            docs_exactness="exact_version_url",
            docs_binding_source="pub_dartdoc_template",
            confidence="very_high",
        ),
    )

    result = service.get_project_context(str(project), "GoRouter example", library="go_router", allow_network=True)

    dependency_item = next(item for item in result.context_pack if item["source_class"] == "dependency_doc")
    assert dependency_item["snippet"] == {
        "language": "dart",
        "code": "final router = GoRouter(routes: []);",
        "why_relevant": "code example extracted from matching GoRouter example section",
    }
    assert dependency_item["surrounding_context"] == "Example prose plus code."


def test_get_project_context_deps_only_skips_project_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service(tmp_path, monkeypatch)

    result = service.get_project_context(str(project), "go_router APIs", library="go_router", mode="deps-only")

    assert result.mode == "deps-only"
    assert result.project_docs is None
    assert any(item["reason_code"] == "project_docs_skipped" for item in result.trust_contract["sources"]["risky"])


def test_context_cli_outputs_json_and_explain(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    fake_config = DocmancerConfig()
    fake_result = ProjectContextResult(
        project_path=str(project),
        question="How?",
        trust_contract={"sources": {"selected": [], "rejected": [], "risky": []}, "warnings": [], "next_actions": []},
    )

    with patch("docmancer.cli.commands._load_config", return_value=fake_config), \
         patch("docmancer.docs.service.LibraryDocsService") as service_cls:
        service_cls.return_value.get_project_context.return_value = fake_result
        result = CliRunner().invoke(cli, ["context", str(project), "How?", "--format", "json", "--mode", "project-only"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["trust_contract"]["sources"]["selected"] == []
    service_cls.return_value.get_project_context.assert_called_once()
    assert service_cls.return_value.get_project_context.call_args.kwargs["mode"] == "project-only"


def test_context_cli_explain_outputs_human_readable_trust_contract(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    fake_config = DocmancerConfig()
    fake_result = ProjectContextResult(
        project_path=str(project),
        question="How?",
        trust_contract={
            "selected_sources": [{"source_class": "project_file", "path": "docs/architecture.md", "why_selected": "matched local rule", "freshness": "current"}],
            "rejected_sources": [{"source_class": "dependency_doc", "library": "go_router latest", "reason": "wrong_version_risk"}],
            "risky_sources": [],
            "warnings": [],
            "next_actions": [],
        },
    )

    with patch("docmancer.cli.commands._load_config", return_value=fake_config), \
         patch("docmancer.docs.service.LibraryDocsService") as service_cls:
        service_cls.return_value.get_project_context.return_value = fake_result
        result = CliRunner().invoke(cli, ["context", str(project), "How?", "--explain"])

    assert result.exit_code == 0, result.output
    assert "Trusted context for: How?" in result.output
    assert "[project_file] docs/architecture.md" in result.output
    assert "Rejected / risky:" in result.output
    assert "wrong_version_risk" in result.output


def test_get_project_docs_returns_sync_next_action_when_candidates_not_indexed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nProject docs exist but are not indexed.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.get_project_docs(str(project), "Architecture", tokens=1200, limit=3)

    assert result.status == "not_indexed"
    assert result.answer_available is False
    assert result.reason == "project_docs_not_indexed"
    assert result.reason_code == "project_docs_found_not_indexed"
    assert result.next_action == {"type": "sync_project_docs", "tool": "sync_project_docs"}
    assert result.requires_confirmation is False
    assert result.arguments_patch == {"project_path": str(project.resolve()), "with_vectors": False}
    assert result.results == []
    assert result.candidate_sources[0]["path"] == "README.md"
    assert result.next_actions[0]["tool"] == "sync_project_docs"
    assert result.next_actions[0]["arguments_patch"] == {"project_path": str(project.resolve()), "with_vectors": False}


def test_get_project_docs_distinguishes_indexed_no_results_from_not_indexed(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Architecture\n\nKnown project docs topic.", encoding="utf-8")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.ingest_project_docs(str(project), with_vectors=False)

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
