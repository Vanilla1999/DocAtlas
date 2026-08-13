from __future__ import annotations

import json
from dataclasses import asdict

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.model_visible_projection import project_docs_answer
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def _named_document_service(tmp_path, monkeypatch, paths: list[str]) -> tuple[LibraryDocsService, str]:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    for path in paths:
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {target.stem}\n\nMarker for {path}.\n", encoding="utf-8")
    catalog = "schema_version: 1\ndocuments:\n" + "".join(
            f"  - path: {path}\n    role: other\n    scope: project\n"
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
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
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
            "mode": "project",
            "delivery_strategy": "bounded_direct",
            "packet_tokens": 1500,
        },
        service,
    )
    direct, _ = project_docs_answer(
        question=question,
        retrieval=asdict(unified),
        canonical_selection=unified.selection_decision,
        max_tokens=800,
    )

    assert sync.status == "success"
    assert sync.diagnostics["vector_sync"]["status"] == "not_requested"
    assert unified.answer_supported is True, unified
    assert all(candidate.identity_kind == "stable_child" for candidate in unified.selection_decision.selected_candidates)
    assert all(not candidate.stable_id.startswith("legacy:") for candidate in unified.selection_decision.selected_candidates)
    assert all(candidate.parent_logical_id for candidate in unified.selection_decision.selected_candidates)
    assert all(candidate.char_start is not None and candidate.line_start is not None for candidate in unified.selection_decision.selected_candidates)
    qualifier_bindings = {
        assignment.qualifiers
        for assignment in unified.selection_decision.assignments
        if assignment.qualifiers
    }
    assert ("confirmation_required", "proposed") in qualifier_bindings
    assert ("negated", "not_implemented") in qualifier_bindings
    assert direct["status"] == "ok", json.dumps(direct, indent=2, default=str)
    assert result["status"] == "ok", json.dumps(result, indent=2, default=str)
    assert result["answer_supported"] is True
    assert result["answer_available"] is True
    assert result["context_available"] is True
    assert {source["path_or_url"] for source in result["sources"]} == {plan_path}
    assert "ARCHITECTURE.md" not in {
        source["path_or_url"] for source in result["sources"]
    }
    for text in (
        "ForkSource uses upstream",
        "Policy72Hours is proposed",
        "confirmation is required",
        "LocalizationError is not implemented",
        "DependencyPin is pinned to the reviewed revision",
    ):
        assert text in result["answer"]
    assert result["answer_evidence_ids"] == result["selected_evidence_ids"]
    assert result["answer_evidence_ids"] == [
        source["evidence_id"] for source in result["sources"]
    ]


def test_named_document_single_fact_does_not_expose_unrequested_document_content(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
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
    unified = service.get_docs_context(
        question,
        project_path=str(project),
        mode="project",
        prepare_project_docs=False,
    )

    assert unified.answer_supported is True, unified
    selected_text = "\n".join(
        candidate.projected_text for candidate in unified.selection_decision.selected_candidates
    )
    assert "ForkSource uses upstream" in selected_text
    assert "UnrequestedSecret" not in selected_text


def test_public_named_document_unknown_locator_fails_closed(tmp_path, monkeypatch):
    service, project = _named_document_service(tmp_path, monkeypatch, ["docs/PLAN.md"])

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "In docs/MISSING.md, summarize the marker.",
            "project_path": project,
            "mode": "project",
            "output_mode": "full",
        },
        service,
    )

    assert result["support_status"] == "insufficient_evidence"
    assert result["reason_code"] == "required_evidence_missing"
    assert result["lanes"]["project"]["reason_code"] == "document_not_indexed"
    assert result["answer_available"] is False
    assert result["context_available"] is False
    assert result["context_pack"] == []


def test_public_named_document_ambiguous_basename_fails_closed(tmp_path, monkeypatch):
    service, project = _named_document_service(
        tmp_path, monkeypatch, ["docs/one/PLAN.md", "docs/two/PLAN.md"]
    )

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "In PLAN.md, summarize the marker.",
            "project_path": project,
            "mode": "project",
            "output_mode": "full",
        },
        service,
    )

    assert result["support_status"] == "insufficient_evidence"
    assert result["reason_code"] == "required_evidence_missing"
    assert result["lanes"]["project"]["reason_code"] == "ambiguous_document_locator"
    assert result["answer_available"] is False
    assert result["context_available"] is False
    assert result["context_pack"] == []
