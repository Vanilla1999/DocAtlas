from dataclasses import replace
from itertools import permutations

import pytest

from docmancer.docs.application.context_selection import component_coverage_decision
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract, can_authorize_docs_answer
from docmancer.docs.domain.question_plan import compile_question_plan


def _plan(question):
    return build_documentation_query_plan(
        question, requirements=build_requirements(question, profile="project_docs_answer"),
    ).as_payload()


def _coverage(plan, text, **metadata):
    return component_coverage_decision(plan["_component_contract"], (), ({
        "evidence_id": "visible", "source_class": "project_doc",
        "project_identity": "repository", "snippet": text, **metadata,
    },), unresolved_residue=plan["unresolved_parts"],
        component_scope_complete=plan["component_scope_complete"])


@pytest.mark.parametrize("subject", ["Aurora MCP", "KestrelService", "Delta Bridge"])
@pytest.mark.parametrize("names", [("fetch_item", "queue_work"), ("read_state", "write_state", "clear_state")])
def test_inventory_needs_visible_subject_and_all_declared_names(subject, names):
    plan = _plan(f"Which public tools does {subject} expose?")
    listing = ", ".join(f"`{name}`" for name in names)
    complete = f"{subject} exposes exactly {len(names)} public tools: {listing}."
    decision = _coverage(plan, complete)
    assert decision.as_payload()["recognized_component_status"] == "full"
    assert decision.status == "partial"
    assert decision.unresolved_residue == ("unverified_original_component_scope",)
    contract = build_project_answer_contract(f"Which public tools does {subject} expose?")
    assert not contract.component_scope_complete and not contract.unresolved_parts
    assert not can_authorize_docs_answer(contract)
    diagnostics = {}
    projection, snapshot = project_docs_context(retrieval={
        "documentation_query_plan": plan,
        "context_pack": [{
            "stable_id": "inventory", "source_class": "project_doc", "path": "docs/tools.md",
            "project_identity": "repository", "content": complete,
            "authority": "source_of_truth", "lifecycle_status": "active",
        }],
    }, selection_diagnostics=diagnostics)
    assert diagnostics["component_coverage"]["status"] == "partial"
    assert diagnostics["component_coverage"]["recognized_component_status"] == "full"
    assert projection["answer_supported"] is False and projection["edit_ready"] is False
    assert "component_scope_complete" not in str(projection)
    assert len(projection["sources"]) <= 3 and projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []
    for incomplete in (
        f"Its public workflow has exactly {len(names)} tools: {listing}.",
        f"AnotherService exposes exactly {len(names)} public tools: {listing}.",
        f"{subject} exposes exactly {len(names) + 1} public tools: {listing}.",
        f"## {subject} public tools: {listing}",
        f"{subject} exposes public tools including but not limited to {listing}.",
    ):
        decision = _coverage(plan, incomplete, section=f"{subject} public tools", authority="source_of_truth")
        assert decision.status != "full", incomplete
        assert decision.missing_component_ids


@pytest.mark.parametrize("language", ["en", "ru"])
def test_recognized_components_survive_unknown_clauses_in_every_order(language):
    inventory = {
        "en": "Which public tools does Aurora MCP expose?",
        "ru": "Какие публичные инструменты предоставляет Aurora MCP?",
    }[language]
    unknown = {
        "en": "Explain the orbital ledger warranty?",
        "ru": "Объясните гарантию орбитального реестра?",
    }[language]
    for clauses in permutations((inventory, unknown)):
        for separator in (" ", "; "):
            question = separator.join(clauses)
            parsed = compile_question_plan(question)
            contract = build_project_answer_contract(question)
            plan = _plan(question)
            assert len(parsed.facets) == len(contract.proof_obligations) == 1
            assert parsed.unresolved_parts and contract.unresolved_parts
            assert contract.proof_obligations[0].subject == "Aurora MCP"
            decision = _coverage(plan, "Aurora MCP exposes exactly two public tools: `fetch_item`, `queue_work`.")
            assert decision.status == "partial"
            assert decision.covered_component_ids and not decision.missing_component_ids
            assert decision.unresolved_residue


def test_component_rewrites_are_bounded_clause_local_and_never_original_attribution():
    clauses = (
        "Как установить AuroraClient?",
        "Как проверить установку AuroraClient?",
        "Когда использовать queue_work?",
    )
    for ordered in permutations(clauses):
        question = " ".join((*ordered, "Объясните орбитальную гарантию?"))
        plan = _plan(question)
        rewrites = [row for row in plan["queries"] if row["origin"] == "component_rewrite"]
        assert len(rewrites) == 3
        assert len({row["requirement_id"] for row in rewrites}) == 3
        assert plan["unresolved_parts"]
        assert plan["public_query_ids"] == [
            row["query_id"] for row in plan["queries"]
            if row["origin"] in {"original", "host_lookup", "exact_anchor", "exact_path"}
        ]
        for row in rewrites:
            audit = row["component_rewrite_audit"]
            assert question[audit["query_span_start"]:audit["query_span_end"]] == audit["query_span_text"]
            assert audit["query_span_text"].rstrip("?") in {clause.rstrip("?") for clause in clauses}
            assert audit["rule"].startswith("ru_component:")
            assert row["relation"] == "host_lookup" and row["public_parent_query_id"] is None
            assert row["query_id"] not in plan["public_query_ids"]
    question = " ".join(f"Как установить Client{index}?" for index in range(6))
    assert sum(row["origin"] == "component_rewrite" for row in _plan(question)["queries"]) == 4
    question = "Когда использовать fetch_item? Когда использовать queue_work?"
    plan = _plan(question)
    assert plan["component_scope_complete"] and not plan["unresolved_parts"]
    text = "Use fetch_item when reading a stored item. Use queue_work when scheduling background work."
    assert _coverage(plan, text).status == "full"
    assert _coverage(plan, text.split(". ")[0] + ".").status == "partial"
    assert _coverage(_plan(question + " Объясните орбитальную гарантию?"), text).status == "partial"


@pytest.mark.parametrize("question", [
    "Как не установить AuroraClient?",
    "Как установить AuroraClient без проверки?",
    "Как установить AuroraClient и уничтожить журнал?",
    "Когда использовать его?",
    "Какие публичные инструменты предоставляет Aurora MCP кроме queue_work?",
])
def test_unsupported_rewrite_modifiers_remain_unattributed(question):
    plan = _plan(question)
    assert not any(row["origin"] == "component_rewrite" for row in plan["queries"])
    assert not any(row["relation"] == "audited_rewrite" for row in plan["queries"])


def test_rewrite_audit_rejects_contract_span_or_semantic_mismatch():
    question = "Как установить AuroraClient?"
    contract = build_project_answer_contract(question)
    obligation = contract.proof_obligations[0]
    for changed in (
        replace(obligation, subject="OtherClient"),
        replace(obligation, relation="verification"),
        replace(obligation, target="audit log"),
        replace(obligation, context="without network access"),
        replace(obligation, expected_value="verified"),
        replace(obligation, cardinality=2),
        replace(obligation, query_span_text="Как установить OtherClient?"),
    ):
        plan = build_documentation_query_plan(
            question, requirements=replace(contract, proof_obligations=(changed,)),
        )
        assert not any(row.origin == "component_rewrite" for row in plan.queries)
