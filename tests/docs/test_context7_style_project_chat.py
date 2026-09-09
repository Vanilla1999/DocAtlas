from __future__ import annotations

import pytest

from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    build_project_answer_contract,
    can_authorize_docs_answer,
)
from docmancer.docs.domain.project_retrieval_intent import (
    build_project_retrieval_aliases,
    project_retrieval_allows_certified_answer,
    project_retrieval_disposition,
    project_retrieval_requires_context_only,
)
from docmancer.docs.application.recovery import _suggested_questions


@pytest.mark.parametrize(
    ("question", "intent_id"),
    [
        ("Как установить DocAtlas и проверить запуск?", "installation_verification"),
        ("Какие первые команды выполнить после установки?", "getting_started"),
        ("Где хранится индекс и как он изолирован по проектам?", "project_storage"),
        ("Как пользоваться без интернета?", "offline_usage"),
        ("Что делать, когда ничего не находится?", "troubleshooting"),
        ("Что нужно протестировать перед открытием pull request?", "testing_contribution"),
        ("Где посмотреть карту модулей и с чего читать кодовую базу?", "contributor_start"),
        ("Куда пишется база индекса проекта?", "project_storage"),
        ("Что сделать после редактирования markdown-документа, чтобы поиск увидел изменения?", "project_docs_sync"),
        ("Почему get_docs_context вернул insufficient_evidence и что проверить первым?", "troubleshooting"),
        ("Архитектура?", "project_architecture"),
    ],
)
def test_russian_newcomer_queries_get_retrieval_only_aliases(question: str, intent_id: str):
    aliases = build_project_retrieval_aliases(question)

    assert intent_id in {alias.intent_id for alias in aliases}
    assert all(alias.force_context_only for alias in aliases)
    assert all(alias.text for alias in aliases)


@pytest.mark.parametrize(
    "question",
    [
        "Какую лунную квантовую политику хранения использует DocAtlas?",
        "Какой вымышленный контракт удержания принят в этом проекте?",
        "Which undocumented retention policy governs this repository?",
    ],
)
def test_named_policy_or_contract_is_not_collapsed_to_broad_storage_alias(question: str):
    assert build_project_retrieval_aliases(question) == ()


def test_state_home_variable_uses_narrow_retrieval_without_forcing_context():
    aliases = build_project_retrieval_aliases(
        "Какая переменная задаёт корень состояния DocAtlas?"
    )

    alias = next(row for row in aliases if row.intent_id == "state_home_variable")
    assert alias.force_context_only is False
    assert "DOCATLAS_HOME" in alias.text


def test_russian_docs_mcp_start_command_builds_a_command_obligation():
    contract = build_project_answer_contract(
        "Какая команда запускает Docs MCP сервер?"
    )

    assert any(
        obligation.kind == "command" and obligation.relation == "invocation"
        for obligation in contract.proof_obligations
    )


def test_exact_symbol_question_is_not_misclassified_as_product_overview():
    aliases = build_project_retrieval_aliases("What is DOCATLAS_HOME?")

    assert "product_overview" not in {alias.intent_id for alias in aliases}

    aliases = build_project_retrieval_aliases("What is the model-visible projection?")

    assert "product_overview" not in {alias.intent_id for alias in aliases}


def test_generic_project_alias_does_not_require_docatlas_product_wording():
    aliases = build_project_retrieval_aliases(
        "Как установить проект локально и проверить запуск?"
    )

    installation = next(
        alias for alias in aliases if alias.intent_id == "installation_verification"
    )
    assert "DocAtlas" not in installation.text


def test_broad_intent_suppresses_mandatory_proof_queries_for_retrieval():
    plan = build_documentation_query_plan(
        "Какие первые команды выполнить после установки?",
        requirements=(),
    )

    canonical = [item for item in plan.queries if item.origin == "canonical_intent"]
    original = next(item for item in plan.queries if item.origin == "original")
    assert canonical
    assert original.coverage_required is False
    assert any(item.facet_id == "intent-context:getting_started" for item in canonical)

    technical = build_documentation_query_plan(
        "Compare docatlas.project-docs.yaml with docatlas.docs.yaml via get_docs_context"
    )
    anchors = [item.text for item in technical.queries if item.origin == "exact_anchor"]
    assert anchors == [
        "docatlas.project-docs.yaml", "docatlas.docs.yaml", "get_docs_context",
    ]


def test_canonical_intent_can_carry_bounded_context_without_answer_proof():
    question = "Как установить проект локально и проверить запуск?"
    plan = build_documentation_query_plan(question, requirements=())
    canonical = next(
        item for item in plan.queries if item.origin == "canonical_intent"
    )
    retrieval = {
        "context_pack": [{
            "source_class": "project_doc",
            "path": "README.md",
            "heading_path": "Installation",
            "content": (
                "Local installation setup verification: install the package, run command-line "
                "help, and verify the server starts."
            ),
            "project_identity": "git:example/project",
            "authority": "source_of_truth",
            "doc_scope": "project",
            "lifecycle_status": "active",
            "freshness": "current",
            "index_freshness": "synchronized",
            "risk_flags": [],
            "retrieval_query_matches": {
                canonical.query_id: {
                    "qualified": True,
                    "mode": "and",
                    "query_text": canonical.text,
                },
            },
        }],
        "documentation_query_plan": plan.as_payload(),
    }

    projection, _snapshot = project_docs_context(retrieval=retrieval)

    assert projection["status"] == "ok"
    assert projection["kind"] == "docs_context"
    assert projection["answer_supported"] is False
    assert projection["edit_ready"] is False
    assert projection["sources"][0]["path_or_url"] == "README.md"
    assert canonical.query_id not in projection["covered_query_ids"]
    assert projection["missing_query_ids"] == ["query-original"]
    assert any(
        facet["status"] == "retrieval_only" for facet in projection["facets"]
    )


def test_generic_first_commands_are_not_docs_mcp_public_tool_inventory():
    contract = build_project_answer_contract(
        "Какие первые команды выполнить после установки?"
    )

    assert not any(
        obligation.attribute == "public_tools"
        for obligation in contract.proof_obligations
    )


def test_explicit_docs_mcp_command_inventory_remains_supported():
    contract = build_project_answer_contract(
        "What public commands does Docs MCP expose?"
    )

    assert any(
        obligation.attribute == "public_tools"
        for obligation in contract.proof_obligations
    )


def test_explicit_docs_mcp_tool_inventory_remains_supported():
    contract = build_project_answer_contract(
        "Какие публичные инструменты есть у Docs MCP?"
    )

    assert any(
        obligation.attribute == "public_tools"
        for obligation in contract.proof_obligations
    )


def test_generic_architecture_is_not_rewritten_as_mcp_server_architecture():
    contract = build_project_answer_contract("Архитектура?")

    assert not any(
        obligation.subject == "MCP server" and obligation.relation == "architecture"
        for obligation in contract.proof_obligations
    )
    assert can_authorize_docs_answer(contract) is False


class _EmptyRequirements:
    retrieval_hints = ()
    query_requirement_spans = ()

    def __iter__(self):
        return iter(())


def test_russian_parser_failure_does_not_generate_mixed_language_rephrase():
    assert _suggested_questions(
        "Как пользоваться DocAtlas?",
        _EmptyRequirements(),
        evidence_path=None,
    ) == []


def test_broad_retrieval_intent_requires_context_only_delivery():
    assert project_retrieval_requires_context_only(
        "Где хранится индекс и как он изолирован для каждого проекта?"
    ) is True
    assert project_retrieval_requires_context_only(
        "Какая команда запускает Docs MCP сервер?"
    ) is False


def test_certified_answer_preservation_requires_a_complete_question_contract():
    narrow = "Which command syncs project docs after file changes?"
    mixed = (
        "Which command syncs project docs after file changes and "
        "how is the project architecture organized?"
    )

    assert project_retrieval_requires_context_only(narrow) is False
    assert project_retrieval_allows_certified_answer(narrow) is True
    assert project_retrieval_requires_context_only(mixed) is True
    assert project_retrieval_allows_certified_answer(mixed) is False
    assert project_retrieval_allows_certified_answer(
        "How do I install and verify DocAtlas locally?"
    ) is False
    assert project_retrieval_allows_certified_answer(
        "What is DocAtlas and what problem does it solve?"
    ) is False
    assert project_retrieval_allows_certified_answer(
        "What test markers are available?"
    ) is True


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is OrdersDraftStore?", "typed_context"),
        ("What is Storage?", "broad_context"),
        ("What markers are available?", "broad_context"),
        ("What test markers are available?", "typed_context"),
        ("Which imaginary contract governs this repository?", "fail_closed"),
        ("How many attempts does ProjectRetryPolicy allow?", "fail_closed"),
        ("Does README prove the storage writer-lease contract?", "broad_context"),
        ("What lunar quantum retention policy does DocAtlas use?", "fail_closed"),
        ("What problem do projects solve?", "broad_context"),
        ("What is the model-visible projection?", "broad_context"),
    ],
)
def test_project_retrieval_disposition_is_structural(question: str, expected: str):
    assert project_retrieval_disposition(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "What problem does a project solve?",
        "What problem do projects solve?",
        "What problem does a repository solve?",
        "What problem do repositories solve?",
        "What problem do systems solve?",
        "What problem do products solve?",
    ],
)
def test_project_scope_aliases_accept_bounded_plural_forms(question: str):
    assert project_retrieval_disposition(question) == "broad_context"


@pytest.mark.parametrize("term", ["projection", "projector", "projective"])
def test_project_scope_aliases_reject_prefix_collisions(term: str):
    assert build_project_retrieval_aliases(f"What is the model-visible {term}?") == ()


def test_current_docatlas_index_persists_across_service_restart_without_resync(
    tmp_path, monkeypatch,
):
    from docmancer.agent import DocmancerAgent
    from docmancer.core.config_resolution import resolve_config
    from docmancer.docs.application.docs_job_service import DocsJobTracker
    from docmancer.docs.registry import LibraryRegistry
    from docmancer.docs.service import LibraryDocsService
    from docmancer.mcp.docs_server import call_docs_tool_payload

    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        """# Local installation setup verification getting started

Install the project locally with `pipx install sample-project`.
Verify the installation with `sample-project --help`.
""",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        """schema_version: 1
documents:
  - path: README.md
    role: overview
    scope: project
    description: Installation and verification guide.
    authority: source_of_truth
    status: active
    impact: track
""",
        encoding="utf-8",
    )
    (project / "docatlas.yaml").write_text(
        """index:
  provider: sqlite
  db_path: .docatlas/docatlas.db
  extracted_dir: .docatlas/extracted
query:
  default_budget: 800
  default_limit: 5
  default_expand: none
project:
  documentation_roots:
    - .
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("DOCATLAS_HOME", str(project / ".docatlas"))

    resolved = resolve_config(project_path=project)
    first_agent = DocmancerAgent(config=resolved.config)
    first = LibraryDocsService(
        config=resolved.config,
        config_source=resolved.source,
        config_path=resolved.path,
        registry=LibraryRegistry(resolved.config.index.db_path),
        agent=first_agent,
        job_tracker=DocsJobTracker(db_path=resolved.config.index.db_path),
    )
    sync = first.sync_project_docs(str(project), with_vectors=False)
    assert sync.status == "success"
    first_stats = first_agent.collection_stats()
    first_generation = first_agent.store.generation_info()
    assert first_stats["sources_count"] == 1
    assert first_stats["sections_count"] >= 1
    assert first_generation is not None

    # Simulate a fresh MCP/service process against only the current .docatlas DB.
    reopened = resolve_config(project_path=project)
    second_agent = DocmancerAgent(config=reopened.config)
    second = LibraryDocsService(
        config=reopened.config,
        config_source=reopened.source,
        config_path=reopened.path,
        registry=LibraryRegistry(reopened.config.index.db_path),
        agent=second_agent,
        job_tracker=DocsJobTracker(db_path=reopened.config.index.db_path),
    )
    assert second_agent.collection_stats() == first_stats
    assert second_agent.store.generation_info() == first_generation

    result = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "Как установить проект локально и проверить запуск?",
            "project_path": str(project),
        },
        second,
    )

    assert result["status"] == "ok"
    assert result["kind"] == "docs_context"
    assert result["edit_ready"] is False
    assert result["sources"][0]["path_or_url"] == "README.md"


@pytest.mark.parametrize(
    ("question", "expected_facet"),
    [
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
    ],
)
def test_direct_questions_get_relation_specific_retrieval_facets(question: str, expected_facet: str):
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
def test_direct_relation_facets_do_not_capture_neighboring_questions(question: str, forbidden_facet: str):
    facets = {alias.intent_id for alias in build_project_retrieval_aliases(question)}
    assert forbidden_facet not in facets


def test_direct_product_purpose_alias_stays_product_overview_only():
    aliases = build_project_retrieval_aliases(
        "What is DocAtlas, and what core problem is it designed to solve for coding agents?"
    )
    assert {alias.intent_id for alias in aliases} == {"product_overview"}


def test_docs_mcp_sequence_alias_is_workflow_not_product_overview():
    aliases = build_project_retrieval_aliases(
        "What is the recommended sequence of MCP tool calls for answering a normal project documentation question?"
    )
    facets = {alias.intent_id for alias in aliases}
    assert "docs_mcp_workflow" in facets
    assert "product_overview" not in facets


@pytest.mark.parametrize(
    "question",
    [
        "What does fail-closed behavior mean in the DocAtlas documentation workflow?",
        "What is the difference between docs_answer, docs_context, patch_context, and insufficient_evidence?",
    ],
)
def test_concept_questions_do_not_receive_troubleshooting_alias(question: str):
    assert "troubleshooting" not in {
        alias.intent_id for alias in build_project_retrieval_aliases(question)
    }


def test_real_insufficient_evidence_incident_keeps_troubleshooting_alias():
    aliases = build_project_retrieval_aliases(
        "get_docs_context returned insufficient_evidence unexpectedly; how do I troubleshoot it?"
    )
    assert "troubleshooting" in {alias.intent_id for alias in aliases}
