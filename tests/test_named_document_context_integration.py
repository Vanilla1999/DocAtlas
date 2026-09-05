from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def _named_document_service(
    tmp_path, monkeypatch, paths: list[str], contents: dict[str, str] | None = None,
    roles: dict[str, str] | None = None,
) -> tuple[LibraryDocsService, str]:
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    for path in paths:
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (contents or {}).get(path, f"# {target.stem}\n\nMarker for {path}.\n"),
            encoding="utf-8",
        )
    catalog = "schema_version: 1\ndocuments:\n" + "".join(
            f"  - path: {path}\n    role: {(roles or {}).get(path, 'other')}\n    scope: project\n"
        "    description: Named document fixture.\n    authority: source_of_truth\n"
        "    status: active\n    impact: track\n"
        for path in paths
    )
    (project / "docatlas.project-docs.yaml").write_text(catalog, encoding="utf-8")
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    return service, str(project)


def test_named_plan_is_scoped_complete_and_visible_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    plan_path = "docs/IOS_TRUSTED_TIME_PLAN.md"
    (project / plan_path).write_text(
        """# iOS Trusted Time Plan

## Source and policy
ForkSource uses upstream.
Policy72Hours is proposed; confirmation is required.

## Validation and dependencies
LocalizationError is not implemented.
DependencyPin is pinned to the reviewed revision.
""",
        encoding="utf-8",
    )
    (project / "ARCHITECTURE.md").write_text(
        """# Architecture

Architecture conventions mention ForkSource, Policy72Hours, LocalizationError,
TimestampPolicy, and DependencyPin, but do not define the trusted-time plan.
""",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        """schema_version: 1
documents:
  - path: docs/IOS_TRUSTED_TIME_PLAN.md
    role: roadmap
    scope: project
    description: Proposed trusted-time implementation plan.
    authority: supporting
    status: active
    impact: track
  - path: ARCHITECTURE.md
    role: project_architecture
    scope: project
    description: Current project architecture.
    authority: source_of_truth
    status: active
    impact: track
""",
        encoding="utf-8",
    )
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )

    sync = service.sync_project_docs(str(project), with_vectors=False)
    question = (
        f"In {plan_path}, summarize ForkSource, Policy72Hours, LocalizationError, "
        "and DependencyPin."
    )
    unified = service.get_docs_context(
        question,
        project_path=str(project),
        mode="project",
        prepare_project_docs=False,
    )
    result = call_docs_tool_payload(
        "get_docs_context",
        {
                "question": question,
                "project_path": str(project),
        },
        service,
    )
    assert sync.status == "success"
    assert sync.diagnostics["vector_sync"]["status"] == "not_requested"
    assert result["status"] == "ok", json.dumps({
        "public": result,
        "unified": asdict(unified),
    }, indent=2, default=str)
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["context_available"] is True
    assert {source["path_or_url"] for source in result["sources"]} == {plan_path}
    assert "ARCHITECTURE.md" not in {
        source["path_or_url"] for source in result["sources"]
    }
    context = "\n".join(source["snippet"] for source in result["sources"])
    assert "ForkSource uses upstream" in context
    assert "LocalizationError is not implemented" in context


def test_named_document_single_fact_does_not_expose_unrequested_document_content(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    plan_path = "docs/PLAN.md"
    (project / plan_path).write_text(
        "# Plan\n\n## Fork source\nForkSource uses upstream.\n\n"
        "## Internal note\nUnrequestedSecret remains internal.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\ndocuments:\n  - path: docs/PLAN.md\n    role: roadmap\n"
        "    scope: project\n    description: Plan.\n    authority: source_of_truth\n"
        "    status: active\n    impact: track\n",
        encoding="utf-8",
    )
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    service = LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    question = f"In {plan_path}, summarize ForkSource."
    result = call_docs_tool_payload(
        "get_docs_context",
        {"question": question, "project_path": str(project)},
        service,
    )

    assert result["status"] == "ok", result
    assert result["kind"] == "docs_context"
    context = "\n".join(source["snippet"] for source in result["sources"])
    assert "ForkSource uses upstream" in context
    assert "UnrequestedSecret" not in context


def test_public_named_document_unknown_locator_fails_closed(tmp_path, monkeypatch):
    service, project = _named_document_service(tmp_path, monkeypatch, ["docs/PLAN.md"])

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "In docs/MISSING.md, summarize the marker.",
            "project_path": project,
        },
        service,
    )

    assert result["support_status"] == "insufficient_evidence"
    assert result["status"] == "insufficient_evidence"
    assert result["kind"] == "docs_context"
    assert result["answer_available"] is False
    assert result["context_available"] is False
    assert "context_pack" not in result


def test_public_project_answer_requires_all_semantic_facets(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": "# Status\n\ndocs_status reports index freshness.\n"},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What does docs_status report and when should it be used?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["context_available"] is True


def test_public_project_answer_accepts_all_semantic_facets(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": (
            "# Status\n\n"
            "docs_status reports index freshness and should be used for health checks.\n"
        )},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What does docs_status report and when should it be used?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["context_available"] is True


def test_public_project_answer_heading_only_is_not_factual_proof(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": "# docs_status\n"},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What does docs_status report and when should it be used?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "insufficient_evidence"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "insufficient_evidence"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False


def test_public_project_answer_negated_facet_is_not_factual_proof(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": (
            "# Status\n\n"
            "docs_status does not report index freshness and should not be used for health checks.\n"
        )},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What does docs_status report and when should it be used?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False


def test_project_context_remains_available_when_authority_facet_is_missing(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": "# Retrieval\n\nExact-term retrieval improves recall.\n"},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "How does exact-term recall improve without widening authority?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["context_available"] is True


def test_public_project_answer_accepts_recall_with_authority_invariant(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": (
            "# Retrieval\n\n"
            "Exact-term retrieval improves recall while authority scope remains unchanged.\n"
        )},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "How does exact-term recall improve without widening authority?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["context_available"] is True


def test_public_project_answer_requires_comparison_relation(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": "# Scheduling\n\nasync and launch are available APIs.\n"},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Compare async with launch",
            "project_path": project,
        },
        service,
    )

    assert result["support_status"] == "insufficient_evidence"
    assert result["status"] == "insufficient_evidence"
    assert result["answer_available"] is False


def test_public_project_answer_accepts_comparison_relation(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": (
            "# Scheduling\n\n"
            "async returns a result, whereas launch schedules background work.\n"
        )},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Compare async with launch",
            "project_path": project,
        },
        service,
    )

    assert result["support_status"] == "insufficient_evidence"
    assert result["answer_supported"] is False


def test_public_project_answer_supports_russian_behavior_and_usage(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": (
            "# Статус\n\n"
            "docs_status сообщает свежесть индекса и используется для проверки здоровья.\n"
        )},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Что сообщает docs_status и когда его использовать?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False


def test_public_project_answer_rejects_incomplete_russian_usage(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["ARCHITECTURE.md"],
        {"ARCHITECTURE.md": "# Статус\n\ndocs_status сообщает свежесть индекса.\n"},
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Что сообщает docs_status и когда его использовать?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False


def test_public_named_document_ambiguous_basename_fails_closed(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path, monkeypatch, ["docs/one/PLAN.md", "docs/two/PLAN.md"]
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "In PLAN.md, summarize the marker.",
            "project_path": project,
        },
        service,
    )

    assert result["support_status"] == "insufficient_evidence"
    assert result["status"] == "insufficient_evidence"
    assert result["kind"] == "docs_context"
    assert result["answer_available"] is False
    assert result["context_available"] is False
    assert "context_pack" not in result


@pytest.mark.parametrize(
    ("question", "expected_path", "expected_text"),
    [
        (
            "What public MCP tools does DocAtlas expose?",
            "docs/mcp-docs-server.md",
            "get_docs_context",
        ),
        (
            "How do I configure DocAtlas in OpenCode?",
            "README.md",
            "opencode.json",
        ),
        (
            "How are external dependency docs prepared for a project?",
            "docs/project-docs-mcp-workflow.md",
            "prefetch_project_dependency_docs",
        ),
        (
            "What output budgets apply to Docs MCP responses?",
            "docs/mcp-docs-server.md",
            "800 tokens and three sources",
        ),
    ],
)
def test_real_sqlite_newcomer_topics_reach_expected_project_docs(
    tmp_path, monkeypatch, question, expected_path, expected_text,
):
    contents = {
        "README.md": (
            "# OpenCode setup\n\nConfigure DocAtlas in `opencode.json` and start the Docs MCP server.\n"
        ),
        "docs/mcp-docs-server.md": (
            "# DocAtlas Docs MCP server\n\nThe public tools are `get_docs_context`, `prepare_docs`, and "
            "`docs_status`. Responses are bounded to 800 tokens and three sources.\n"
        ),
        "docs/project-docs-mcp-workflow.md": (
            "# Dependency documentation\n\nPrepare project-bound external dependency docs with "
            "`prefetch_project_dependency_docs`.\n"
        ),
        "wiki/Configuration.md": (
            "# Generic configuration\n\nGeneral configuration concepts and defaults.\n"
        ),
    }
    service, project = _named_document_service(
        tmp_path, monkeypatch, list(contents), contents,
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {"question": question, "project_path": project},
        service,
    )

    assert result["status"] == "ok", result
    assert result["kind"] == "docs_context"
    assert result["answer_supported"] is False
    paths = [source["path_or_url"] for source in result["sources"]]
    assert expected_path in paths[:3]
    assert expected_text in str(result)


def test_real_sqlite_compound_onboarding_maximizes_host_lookup_coverage(
    tmp_path, monkeypatch,
):
    contents = {
        "docs/product.md": "# Product\n\nPurposeword newcomerword explains the product goal.\n",
        "docs/architecture.md": "# Architecture\n\nBoundaryword runtimeword explains architecture.\n",
        "docs/data-flow.md": "# Data flow\n\nFlowword pipelineword explains request flow.\n",
        "docs/development.md": "# Development\n\nBootstrapword localword explains local setup.\n",
        "docs/testing.md": "# Testing\n\nTestword pytestword explains test commands.\n",
    }
    service, project = _named_document_service(
        tmp_path, monkeypatch, list(contents), contents,
    )
    lookup_queries = [
        "purposeword newcomerword",
        "boundaryword runtimeword",
        "flowword pipelineword",
        "bootstrapword localword",
        "testword pytestword",
    ]

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "I just joined this project. Help me understand it.",
            "lookup_queries": lookup_queries,
            "project_path": project,
            "scope": "project",
        },
        service,
    )

    assert result["status"] == "ok", result
    assert result["kind"] == "docs_context"
    assert result["support_status"] == "retrieval_only"
    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["edit_ready"] is False
    assert len(result["sources"]) == 3
    lookup_ids = {f"query-lookup-{index}" for index in range(1, 6)}
    covered_lookup_ids = set(result["covered_query_ids"]) & lookup_ids
    missing_lookup_ids = set(result["missing_query_ids"]) & lookup_ids
    assert len(covered_lookup_ids) == 3
    assert len(missing_lookup_ids) == 2
    assert covered_lookup_ids | missing_lookup_ids == lookup_ids
    assert "query-original" in result["missing_query_ids"]
    assert not any(
        query_id.startswith("query-intent-")
        for query_id in result["missing_query_ids"]
    )
    assert result["estimated_tokens"] <= 800


def test_real_sqlite_audited_russian_alias_covers_original_question(
    tmp_path, monkeypatch,
):
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        ["README.md"],
        {"README.md": (
            "# Local installation setup verification\n\n"
            "Install DocAtlas locally and run command-line help to verify the setup.\n"
        )},
        {"README.md": "overview"},
    )
    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Как установить DocAtlas локально и проверить, что он работает?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok", result
    assert result["sources"][0]["path_or_url"] == "README.md"
    assert "query-original" in result["covered_query_ids"]
    assert result["answer_supported"] is False


def test_real_sqlite_docs_mcp_intent_excludes_packs_and_adrs(
    tmp_path, monkeypatch,
):
    contents = {
        "docs/mcp-docs-server.md": (
            "# Docs MCP server workflow\n\n"
            "Use get_docs_context, prepare_docs, and docs_status for documentation context.\n"
        ),
        "docs/mcp-packs.md": (
            "# MCP pack commands\n\nUse install-pack and packs-serve for API action packs.\n"
        ),
        "docs/adr/mcp.md": "# MCP boundary\n\nHistorical MCP transport decision.\n",
    }
    service, project = _named_document_service(
        tmp_path,
        monkeypatch,
        list(contents),
        contents,
        {
            "docs/mcp-docs-server.md": "api_contract",
            "docs/mcp-packs.md": "api_contract",
            "docs/adr/mcp.md": "project_architecture",
        },
    )
    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Как устроен полный процесс работы Docs MCP?",
            "project_path": project,
        },
        service,
    )

    assert result["status"] == "ok", result
    paths = {source["path_or_url"] for source in result["sources"]}
    visible = "\n".join(source["snippet"] for source in result["sources"])
    assert "docs/mcp-docs-server.md" in paths
    assert "docs/mcp-packs.md" not in paths
    assert "docs/adr/mcp.md" not in paths
    assert "packs-serve" not in visible
