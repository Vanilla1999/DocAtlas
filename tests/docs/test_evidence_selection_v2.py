from __future__ import annotations

from pathlib import Path

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
from tests.docs.test_question_frame_paraphrase_e2e import _service


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


def test_permission_frames_select_and_project_decisive_local_evidence(tmp_path, monkeypatch):
    fixture_docs = (
        Path(__file__).parents[2]
        / "eval/task_level/fixtures/templates/decisive_nbo_cross_module_gate_large_001/docs"
    )
    candidates = []
    for name in ("browser-flow.md", "scan-flow.md", "offline-sync.md", "permission-architecture.md"):
        content = (fixture_docs / name).read_text(encoding="utf-8")
        candidates.append({
            "stable_id": f"permission-{name}",
            "source": f"docs/{name}",
            "path": f"docs/{name}",
            "title": content.splitlines()[0].removeprefix("# "),
            "authority": "primary",
            "lifecycle_status": "active",
            "content": content,
        })
    architecture = candidates[3]
    architecture_paragraph = (
        "Browser and scan flows both share the same immediate-entry contract. "
        "Browser may set `allowOfflineFallback` when it can queue work for later, but offline fallback still cannot bypass missing immediate-entry permissions. "
        "Offline sync must also delegate to the same permission service before accepting work created by either flow."
    )
    architecture["content"] = architecture_paragraph
    architecture["display_text"] = "Browser and scan flows both share the same immediate-entry contract."
    architecture["authority"] = "supporting"
    cases = [
        (
            "According to the project documentation, which PermissionDecision permits BrowserPermissionGate to enter?",
            "PermissionDecision.allow",
            True,
        ),
        (
            "According to the project documentation, how does ScanPermissionGate determine whether scan may enter?",
            "evaluateFlowEntry",
            True,
        ),
        (
            "According to the project documentation, what allowOfflineFallback value must offline sync pass to PermissionService.evaluateFlowEntry?",
            "allowOfflineFallback: false",
            True,
        ),
        (
            "What project permission contract applies to browser, scan, and sync when immediate permission is missing?",
            "cannot bypass missing immediate-entry permissions",
            False,
        ),
        (
            "What does the browser flow do to determine permission for entry?",
            "evaluateFlowEntry",
            False,
        ),
        (
            "What does offline sync do before accepting queued work?",
            "before accepting queued work",
            False,
        ),
    ]
    for question, expected, answer_expected in cases:
        decision = _select(question, candidates)
        if not answer_expected:
            assert decision.status == "insufficient_evidence"
            assert any(item.startswith("context_only:") for item in decision.missing_requirements)
            continue
        assert decision.status == "ok", decision.missing_requirements
        projection, _snapshot = project_docs_answer(
            question=question,
            retrieval={
                "status": "success", "answer_available": True,
                "selection_profile": "project_docs_answer", "context_pack": candidates,
            },
            canonical_selection=decision,
        )
        assert projection["status"] == "ok"
        assert expected in projection["answer"]
        assert validate_model_visible_projection(
            projection,
            snapshot=_snapshot,
            max_tokens=800,
            canonical_selection=decision,
        ) == []

    project = tmp_path / "permission-project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (project / "README.md").write_text("# Permission fixture\n", encoding="utf-8")
    for name in ("browser-flow.md", "scan-flow.md", "offline-sync.md", "permission-architecture.md"):
        (docs / name).write_text((fixture_docs / name).read_text(encoding="utf-8"), encoding="utf-8")
    manifest = [
        "schema_version: 1", "documents:",
        "  - path: README.md", "    role: overview", "    scope: project",
        "    description: Permission fixture overview.",
        "    authority: source_of_truth", "    status: active", "    impact: track",
    ]
    for name in ("browser-flow.md", "scan-flow.md", "offline-sync.md", "permission-architecture.md"):
        manifest.extend((
            f"  - path: docs/{name}",
            "    role: other",
            "    scope: project",
            f"    description: Permission fixture evidence from docs/{name}.",
            "    authority: source_of_truth",
            "    status: active",
            "    impact: track",
        ))
    (project / "docatlas.project-docs.yaml").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8",
    )
    service = _service(tmp_path, monkeypatch)
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"
    for question, _expected, answer_expected in cases:
        result = service.get_docs_context(
            question,
            project_path=str(project),
            mode="project",
            scope="project",
            tokens=4_000,
            limit=12,
        )
        assert result.answer_available is answer_expected, (
            question, result.status, result.reason_code, result.message,
            result.next_action, result.missing_requirement_ids,
        )

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
