from __future__ import annotations

from types import SimpleNamespace

from docmancer.docs.application.project_context_service import project_context_pack
from docmancer.docs.domain.answer_completeness import (
    evaluate_project_answer_completeness,
    extract_query_relevance_terms,
)
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult


def _intent(**kwargs):
    defaults = {
        "name": "general",
        "broad": False,
        "wants_architecture": False,
        "wants_how_to": False,
        "wants_code_symbols": False,
        "wants_release_history": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_bogus_query_gets_high_signal_relevance_terms():
    terms = extract_query_relevance_terms(
        "zzzxq nonexistent foobar protocol imaginary feature",
        intent=_intent(),
    )

    assert "zzzxq" in terms
    assert "nonexistent" in terms
    assert "foobar" in terms
    assert "imaginary" in terms
    assert "protocol" not in terms
    assert "feature" not in terms


def test_bogus_query_does_not_become_exact_when_only_generic_docs_match():
    result = evaluate_project_answer_completeness(
        question="zzzxq nonexistent foobar protocol imaginary feature",
        context_pack=[
            {
                "source_class": "project_doc",
                "source_type": "docs",
                "path": "docs/oidc.md",
                "title": "OIDC protocol",
                "content": "OpenID Connect protocol overview.",
            }
        ],
        answer_available=True,
        intent=_intent(),
    )

    completeness = result["answer_completeness"]
    assert result["answer_type"] != "exact"
    assert completeness["coverage_score"] < 1.0
    assert "high_signal_query_terms_missing_from_context" in completeness["reason_codes"]


def test_broad_architecture_query_does_not_require_random_word_gate():
    terms = extract_query_relevance_terms(
        "How is this project structured and where should UI changes be made?",
        intent=_intent(name="architecture", broad=True, wants_architecture=True),
    )

    assert terms == []


def test_context_pack_excludes_low_trust_artifacts_unless_requested():
    artifact_path = "docs/research/docatlas-dogfood-v4/nbo/patch-review/review_summary.md"
    project_docs = ProjectDocsResult(
        project_path="/repo",
        query="How should agents use the Docmancer MCP workflow?",
        results=[
            ProjectDocsChunk(
                title="Dogfood output",
                content="Docmancer MCP Workflow architecture conventions project context.",
                source=f"/repo/{artifact_path}",
                url=None,
                path=artifact_path,
            ),
            ProjectDocsChunk(
                title="Architecture",
                content="Docmancer MCP Workflow is defined by authoritative architecture docs.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            ),
        ],
    )

    pack = project_context_pack(
        question="How should agents use the Docmancer MCP workflow?",
        project_docs=project_docs,
        dependency_docs=None,
    )

    assert [item["path"] for item in pack] == ["ARCHITECTURE.md"]

    artifact_pack = project_context_pack(
        question="Inspect dogfood research artifact output",
        project_docs=project_docs,
        dependency_docs=None,
    )

    assert artifact_path in [item["path"] for item in artifact_pack]
