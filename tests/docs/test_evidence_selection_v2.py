from __future__ import annotations

from docmancer.docs.application.evidence_selection import (
    build_requirements,
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
