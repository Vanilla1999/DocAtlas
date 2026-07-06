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


def test_weighted_relevance_gate_single_low_weight_does_not_pass():
    question = "nonexistent zzzxq foobar"
    from docmancer.docs.application.project_context_service import _query_relevance_gate

    gate = _query_relevance_gate(
        question=question,
        intent=_intent(),
        context_pack=[
            {"source_class": "project_doc", "path": "docs/oidc.md", "title": "OIDC", "content": "protocol overview"},
        ],
        relevance_terms=["nonexistent", "zzzxq", "foobar"],
    )
    assert not gate["passed"]
    assert gate["reason"] == "insufficient_weighted_relevance"
    assert "matched_details" in gate
    assert "weighted_score" in gate


def test_weighted_relevance_gate_strong_content_match_passes():
    question = "authentication protocol oidc token"
    from docmancer.docs.application.project_context_service import _query_relevance_gate

    gate = _query_relevance_gate(
        question=question,
        intent=_intent(),
        context_pack=[
            {
                "source_class": "project_doc",
                "path": "docs/oidc.md",
                "title": "OIDC protocol",
                "content": "authentication protocol oidc token overview with detailed explanation of flows",
            },
        ],
        relevance_terms=["authentication", "protocol", "oidc"],
    )
    assert gate["passed"]
    assert gate["reason"] == "weighted_relevance_sufficient"


def test_weighted_relevance_gate_symbol_match_passes():
    question = "PermissionService grant authority"
    from docmancer.docs.application.project_context_service import _query_relevance_gate

    gate = _query_relevance_gate(
        question=question,
        intent=_intent(),
        context_pack=[
            {
                "source_class": "source_evidence",
                "evidence_class": "source_snippet",
                "path": "lib/permission_service.dart",
                "title": "PermissionService",
                "content": "class PermissionService implements GrantAuthority",
            },
        ],
        relevance_terms=["PermissionService", "grant authority"],
    )
    assert gate["passed"]
    assert gate["reason"] == "weighted_relevance_sufficient"


def test_weighted_relevance_gate_dependency_match_passes():
    question = "go_router navigate screen"
    from docmancer.docs.application.project_context_service import _query_relevance_gate

    gate = _query_relevance_gate(
        question=question,
        intent=_intent(),
        context_pack=[
            {
                "source_class": "dependency_doc",
                "path": "pub/go_router",
                "title": "GoRouter navigate",
                "content": "go_router provides navigate method for screen routing with detailed navigation patterns",
            },
        ],
        relevance_terms=["go_router", "navigate"],
    )
    assert gate["passed"]
    assert gate["reason"] == "weighted_relevance_sufficient"


def test_answer_type_not_exact_without_strong_evidence():
    result = evaluate_project_answer_completeness(
        question="How to use the widget tree?",
        context_pack=[
            {
                "source_class": "project_doc",
                "source_type": "readme",
                "path": "README.md",
                "title": "Project Overview",
                "authority": "supporting",
                "content": "the widget tree is defined by the Flutter framework.",
            }
        ],
        answer_available=True,
        intent=_intent(),
    )
    assert result["answer_type"] != "exact"
    assert "missing_strong_evidence_for_exact" in result["answer_completeness"]["reason_codes"] or "high_signal_query_terms_missing_from_context" in result["answer_completeness"]["reason_codes"]


def test_answer_type_exact_only_with_strong_evidence():
    result = evaluate_project_answer_completeness(
        question="PermissionService grant access",
        context_pack=[
            {
                "source_class": "source_evidence",
                "evidence_class": "source_snippet",
                "path": "lib/permission_service.dart",
                "title": "PermissionService",
                "content": "class PermissionService implements GrantAccessAuthority",
            }
        ],
        answer_available=True,
        intent=_intent(),
    )
    assert result["answer_type"] == "exact"
