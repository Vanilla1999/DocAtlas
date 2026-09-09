from __future__ import annotations

import pytest

from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


CASES = (
    ("When should an agent use get_docs_context?", "docs_mcp_tool_policy"),
    ("When is an agent allowed to call prepare_docs?", "docs_mcp_tool_policy"),
    ("What kinds of requests should use docs_status, and when must it not be used?", "docs_mcp_tool_policy"),
    ("What does fail-closed behavior mean in the DocAtlas documentation workflow?", "fail_closed_workflow"),
    ("What is the difference between docs_answer, docs_context, patch_context, and insufficient_evidence?", "response_contract"),
    ("Which repository files are the source of truth, and which DocAtlas storage artifacts are only derived indexes?", "source_authority"),
    ("What systems does DocAtlas explicitly not replace?", "product_boundaries"),
    ("How does DocAtlas determine whether a dependency version is exact, declared-only, or unbound?", "dependency_version_binding"),
    ("What are the responsibilities of docmancer/docs/application and docmancer/docs/domain in this repository?", "module_responsibilities"),
    ("What claims about DocAtlas are not currently demonstrated according to the product brief?", "product_claims"),
)


@pytest.mark.parametrize(("question", "expected_facet"), CASES)
def test_direct_questions_have_relation_specific_retrieval_facets(question: str, expected_facet: str):
    facets = {alias.intent_id for alias in build_project_retrieval_aliases(question)}
    assert expected_facet in facets


@pytest.mark.parametrize(
    ("question", "forbidden_facet"),
    [
        ("get_docs_context returned an error; how should I troubleshoot it?", "fail_closed_workflow"),
        ("What claims are accepted by the HTTP API contract?", "product_claims"),
        ("Which database file stores the local cache?", "source_authority"),
        ("Which version of Python should I install?", "dependency_version_binding"),
        ("Which modules import pathlib?", "module_responsibilities"),
    ],
)
def test_relation_specific_facets_do_not_capture_neighboring_questions(question: str, forbidden_facet: str):
    facets = {alias.intent_id for alias in build_project_retrieval_aliases(question)}
    assert forbidden_facet not in facets
