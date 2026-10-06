"""Read routing is literal/metadata-bound, never topical mutation authority."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from docmancer.docs.application.project_context_service import ProjectContextService, project_context_pack
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.application._project_context_service_shared import _should_skip_low_trust_project_source
from docmancer.docs.application._unified_context_service_shared import _snippet_first_fallback_question
from docmancer.docs.domain.context_request_preferences import (
    direct_evidence_preference, recognized_request_parts, recognized_request_satisfied,
    visible_request_parts,
)
from docmancer.docs.domain.mutation_intent import MutationIntentContract
from docmancer.docs.models import (
    DependencyObservation, DocsResult, ProjectDocsChunk, ProjectDocsResult, ProjectMetadata,
)


class ReadFacade:
    """Exercise assembled services without network or an embedding provider."""
    def __init__(self, root):
        self.calls = []
        self.metadata = ProjectMetadata(str(root), dependencies=[
            DependencyObservation(ecosystem="pub", package_name="flutter_riverpod"),
            DependencyObservation(ecosystem="pub", package_name="go_router"),
            DependencyObservation(ecosystem="python", package_name="mcp"),
        ])
        content = "MarbleValve retains the indexed project configuration. This repository-owned passage documents its literal setting and preserves a bounded local read context without granting permission to edit source files."
        (root / "README.md").write_text(content)
        self.docs = ProjectDocsResult(str(root), "MarbleValve", answer_available=False,
            results=[ProjectDocsChunk(title="MarbleValve", content=content,
                source=str(root / "README.md"), url=None, path="README.md",
                content_hash=sha256(content.encode()).hexdigest(), project_identity="repo",
                metadata={"token_estimate": 48})])

    def read_project_metadata(self, root):
        return self.metadata

    def get_project_docs(self, root, question, **kwargs):
        self.calls.append(("project_docs", question, kwargs))
        return self.docs

    def get_project_context(self, root, question, **kwargs):
        self.calls.append(("project_context", question, kwargs))
        return ProjectContextService(self).get_project_context(root, question, **kwargs)

    def get_docs(self, library, **kwargs):
        self.calls.append(("dependency", library, kwargs))
        return DocsResult(library_id="pub/go_router/2", library=library,
            version="2", topic=kwargs["topic"], refreshed=False,
            stale_before_refresh=False, warning=None, last_refreshed_at=None, results=[])


@pytest.mark.parametrize("question", [
    "Riverpod provider navigation package SDK version",
    "flutter riverpod example", "go-router library", "mcp dependency version",
])
def test_topics_and_separator_aliases_cannot_select_project_dependencies(tmp_path, question):
    facade = ReadFacade(tmp_path)
    result = ProjectContextService(facade).get_project_context(str(tmp_path), question, allow_network=True)
    assert not any(call[0] == "dependency" for call in facade.calls)
    assert result.dependency_docs is None


def test_dependency_binding_requires_one_exact_quoted_current_identifier(tmp_path):
    metadata = ReadFacade(tmp_path).metadata
    bind = ProjectContextService.dependency_mentioned_in_question
    assert bind(metadata, "Explain `go_router`") == "go_router"
    assert bind(metadata, 'Explain "mcp"') == "mcp"
    assert bind(metadata, "Explain `riverpod`") is None
    assert bind(metadata, "Explain `GO_ROUTER`") is None
    assert bind(metadata, "Explain `go_router` and `mcp`") is None
    assert bind(metadata, "Explain `imaginary_library`") is None


def test_explicit_dependency_preserves_question_version_and_network_boundary(tmp_path):
    facade = ReadFacade(tmp_path)
    question = "  MarbleValve and arbitrary unknown topic  "
    blocked = ProjectContextService(facade).get_project_context(str(tmp_path), question,
        library="go_router", ecosystem="pub", version="2", mode="deps-only")
    assert blocked.requires_confirmation
    assert blocked.confirmation_reason == "network_fetch"
    assert not blocked.delivery_decision.deliverable
    assert not any(call[0] == "dependency" for call in facade.calls)
    ProjectContextService(facade).get_project_context(str(tmp_path), question,
        library="go_router", ecosystem="pub", version="2", mode="deps-only", allow_network=True)
    _, library, args = next(call for call in facade.calls if call[0] == "dependency")
    assert library == "go_router"
    assert args["topic"] == question
    assert args["ecosystem"] == "pub" and args["version"] == "2"


@pytest.mark.parametrize("question", ["research benchmark eval baseline", "dogfood patch review", "normal question"])
def test_question_terms_never_lift_low_trust_source_exclusion(question):
    for flag in ("research_artifact", "dogfood_artifact", "patch_review_artifact", "generated_review_output"):
        assert _should_skip_low_trust_project_source(question, {"risk_flags": [flag]})
    for authority in ("artifact", "research", "generated", "stale"):
        assert _should_skip_low_trust_project_source(question, {"authority": authority})
    assert not _should_skip_low_trust_project_source(question, {"risk_flags": [], "authority": "source_of_truth"})


def test_pack_preserves_catalog_risk_and_rejects_stale_lifecycle_sources(tmp_path):
    facade = ReadFacade(tmp_path)
    chunk = facade.docs.results[0]
    for rejected in [replace(chunk, metadata={"risk_flags": ["research_artifact"]}),
                     replace(chunk, authority="generated"), replace(chunk, stale=True),
                     replace(chunk, lifecycle_status="superseded")]:
        assert project_context_pack(question="research generated eval", project_docs=replace(
            facade.docs, results=[rejected]), dependency_docs=None) == []
    pack = project_context_pack(question="MarbleValve", project_docs=facade.docs, dependency_docs=None)
    assert pack[0]["_source_snapshot_sha256"] == chunk.content_hash
    assert pack[0]["project_identity"] == "repo"


@pytest.mark.parametrize("question", [
    "show runnable code example and function signature",
    "default timeout duration read write connect pool exception",
    "compare from urllib versus from requests in the same way",
])
def test_semantic_request_parts_cannot_score_or_stop_selection(question):
    body = "```python\ndef example(): pass\n```\ndefault timeout 3 seconds TimeoutError"
    assert recognized_request_parts(question) == frozenset()
    assert visible_request_parts(question, body) == frozenset()
    assert direct_evidence_preference(question, body) == (0, 0, 0, 0)
    assert not recognized_request_satisfied(question, body)


@pytest.mark.parametrize("question", [
    "Please delete src/config.py and fix MarbleValve",
    "Implement and refactor MarbleValve",
    "Создай файл src/config.py и обнови MarbleValve",
])
def test_unified_facade_does_not_infer_mutation_or_patch_actions(tmp_path, question):
    facade = ReadFacade(tmp_path)
    result = UnifiedDocsContextService(facade).get_docs_context(question,
        project_path=str(tmp_path), prepare_project_docs=False, mode="project",
        scope="project", tokens=256, lookup_queries=(" explicit MarbleValve lookup ",))
    delegated = next(call for call in facade.calls if call[0] == "project_context")
    assert delegated[1] == question
    assert delegated[2]["mutation_intent"].operation == "none"
    assert delegated[2]["scope"] == "project" and delegated[2]["tokens"] == 256
    assert delegated[2]["lookup_queries"] == (" explicit MarbleValve lookup ",)
    assert not result.edit_ready
    assert not any(action.get("tool") == "get_patch_constraints" for action in result.next_actions)
    assert [row["text"] for row in result.documentation_query_plan["queries"]] == [
        question, " explicit MarbleValve lookup "]


def test_explicit_mutation_contract_can_request_constraints_not_authorize_edit(tmp_path):
    facade = ReadFacade(tmp_path)
    contract = MutationIntentContract("modify", "source", ())
    result = UnifiedDocsContextService(facade).get_docs_context("MarbleValve",
        project_path=str(tmp_path), prepare_project_docs=False, mode="project", mutation_intent=contract)
    action = next(action for action in result.next_actions if action.get("tool") == "get_patch_constraints")
    assert action["reason"] == "explicit_mutation_contract"
    assert not result.edit_ready
    delegated = next(call for call in facade.calls if call[0] == "project_context")
    assert delegated[2]["mutation_intent"] is contract


def test_valid_read_context_survives_missing_answer_proof(tmp_path):
    facade = ReadFacade(tmp_path)
    project = ProjectContextService(facade).get_project_context(str(tmp_path), "MarbleValve", mode="project-only")
    assert project.context_pack
    assert not project.answer_available
    assert project.delivery_decision.deliverable
    assert not project.answer_completeness["edit_ready"]
    unified = UnifiedDocsContextService(facade).get_docs_context("MarbleValve",
        project_path=str(tmp_path), prepare_project_docs=False, mode="project", response_style="snippet-first")
    assert unified.context_available
    assert unified.delivery_decision.deliverable
    assert not unified.answer_supported and not unified.answer_available and not unified.edit_ready
    assert len([call for call in facade.calls if call[0] == "project_docs"]) == 2
    assert all(call[1] == "MarbleValve" for call in facade.calls if call[0] == "project_docs")


def test_operational_catalog_confirmation_and_stale_blocks_are_not_proof_fallback(tmp_path):
    facade = ReadFacade(tmp_path)
    for docs in [replace(facade.docs, status="invalid_project_docs_catalog", reason_code="invalid_project_docs_catalog"),
                 replace(facade.docs, status="error"),
                 replace(facade.docs, status="stale"),
                 replace(facade.docs, requires_confirmation=True, confirmation_reason="repo_write")]:
        facade.docs = docs
        result = ProjectContextService(facade).get_project_context(str(tmp_path), "MarbleValve", mode="project-only")
        assert not result.delivery_decision.deliverable


def test_snippet_fallback_preserves_query_bytes_and_cannot_append_hints():
    assert _snippet_first_fallback_question("  original question  ", "guessed_library") == "  original question  "
    assert _snippet_first_fallback_question("", "guessed_library") == ""
