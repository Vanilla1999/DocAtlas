from __future__ import annotations

from docmancer.docs.application.evidence_selection import (
    build_requirements,
    diagnose_proofability,
    project_docs_selection_config,
    select_evidence,
)
from docmancer.docs.application.model_visible_projection import (
    project_docs_answer,
    validate_model_visible_projection,
)


def _select(question: str, candidates: list[dict], *, budget: int = 800):
    requirements = build_requirements(question, profile="project_docs_answer")
    return select_evidence(
        candidates,
        question=question,
        config=project_docs_selection_config(budget),
        requirements=requirements,
    )


def test_selector_rejects_branding_and_chooses_inventory_witness():
    question = "How many public MCP tools does DocAtlas expose?"
    candidates = [
        {
            "stable_id": "branding",
            "source": "CONTRIBUTING.md",
            "content": "New user-facing docs should use DocAtlas and the doc-atlas CLI command.",
        },
        {
            "stable_id": "inventory",
            "source": "roadmap/README.md",
            "content": "Preserve the three-tool public Docs MCP surface: `get_docs_context`, `prepare_docs`, `docs_status`.",
        },
    ]
    decision = _select(question, candidates)
    assert decision.status == "ok"
    assert decision.support_decision.answer_supported is True
    assert decision.support_decision.selected_evidence_ids == ("inventory",)

    diagnostic = diagnose_proofability(decision)
    assert diagnostic == {
        "schema_version": 1,
        "status": "provable",
        "origin": "none",
        "documentation_issue": False,
        "reason_codes": [],
    }
    assert diagnose_proofability(decision.audit_manifest()) == diagnostic


def test_selector_rejects_wrong_command_and_materializes_call():
    question = "Which command does doc-atlas use to sync project docs after file changes?"
    candidates = [
        {
            "stable_id": "troubleshooting",
            "source": "wiki/Troubleshooting.md",
            "content": "The agent does not use the Docs MCP workflow.",
        },
        {
            "stable_id": "command",
            "source": "README.md",
            "content": 'Call `prepare_docs(action="sync_project_docs", changed_paths=[...])` after file changes.',
        },
    ]
    decision = _select(question, candidates)
    assert decision.status == "ok"
    assert decision.support_decision.selected_evidence_ids == ("command",)

    retrieval_failure = _select(
        "What is the project-wide retry policy?",
        [],
    )
    diagnostic = diagnose_proofability(retrieval_failure)
    assert diagnostic["status"] == "blocked"
    assert diagnostic["origin"] == "retrieval"
    assert diagnostic["documentation_issue"] is False
    assert diagnostic["reason_codes"] == ["no_candidate_evidence"]
    assert diagnostic["candidate_count"] == 0
    assert diagnose_proofability(retrieval_failure.audit_manifest()) == diagnostic


def test_witness_scoped_fitting_does_not_charge_the_surrounding_chunk():
    question = "What are the public tools of the Docs MCP server?"
    content = ("Background " * 3000) + (
        "\n- The public tools are `get_docs_context`, `prepare_docs`, and `docs_status`."
    )
    decision = _select(
        question,
        [{"stable_id": "long-roadmap", "source": "roadmap/README.md", "content": content}],
    )
    assert decision.status == "ok"
    selected = decision.selected_candidates[0]
    assert selected.fit_token_estimate < 200
    assert selected.token_estimate < 100

    stale_failure = _select(
        question,
        [{
            "stable_id": "stale-roadmap",
            "source": "roadmap/README.md",
            "content": "The public tools are `get_docs_context`, `prepare_docs`, and `docs_status`.",
            "freshness": "stale",
        }],
    )
    diagnostic = diagnose_proofability(stale_failure)
    assert diagnostic["status"] == "blocked"
    assert diagnostic["origin"] == "eligibility"
    assert diagnostic["documentation_issue"] is False
    assert diagnostic["reason_codes"][:2] == [
        "all_candidate_evidence_ineligible",
        "ineligible_stale",
    ]
    assert diagnostic["candidate_count"] == 1
    assert diagnostic["eligible_count"] == 0
    assert diagnostic["omission_counts"]["stale"] == 1
    assert diagnose_proofability(stale_failure.audit_manifest()) == diagnostic


def test_location_and_workflow_materialize_valid_canonical_projection():
    cases = [
        (
            "Where is the DocAtlas execution roadmap?",
            {
                "stable_id": "roadmap",
                "source": "roadmap/README.md",
                "title": "Execution roadmap",
                "content": "Current execution tasks are tracked here.",
            },
            "roadmap/README.md",
        ),
        (
            "How does prepare_docs sync_project_docs work?",
            {
                "stable_id": "workflow",
                "source": "README.md",
                "content": '`prepare_docs(action="sync_project_docs")` first discovers changed project documents. Then it removes deleted pages, reindexes changed sections, and publishes the new generation.',
            },
            "publishes the new generation",
        ),
    ]
    for question, candidate, expected in cases:
        decision = _select(question, [candidate])
        assert decision.status == "ok", decision.missing_requirements
        projection, snapshot = project_docs_answer(
            question=question,
            retrieval={
                "status": "success",
                "answer_available": True,
                "selection_profile": "project_docs_answer",
                "context_pack": [candidate],
            },
            canonical_selection=decision,
        )
        assert projection["status"] == "ok"
        assert expected in projection["answer"]
        assert validate_model_visible_projection(
            projection,
            snapshot=snapshot,
            max_tokens=800,
            canonical_selection=decision,
        ) == []

    navigation_failure = _select(
        "What are the public tools of the Docs MCP server?",
        [{
            "stable_id": "navigation",
            "source": "docs/index.md",
            "content": "See the API reference for the public tool inventory.",
            "navigation_only": True,
        }],
    )
    diagnostic = diagnose_proofability(navigation_failure)
    assert diagnostic["status"] == "blocked"
    assert diagnostic["origin"] == "source_documentation"
    assert diagnostic["documentation_issue"] is True
    assert "navigation_only_evidence" in diagnostic["reason_codes"]
    assert diagnostic["recommended_doc_action"] == "add_factual_documentation"
    assert diagnostic["omission_counts"]["navigation_only"] == 1
    assert diagnose_proofability(navigation_failure.audit_manifest()) == diagnostic
