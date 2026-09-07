import hashlib
from types import SimpleNamespace

import pytest

from docmancer.docs.application.context_selection import component_coverage_decision
from docmancer.docs.application.docs_context_projection import _facet_aware_candidates, project_docs_context
from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.application.evidence_selection import build_requirements


def _decision(component_ids, assignments, sources, residue=()):
    return component_coverage_decision(
        ({"component_id": value} for value in component_ids), assignments, sources,
        unresolved_residue=residue,
    )


def _assignment(component_id, evidence_id, content_hash):
    return {"requirement_id": component_id, "evidence_id": evidence_id,
            "projected_content_hash": content_hash}


def _visible_source(text, *, evidence_id="doc"):
    return {
        "evidence_id": "ev-public", "snippet": text,
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "_qualification_candidate": {"stable_id": evidence_id, "content": text},
    }


def _text_assignment(component_id, evidence_id, text):
    return {
        **_assignment(component_id, evidence_id, hashlib.sha256(text.encode()).hexdigest()),
        "unit_char_start": 0, "unit_char_end": len(text),
    }


def test_install_without_verify_and_architecture_without_testing_are_partial():
    for components, covered, missing in (
        (("install", "verify"), "install", "verify"),
        (("architecture", "testing"), "architecture", "testing"),
    ):
        decision = _decision(
            components, (_text_assignment(covered, "project:doc", "visible-hash"),),
            (_visible_source("visible-hash", evidence_id="project:doc"),),
        )
        assert decision.status == "partial"
        assert decision.covered_component_ids == (covered,)
        assert decision.missing_component_ids == (missing,)


def test_unresolved_extra_subsystem_prevents_full_coverage():
    decision = _decision(
        ("architecture",), (_text_assignment("architecture", "doc", "hash"),),
        (_visible_source("hash"),),
        residue=("unresolved subsystem: orbital ledger",),
    )
    assert decision.status == "partial"
    assert decision.unresolved_residue == ("unresolved subsystem: orbital ledger",)


def test_all_visible_assigned_components_are_full():
    decision = _decision(
        ("install", "verify"),
        (_text_assignment("install", "doc", "hash"), _text_assignment("verify", "doc", "hash")),
        (_visible_source("hash"),),
    )
    assert decision.status == "full"
    assert decision.evidence_ids == ("doc",)


def test_clipped_component_witness_is_unavailable():
    decision = _decision(
        ("verify",), (_text_assignment("verify", "doc", "full-witness-hash"),),
        (_visible_source("clipped-visible-hash"),),
    )
    assert decision.status == "unavailable"
    assert decision.evidence_ids == ()
    assert decision.missing_component_ids == ("verify",)


def test_real_projection_uses_visible_witness_hash_across_mixed_prefixed_ids():
    witness = "Verify the installation with the health check."
    content = "Install locally. " + witness
    witness_start = content.index(witness)
    witness_hash = hashlib.sha256(witness.encode()).hexdigest()
    diagnostics = {}
    projection, snapshot = project_docs_context(retrieval={
        "context_pack": [{
            "stable_id": "project:doc-1", "stable_chunk_id": "chunk:doc-1",
            "evidence_id": "retrieval:doc-1", "source_class": "project_doc",
            "path": "docs/install.md", "content": content,
            "project_identity": "git:example/project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "retrieval_query_matches": {"query-original": {"qualified": True, "mode": "and"}},
        }],
        "selection_decision": {"assignments": [{
            **_assignment("project_answer:verify", "project:doc-1", witness_hash),
            "unit_char_start": witness_start, "unit_char_end": witness_start + len(witness),
        }]},
        "documentation_query_plan": {
            "original_question": "install verify health check",
            "query_ids": ["query-original"], "public_query_ids": ["query-original"],
            "queries": [{"query_id": "query-original", "text": "install verify health check", "origin": "original"}],
            "_component_contract": [{"component_id": "project_answer:verify"}],
        },
    }, selection_diagnostics=diagnostics)

    assert diagnostics["component_coverage"]["status"] == "full"
    assert projection["sources"][0]["content_sha256"] != witness_hash
    assert "_visible_assignment_hashes" not in str(projection)
    assert projection["estimated_tokens"] <= 800
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_real_projection_does_not_count_a_clipped_assignment_witness():
    witness = "The release witness is intentionally outside the projected window."
    content = "Install locally with the package command. " + ("padding " * 100) + witness
    witness_start = content.index(witness)
    diagnostics = {}
    projection, snapshot = project_docs_context(retrieval={
        "context_pack": [{
            "stable_id": "project:doc-2", "source_class": "project_doc",
            "path": "docs/install.md", "content": content,
            "project_identity": "git:example/project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "retrieval_query_matches": {"query-original": {"qualified": True, "mode": "and"}},
        }],
        "selection_decision": {"assignments": [{
            **_assignment(
                "project_answer:release", "project:doc-2",
                hashlib.sha256(witness.encode()).hexdigest(),
            ),
            "unit_char_start": witness_start, "unit_char_end": witness_start + len(witness),
        }]},
        "documentation_query_plan": {
            "original_question": "install locally package command",
            "query_ids": ["query-original"], "public_query_ids": ["query-original"],
            "queries": [{"query_id": "query-original", "text": "install locally package command", "origin": "original"}],
            "_component_contract": [{"component_id": "project_answer:release"}],
        },
    }, selection_diagnostics=diagnostics)

    assert witness not in projection["sources"][0]["snippet"]
    assert diagnostics["component_coverage"]["status"] == "unavailable"
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


def test_query_plan_component_contract_preserves_surface_fields():
    requirement = SimpleNamespace(
        obligation_id="project_answer:verify", mandatory=True, kind="condition",
        query_span_start=18, query_span_end=26, query_span_text="must not",
        subject="verify_install", attribute="status", relation="must not skip",
        target="health check", expected_value="PASS", response_mode="workflow",
    )
    plan = build_documentation_query_plan(
        "Install locally; must not skip verification",
        requirements=SimpleNamespace(
            proof_obligations=(requirement,), retrieval_hints=(), concept_queries=(), unresolved_parts=(),
        ),
    ).as_payload()
    assert plan["_component_contract"] == [{
        "component_id": "project_answer:verify", "query_span_start": 18,
        "query_span_end": 26, "query_span_text": "must not", "subject": "verify_install",
        "attribute": "status", "relation": "must not skip", "target": "health check",
        "obligation_kind": "condition", "expected_value": "PASS",
        "response_mode": "workflow", "subject_aliases": (),
    }]


def test_query_plan_components_come_from_real_answer_contract():
    question = "What are the public tools of the Docs MCP server?"
    contract = build_project_answer_contract(question)
    payload = build_documentation_query_plan(question, requirements=contract).as_payload()

    assert contract.proof_obligations
    assert {row["component_id"] for row in payload["_component_contract"]} == {
        obligation.obligation_id
        for obligation in contract.proof_obligations
        if obligation.mandatory
    }


def test_docs_context_does_not_leak_internal_component_trace():
    diagnostics = {}
    projection, _ = project_docs_context(retrieval={
        "context_pack": [{
            "source_class": "project_doc", "path": "docs/install.md",
            "content": "Install locally and verify with the health check.",
            "project_identity": "git:example/project", "lifecycle_status": "active",
            "freshness": "current", "index_freshness": "synchronized", "risk_flags": [],
            "retrieval_query_matches": {"query-original": {"qualified": True, "mode": "and"}},
        }],
        "documentation_query_plan": {
            "query_ids": ["query-original"], "public_query_ids": ["query-original"],
            "queries": [{"query_id": "query-original", "text": "install verify", "origin": "original"}],
            "_component_contract": [{"component_id": "project_answer:install"}],
        },
    }, selection_diagnostics=diagnostics)

    assert diagnostics["component_coverage"]["status"] == "unavailable"
    assert "component_coverage" not in projection
    assert "_component_contract" not in str(projection)


def test_public_coverage_precedes_canonical_facet_novelty():
    public = {"retrieval_query_matches": {"query-lookup-1": {"qualified": True}}}
    canonical = {"retrieval_query_matches": {"query-intent-2": {"qualified": True}}}
    repeated = {"retrieval_query_matches": {"query-intent-1": {"qualified": True}}}

    ranked = _facet_aware_candidates(
        [repeated, canonical, public], query_text={},
        required_query_ids={"query-lookup-1"}, canonical_query_ids={"query-intent-2"},
    )

    assert ranked == [public, canonical, repeated]


@pytest.mark.parametrize("loss", [None, "clip", "projection_clip", "budget", "unknown"])
def test_visible_component_novelty_follows_exact_constraints_before_public_queries(loss):
    question = "What should I read in OrionRepo and what should I test?"
    plan = build_documentation_query_plan(
        question, requirements=build_requirements(question, profile="project_docs_answer"),
    ).as_payload()
    # Use a compact public plan to put four competing sources under the real cap.
    plan.update(
        public_query_ids=["query-anchor", "query-original", "query-lookup-1"],
        queries=[
            {"query_id": "query-anchor", "text": "EXACT_KEY", "origin": "exact_anchor"},
            {"query_id": "query-original", "text": "contributor overview", "origin": "original"},
            {"query_id": "query-lookup-1", "text": "general background", "origin": "host_lookup"},
        ],
    )
    reading = "For OrionRepo, first read README.md, then read docs/architecture.md."
    testing = "For OrionRepo, run pytest tests/docs before opening a pull request."
    components = {row["relation"]: row["component_id"] for row in plan["_component_contract"]}

    def source(identity, content, matches):
        return {
            "stable_id": identity, "source_class": "project_doc", "path": f"docs/{identity}.md",
            "content": content, "project_identity": "repo", "authority": "source_of_truth",
            "freshness": "current", "index_freshness": "synchronized", "lifecycle_status": "active",
            "line_start": 1, "retrieval_query_matches": matches,
        }

    candidates = [
        source("reading", reading + " Contributor overview.", {"query-original": {"query_text": "contributor overview"}}),
        source("duplicate", reading + " General background.", {"query-lookup-1": {"query_text": "general background"}}),
        source("testing", testing, {components["testing"]: {"query_text": "OrionRepo testing"}}),
        source("exact", "EXACT_KEY selects the local contributor configuration.", {"query-anchor": {"query_text": "EXACT_KEY"}}),
    ]
    if loss == "clip":
        candidates[2]["content"] = "For OrionRepo, run"
    elif loss == "projection_clip":
        candidates[2]["content"] = "For OrionRepo, " + "background " * 55 + "run pytest tests/docs before opening a pull request."
    elif loss == "budget":
        candidates[2]["path"] = "docs/" + "oversized" * 500 + ".md"
    elif loss == "unknown":
        plan["_component_contract"] = [row for row in plan["_component_contract"] if row["relation"] != "testing"]
    diagnostics = {}
    projection, snapshot = project_docs_context(retrieval={
        "context_pack": candidates, "documentation_query_plan": plan,
    }, selection_diagnostics=diagnostics)
    paths = [source["path_or_url"] for source in projection["sources"]]
    assert paths[0] == "docs/exact.md"
    assert len(paths) == 3
    assert projection["estimated_tokens"] <= 800
    assert projection["answer_supported"] is False and projection["edit_ready"] is False
    assert "project_answer:" not in str(projection)
    if loss is None:
        assert set(paths) == {"docs/exact.md", "docs/reading.md", "docs/testing.md"}
        assert diagnostics["component_coverage"]["status"] == "full"
        assert "query-lookup-1" in projection["missing_query_ids"]
    else:
        assert "docs/testing.md" not in paths
        assert "docs/duplicate.md" in paths
        if loss != "unknown":
            assert components["testing"] in diagnostics["component_coverage"]["missing_component_ids"]
    for source in projection["sources"]:
        original = snapshot[source["evidence_id"]]["source"]
        assert source["snippet"] in original["content"]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("relation,text,expected", [
    ("reading", "For OrionRepo, first read README.md, then read docs/architecture.md.", True),
    ("testing", "For OrionRepo, first read README.md, then read docs/architecture.md.", False),
    ("reading", "For OrionRepo, run pytest tests/docs before opening a pull request.", False),
    ("testing", "For OrionRepo, run pytest tests/docs before opening a pull request.", True),
    ("testing", "For OrionRepo, do not run pytest tests/docs.", False),
    ("testing", "OrionRepo has documentation. OtherProject runs pytest tests/docs.", False),
])
def test_reading_and_testing_require_their_own_local_action(relation, text, expected):
    from docmancer.docs.application.context_selection import component_obligations, component_witnesses

    obligations = component_obligations([{
        "component_id": "component", "obligation_kind": "workflow", "subject": "OrionRepo",
        "relation": relation, "response_mode": "workflow",
    }])
    witnesses = component_witnesses({
        "source_class": "project_doc", "project_identity": "repo", "snippet": text,
    }, obligations)
    assert bool(witnesses) is expected


def test_disconnected_component_windows_cannot_replace_an_accepted_witness():
    question = "What should I read in OrionRepo and what should I test?"
    plan = build_documentation_query_plan(
        question, requirements=build_requirements(question, profile="project_docs_answer"),
    ).as_payload()
    reading = "For OrionRepo, first read README.md, then read docs/architecture.md."
    testing = "For OrionRepo, run pytest tests/docs before opening a pull request."
    text = reading + "\n\n" + "Unrelated background. " * 60 + "\n\n" + testing
    diagnostics = {}
    projection, snapshot = project_docs_context(retrieval={
        "documentation_query_plan": plan,
        "context_pack": [{
            "stable_id": "one-document", "source_class": "project_doc", "path": "docs/guide.md",
            "project_identity": "repo", "content": text, "line_start": 1,
            "authority": "source_of_truth", "lifecycle_status": "active",
        }],
    }, selection_diagnostics=diagnostics)
    assert len(projection["sources"]) == 1
    snippet = projection["sources"][0]["snippet"]
    assert snippet in text
    assert (reading in snippet) != (testing in snippet)
    coverage = diagnostics["component_coverage"]
    assert coverage["status"] == "partial"
    assert len(coverage["covered_component_ids"]) == len(coverage["missing_component_ids"]) == 1
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=800) == []
