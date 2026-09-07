import json

import pytest

from eval import project_context_quality_v2_protocol as protocol


@pytest.mark.parametrize("mutation", ["valid", "omitted", "heading", "foreign"])
def test_inventory_question_requires_names_not_unasked_roles(mutation):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-docs-server")
    snippet = "The three Docs MCP public tools are `get_docs_context`, `prepare_docs`, and `docs_status`."
    path = "docs/mcp-docs-server.md"
    if mutation == "omitted":
        snippet = "The Docs MCP server exposes exactly three public tools"
    elif mutation == "heading":
        snippet = "## " + snippet
    elif mutation == "foreign":
        path = "CONTRIBUTING.md"
    response = {"kind": "docs_context", "estimated_tokens": 100,
                "sources": [{"path_or_url": path, "evidence_id": "inventory", "snippet": snippet}]}
    assert protocol.evaluate_case(case, response)["semantic_useful"] is (mutation == "valid")


@pytest.mark.parametrize("omit_test", [False, True])
def test_offline_alternative_preserves_separate_test_obligation(omit_test):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-offline")
    sources = [{"path_or_url": "wiki/Supported-Sources.md", "evidence_id": "ingest",
                "snippet": "`--no-vectors` skips the embedding + vector upsert path for FTS5-only ingest."}]
    if not omit_test:
        sources.append({"path_or_url": "docs/testing.md", "evidence_id": "test",
                        "snippet": 'DOCATLAS_OFFLINE=1 pytest tests/ -m "not advanced and not live and not live_network"'})
    assert protocol.evaluate_case(case, {"kind": "docs_context", "estimated_tokens": 150,
                                         "sources": sources})["semantic_useful"] is (not omit_test)


def test_broad_selection_question_does_not_inherit_lookup_obligations():
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-evidence-selection")
    response = {"kind": "docs_context", "estimated_tokens": 150, "sources": [{
        "path_or_url": "docs/mcp-docs-server.md", "evidence_id": "selection",
        "snippet": "Evidence selection chooses candidates by requiring locally bound subject, relation, and value proof for every mandatory facet; complete exact proof outranks compact generic text."}]}
    assert protocol.evaluate_case(case, response)["semantic_useful"]


def test_v2_inventory_lock_witnesses_and_report_only_lanes():
    validation = protocol.validate_corpus()
    assert validation == {"case_count": 25, "lane_counts": {"natural": 19, "exposed_paraphrases": 6}, "witness_document_count": 12}
    assert sum(case["expected_kind"] == "docs_context" for case in protocol.load_cases("natural")) == 15
    assert sum(case["expected_kind"] == "docs_context" for case in protocol.load_cases("exposed_paraphrases")) == 5
    report = protocol.evaluate({})
    assert report["report_only"] is True
    assert report["verdict"] == "REPORT_ONLY"
    assert report["thresholds"] is None
    assert report["lanes"]["natural"]["status"] == "BASELINE_REPORT_ONLY"
    assert report["lanes"]["exposed_paraphrases"]["status"] == "EXPOSED_PARAPHRASES_REPORT_ONLY"
    assert report["lanes"]["natural"]["metrics"]["semantic_usefulness"] == {"numerator": 0, "denominator": 15}
    assert report["lanes"]["natural"]["metrics"]["negative_correctness"] == {"numerator": 0, "denominator": 2}
    assert report["lanes"]["natural"]["metrics"]["unsupported_answer_control_correctness"] == {"numerator": 0, "denominator": 2}
    assert report["lanes"]["exposed_paraphrases"]["metrics"]["semantic_usefulness"]["denominator"] == 5
    strict_ids = {case["id"] for case in protocol.load_cases() if case.get("case_type", "strict_negative" if case["expected_kind"] == "insufficient_evidence" else "positive") == "strict_negative"}
    assert strict_ids == {"v2-natural-negative-retention", "v2-natural-negative-telepathy", "v2-paraphrase-negative-martian"}


def test_markdown_normalization_preserves_identifiers_negation_and_modality():
    assert protocol.normalize_prose("Use [`get_docs_context`](x); must not prune.") == "use get_docs_context; must not prune."
    assert protocol.normalize_prose("must prune") != protocol.normalize_prose("must not prune")
    assert protocol.normalize_prose("doc-atlas") != protocol.normalize_prose("doc_atlas")


@pytest.mark.parametrize("fixture_id", ["missing-verification", "invented-lineage", "safe-extra", "false-full-original", "unsupported-false-support"])
def test_diagnostic_root_cause_and_metric_separation(fixture_id):
    payload = json.loads(protocol.DIAGNOSTIC_PATH.read_text())
    fixture = next(row for row in payload["fixtures"] if row["id"] == fixture_id)
    case = next(row for row in protocol.load_cases() if row["id"] == fixture["case_id"])
    result = protocol.evaluate_case(case, fixture["response"])
    assert result["root_cause"] == fixture["expected_root_cause"]
    if fixture_id == "missing-verification":
        assert result["lookup_attribution_complete"] and not result["semantic_useful"]
    if fixture_id == "invented-lineage":
        assert result["semantic_useful"] and not result["lookup_attribution_complete"]
    if fixture_id == "safe-extra":
        assert result["semantic_useful"] and result["unadjudicated_source_paths"] == ["docs/testing.md"]
    if fixture_id == "false-full-original":
        assert result["runtime_claimed_original_retrieval_coverage"]
        assert result["false_full_coverage"]
    if fixture_id == "unsupported-false-support":
        assert not result["unsupported_answer_control_correct"]


def test_real_response_uses_public_fields_and_catalog_identity():
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-contributor")
    response = {"kind":"docs_context","estimated_tokens":100,"covered_query_ids":["query-lookup-1","query-lookup-2"],"missing_query_ids":["query-original"],"sources":[{"path_or_url":"CONTRIBUTING.md","evidence_id":"ev-real","authority":"spoofed","scope":"spoofed","snippet":"New contributors should start by reading README.md, this CONTRIBUTING.md. Run the full test suite."}]}
    result = protocol.evaluate_case(case, response)
    assert result["semantic_useful"]
    assert result["hard_gates"]["source_identity"]


def test_query_original_retrieval_does_not_claim_semantic_completeness():
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-install-verify")
    response = {"fixture_kind":"synthetic","kind":"docs_context","estimated_tokens":10,"covered_query_ids":["query-original"],"sources":[]}
    result = protocol.evaluate_case(case, response)
    assert not result["evaluator_verified_component_coverage"]["full"]
    assert result["runtime_component_coverage_claim"]["status"] == "unavailable"
    assert result["false_full_coverage"] is False


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "heading"])
def test_component_witness_requires_unique_nonempty_evidence_and_substantive_snippet(mutation):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-contributor")
    sources = [{"path":"CONTRIBUTING.md","evidence_id":"ev-1","authority":"source_of_truth","scope":"project","snippet":"New contributors should start by reading README.md, this CONTRIBUTING.md. Run the full test suite."}]
    if mutation == "missing":
        sources[0]["evidence_id"] = ""
    elif mutation == "duplicate":
        sources.append({**sources[0], "snippet":"Run the full test suite."})
    else:
        sources[0]["snippet"] = "## Run the full test suite"
    result = protocol.evaluate_case(case, {"fixture_kind":"synthetic","kind":"docs_context","estimated_tokens":10,"sources":sources})
    assert not result["semantic_useful"]
    assert result["root_cause"] == "source_identity_failure"
    assert not result["evaluator_verified_component_coverage"]["full"]


def test_runtime_component_claim_rejects_foreign_evidence_id():
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-contributor")
    response = {"fixture_kind":"synthetic","kind":"docs_context","estimated_tokens":10,"sources":[{"path":"CONTRIBUTING.md","evidence_id":"ev-returned","authority":"source_of_truth","scope":"project","snippet":"New contributors should start by reading README.md, this CONTRIBUTING.md. Run the full test suite."}],"diagnostics":{"component_coverage":{"mandatory_component_ids":["reading","test"],"covered_component_ids":["reading","test"],"missing_component_ids":[],"evidence_ids":["ev-foreign"],"status":"full"}}}
    result = protocol.evaluate_case(case, response)
    assert result["runtime_component_coverage_claim"]["valid"] is False
    assert result["root_cause"] == "runtime_component_claim_invalid"


@pytest.mark.parametrize("path", ["docs/analysis/p2-product-truth-audit-remediation-v2.md", "wiki/Troubleshooting.md"])
def test_real_response_resolves_active_catalog_root_identity_without_adjudicating_relevance(path):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-purpose-start")
    response = {"kind":"docs_context","estimated_tokens":10,"sources":[{"path_or_url":path,"evidence_id":"ev-root","snippet":"Unreviewed context."}]}
    result = protocol.evaluate_case(case, response)
    assert result["hard_gates"]["source_identity"]
    assert result["unadjudicated_relevance"]
    assert path in result["unadjudicated_source_paths"]


@pytest.mark.parametrize("kind", ["insufficient_evidence", "docs_context"])
def test_unsupported_answer_control_accepts_only_fail_closed_or_safe_context(kind):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-negative-retention-policy")
    response = {"kind":kind,"estimated_tokens":0,"sources":[]}
    if kind == "docs_context":
        response.update(answer_supported=False, answer_available=False, edit_ready=False, covered_query_ids=[], missing_query_ids=["query-original"])
    assert protocol.evaluate_case(case, response)["unsupported_answer_control_correct"]


@pytest.mark.parametrize("kind", ["insufficient_evidence", "docs_context"])
def test_unsupported_answer_control_rejects_authorization_and_gate_failures(kind):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-negative-retention-policy")
    response = {"kind":kind,"estimated_tokens":0,"sources":[],"answer_supported":False,"answer_available":False,"edit_ready":True}
    assert not protocol.evaluate_case(case, response)["unsupported_answer_control_correct"]


def test_unmarked_legacy_fixture_fields_do_not_gain_authority():
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-contributor")
    response = {"kind":"docs_context","estimated_tokens":10,"sources":[{"path":"CONTRIBUTING.md","authority":"source_of_truth","scope":"project","snippet":"Run the full test suite."}]}
    assert protocol.evaluate_case(case, response)["root_cause"] == "source_identity_failure"


def test_lock_rejects_drift(monkeypatch, tmp_path):
    changed = tmp_path / "cases.json"
    changed.write_bytes(protocol.CASES_PATH.read_bytes() + b" ")
    monkeypatch.setattr(protocol, "CASES_PATH", changed)
    with pytest.raises(ValueError, match="hash does not match"):
        protocol.load_cases()


@pytest.mark.parametrize("diagnostics,expected", [
    ({"retrieved_candidate_ids": []}, "no_retrieval_hit"),
    ({"retrieved_candidate_ids": ["a"], "qualification_rejections": ["a"]}, "qualification_rejection"),
    ({"retrieved_candidate_ids": ["a"], "pre_projection_qualified_ids": ["a"], "selected_candidate_ids": []}, "ranking_loss"),
    ({"retrieved_candidate_ids": ["a"], "selected_candidate_ids": ["a"], "projection_rejections": ["a"]}, "projection_truncation"),
])
def test_stage_local_root_cause_classification(diagnostics, expected):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-install-verify")
    response = {"fixture_kind":"synthetic","kind":"docs_context","estimated_tokens":1,"sources":[],"diagnostics":diagnostics}
    assert protocol.evaluate_case(case, response)["root_cause"] == expected


@pytest.mark.parametrize("mutation", ["valid", "foreign", "clipped", "wrong_component", "duplicate", "residue"])
def test_runtime_namespace_and_component_binding_are_independent_of_gold(mutation):
    import hashlib

    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-install-verify")
    source = {"path_or_url": "README.md", "evidence_id": "public-id", "snippet": "Install locally."}
    claim = {"mandatory_component_ids": ["runtime:install"], "covered_component_ids": ["runtime:install"],
             "missing_component_ids": [], "evidence_ids": ["internal-id"], "status": "full"}
    binding = {"component_id": "runtime:install", "evidence_id": "public-id", "path_or_url": "README.md",
               "snippet_sha256": hashlib.sha256(source["snippet"].encode()).hexdigest(), "runtime_evidence_ids": ["internal-id"]}
    if mutation == "foreign":
        binding["evidence_id"] = "not-returned"
    elif mutation == "clipped":
        source["snippet"] = "Install"
    elif mutation == "wrong_component":
        binding["component_id"] = "runtime:verify"
    elif mutation == "duplicate":
        claim["mandatory_component_ids"] *= 2
    elif mutation == "residue":
        claim["unresolved_residue"] = ["verification"]
    response = {"kind": "docs_context", "sources": [source], "estimated_tokens": 100,
                "diagnostics": {"runtime_component_coverage": claim, "component_evidence_bindings": [binding]}}
    result = protocol.evaluate_case(case, response)
    assert result["runtime_component_coverage_claim"]["valid"] is (mutation == "valid")
    assert result["false_full_coverage"] is (mutation == "valid")


@pytest.mark.parametrize("mutation", ["answer", "mutation_ready", "authorized_actions", "oversized", "malformed_source", "contradictory_kind"])
def test_strict_negative_checks_complete_payload(mutation):
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-negative-retention")
    case = {**case, "forbidden_fragments": ["invented retention guarantee"]}
    response = {"kind": "insufficient_evidence", "status": "insufficient_evidence", "sources": [], "estimated_tokens": 0}
    if mutation == "answer":
        response["answer"] = "invented retention guarantee"
    elif mutation == "mutation_ready":
        response["mutation_ready"] = True
    elif mutation == "authorized_actions":
        response["authorized_actions"] = ["edit"]
    elif mutation == "oversized":
        response["answer"] = "x" * 4000
    elif mutation == "malformed_source":
        response["sources"] = ["not structured"]
    else:
        response["kind"] = "docs_answer"
    assert not protocol.evaluate_case(case, response)["negative_correct"]


def test_unobserved_retrieval_is_not_a_no_hit_diagnosis():
    case = next(row for row in protocol.load_cases() if row["id"] == "v2-natural-install-verify")
    result = protocol.evaluate_case(case, {"kind": "docs_context", "sources": [], "estimated_tokens": 0,
                                         "diagnostics": {"stage_status": {"retrieval": "unclassified"}}})
    assert result["root_cause"] == "semantic_obligation_missing"


@pytest.mark.parametrize("assignment_source", ["internal-id", "foreign-id"])
def test_same_call_observer_preserves_public_result_and_binds_visible_components(monkeypatch, assignment_source):
    from types import SimpleNamespace
    from scripts import run_project_docs_self_host_gate as runner

    raw = {"context_pack": []}
    app = SimpleNamespace(get_docs_context=lambda: raw)
    service = SimpleNamespace(unified_context=app)
    payload = {"kind": "docs_context", "sources": [{"evidence_id": "public-id", "path_or_url": "docs/install.md",
                                                   "snippet": "Install locally."}], "estimated_tokens": 100}
    snapshot = {"public-id": {"source": {}, "projected_source": payload["sources"][0]}}
    monkeypatch.setattr(runner.context_tools, "validate_model_visible_projection", lambda *args, **kwargs: [])

    def call(name, arguments, observed_service):
        assert app.get_docs_context() is raw
        decision = runner.docs_context_projection.component_coverage_decision(
            [{"component_id": "install"}],
            [{"requirement_id": "install", "evidence_id": assignment_source, "projected_content_hash": "visible"}],
            [{**payload["sources"][0], "_visible_assignment_hashes": ["visible"],
              "_qualification_candidate": {"stable_id": "internal-id"}}],
        )
        runner.context_tools.validate_model_visible_projection(payload, snapshot=snapshot)
        observed_service._same_call_diagnostics_observer({"runtime_component_coverage": decision.as_payload()})
        return payload

    monkeypatch.setattr(runner, "call_docs_tool_payload", call)
    observed, _ = runner._call_with_snapshot({}, service)
    assert {key: value for key, value in observed.items() if key != "diagnostics"} == payload
    assert "diagnostics" not in payload
    assert not hasattr(service, "_same_call_diagnostics_observer")
    assert observed["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
    claim = protocol._runtime_component_claim(observed, {"public-id"})
    assert claim["valid"] is (assignment_source == "internal-id")
    assert claim["visible_binding_verified"] is (assignment_source == "internal-id")
