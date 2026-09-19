from pathlib import Path

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases
from docmancer.docs.service import LibraryDocsService
from eval.project_context_quality.capture_public_context import capture_public_call


@pytest.mark.parametrize("question", [
    "If my question compares two things, should I split it into separate documentation searches before seeing the first result?",
    "Should I split a comparison into separate search requests?",
    "How should I split a payment between two accounts?",
    "Нужно ли разбивать вопрос на отдельные поисковые запросы?",
])
def test_ambiguous_split_does_not_invent_indexing_subject(question):
    aliases = build_project_retrieval_aliases(question)
    assert all(a.intent_id != "index_chunking" for a in aliases)


@pytest.mark.parametrize("question", [
    "How does indexing split parent sections into child chunks?",
    "Как при индексации секции разбиваются на дочерние чанки?",
])
def test_explicit_chunking_question_retains_existing_alias(question):
    assert any(
        a.intent_id == "index_chunking"
        for a in build_project_retrieval_aliases(question)
    )


def test_query_plan_keeps_host_need_without_invented_chunking_lane():
    question = "Should I split a comparison into separate search requests?"
    lookups = ("split comparison before first documentation result",)
    plan = build_documentation_query_plan(
        question,
        lookup_queries=lookups,
        requirements=build_requirements(question, profile="project_docs_answer"),
    ).as_payload()
    assert plan["original_question"] == question
    assert any(
        q["origin"] == "host_lookup" and q["text"] == lookups[0]
        for q in plan["queries"]
    )
    assert not any(
        "indexing split documentation sections parent child chunks" in q["text"]
        for q in plan["queries"]
    )


def _native_alias_service(tmp_path: Path):
    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[project]\nname="alias-subject-regression"\nversion="0.1"\n',
        encoding="utf-8",
    )
    (docs / "retrieval-workflow.md").write_text(
        "# Retrieval workflow\n\n"
        "Before retrieval, keep one root request. Do not pre-split a single "
        "compound or comparison question. Split only after the first packet "
        "leaves a concrete independently answerable requested part missing. "
        "A comparison alone does not trigger a split.\n",
        encoding="utf-8",
    )
    (docs / "indexing.md").write_text(
        "# Indexing\n\n"
        "Markdown indexing normalizes documentation into parent sections. "
        "The chunker then splits each parent section into token-bounded child "
        "chunks. Child chunks preserve the parent heading.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: docs/retrieval-workflow.md\n"
        "    role: runbook\n"
        "    scope: project\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    description: Retrieval workflow\n"
        "  - path: docs/indexing.md\n"
        "    role: project_architecture\n"
        "    scope: project\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    description: Indexing architecture\n",
        encoding="utf-8",
    )
    config = DocmancerConfig()
    config.index.provider = "sqlite"
    config.index.db_path = str(tmp_path / "state" / "index.db")
    config.index.extracted_dir = str(tmp_path / "state" / "extracted")
    service = LibraryDocsService(config=config, config_source="explicit")
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    return service, project


def _native_capture(service, project, question, *, lookups=()):
    return capture_public_call(service, {
        "project_path": str(project),
        "scope": "project",
        "question": question,
        "lookup_queries": list(lookups),
    })


def test_native_comparison_search_does_not_route_through_indexing_distractor(tmp_path):
    service, project = _native_alias_service(tmp_path)
    question = (
        "If my question compares two things, should I split it into separate "
        "documentation searches before seeing the first result?"
    )
    lookups = (
        "comparison question retrieval planning",
        "split comparison before first documentation result",
    )
    record = _native_capture(service, project, question, lookups=lookups)
    payload = record["public_payload"]
    plan = record["projection_attempts"][0]["before_projection"]["documentation_query_plan"]

    assert not any(
        q["origin"] == "canonical_intent" and "parent child chunks" in q["text"]
        for q in plan["queries"]
    )
    paths = [source["path_or_url"] for source in payload["sources"]]
    assert "docs/retrieval-workflow.md" in paths
    assert "docs/indexing.md" not in paths
    assert any(
        "Do not pre-split a single compound or comparison question" in source["snippet"]
        for source in payload["sources"]
    )
    assert payload["kind"] == "docs_context"
    assert payload["answer_supported"] is False
    assert payload["answer_available"] is False
    assert payload["edit_ready"] is False
    assert payload["estimated_tokens"] <= 800
    assert len(payload["sources"]) <= 3


def test_native_explicit_chunking_query_still_returns_indexing_contract(tmp_path):
    service, project = _native_alias_service(tmp_path)
    record = _native_capture(
        service,
        project,
        "How does indexing split parent sections into child chunks?",
    )
    payload = record["public_payload"]
    assert any(
        source["path_or_url"] == "docs/indexing.md"
        and "token-bounded child chunks" in source["snippet"]
        for source in payload["sources"]
    )
    assert payload["estimated_tokens"] <= 800
    assert len(payload["sources"]) <= 3
