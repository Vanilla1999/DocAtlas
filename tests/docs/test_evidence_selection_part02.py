"""Split tests from test_evidence_selection.py; shared helpers remain in the façade module."""
from tests.docs import _shared_test_evidence_selection as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_valid_display_hash_and_reported_token_mismatch_are_audited():
    text = "Unicode доказательство ✅"
    item = _candidate(
        "unicode", text,
        display_content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        token_estimate=999,
    )
    decision = select_evidence([item], question="Что делать?", config=docs_selection_config(800))

    assert decision.status == "ok"
    assert decision.metrics["reported_token_mismatches"] == 1
    assert decision.selected_candidates[0].token_estimate != 999


def test_exact_overlap_and_near_duplicates_are_collapsed_without_text_merging():
    base = _candidate("a", "alpha beta gamma delta epsilon zeta", source="docs/shared.md", char_start=0, char_end=100)
    exact = dict(base)
    overlap = _candidate("b", "alpha beta gamma delta epsilon eta", source="docs/shared.md", char_start=10, char_end=90)
    near = _candidate("c", "alpha beta gamma delta epsilon zeta extra", source="docs/shared.md", char_start=200, char_end=260)
    config = replace(docs_selection_config(800), near_duplicate_threshold=600)

    decision = select_evidence([base, exact, overlap, near], question="Explain alpha", config=config)

    reasons = {item.reason_code for item in decision.omissions}
    assert _ids(decision) == ["a"]
    assert "exact_duplicate" in reasons
    assert "overlap_duplicate" in reasons
    assert "near_duplicate" in reasons


def test_similar_chunks_with_distinct_symbols_and_versions_are_preserved():
    candidates = [
        _candidate("one", "same repeated table header and body", symbols=["first"], version="1.0"),
        _candidate("two", "same repeated table header and body", symbols=["second"], version="1.0"),
        _candidate("three", "same repeated table header and body", symbols=["first"], version="2.0"),
    ]
    config = replace(patch_selection_config(1500), max_items_per_source=5)
    decision = select_evidence(candidates, question="Edit symbols", config=config)

    assert set(_ids(decision)) == {"one", "two", "three"}


def test_mandatory_reservation_prefers_short_complete_evidence():
    long = _candidate("long", "required fact " + "padding " * 300, score=1.0, retrieval_rank=1)
    short = _candidate("short", "required fact", score=0.1, retrieval_rank=20)
    decision = select_evidence(
        [long, short],
        question="Apply change",
        config=patch_selection_config(1500),
        public_requirements=["required fact"],
    )

    assert decision.status == "ok"
    assert _ids(decision)[0] == "short"
    assert "long" not in _ids(decision)


def test_bounded_repair_replaces_one_long_cover_with_two_short_items():
    candidates = [
        _candidate("long", "Must preserve first fact and second fact " + "padding " * 200),
        _candidate("first", "Must preserve first fact."),
        _candidate("second", "Must preserve second fact."),
    ]
    decision = select_evidence(
        candidates,
        question="Apply change",
        config=patch_selection_config(1500),
        public_requirements=["first fact", "second fact"],
    )

    assert decision.status == "ok"
    assert set(_ids(decision)) == {"first", "second"}


def test_missing_or_oversized_mandatory_evidence_is_insufficient():
    missing = select_evidence(
        [_candidate("other", "unrelated")],
        question="Apply change", config=patch_selection_config(1500),
        required_target_paths=["src/required.py"],
    )
    tiny_config = SelectionConfig(
        result_kind="patch_context", target_tokens=160, hard_tokens=160,
        wrapper_reserve_tokens=80, max_sources=3,
    )
    oversized = select_evidence(
        [_candidate("large", "must preserve " + "x" * 1000, source="AGENTS.md", doc_scope="project")],
        question="Apply change", config=tiny_config, required_evidence_paths=["AGENTS.md"],
    )

    assert missing.status == "insufficient_evidence"
    assert any(value.startswith("target_path:") for value in missing.missing_requirements)
    assert oversized.status == "insufficient_evidence"
    assert "mandatory_evidence_does_not_fit" in oversized.missing_requirements
    assert oversized.selected_candidates == ()


def test_candidate_cap_is_applied_after_requirement_aware_ranking():
    candidates = [
        _candidate(f"generic-{index}", f"generic evidence {index}", score=1.0 - index / 100)
        for index in range(25)
    ]
    candidates.append(_candidate("required", "critical public fact", score=0.0, retrieval_rank=100))
    decision = select_evidence(
        candidates,
        question="Apply change",
        config=patch_selection_config(1500),
        public_requirements=["critical public fact"],
    )

    assert decision.status == "ok"
    assert "required" in _ids(decision)
    assert sum(item.reason_code == "candidate_cap" for item in decision.omissions) == 6


def test_forbidden_library_alias_is_rejected_and_authority_is_hash_bound():
    candidate = _candidate(
        "aliased",
        "The supported setting is enabled.",
        source="docs/public.md",
        library_id="private-library",
    )
    rejected = select_evidence(
        [candidate],
        question="Which setting is supported?",
        config=docs_selection_config(800),
        trust_contract={"sources": {"rejected": [{"source": "private-library"}]}},
    )

    assert rejected.status == "insufficient_evidence"
    assert any(item.reason_code == "forbidden_source" for item in rejected.omissions)

    official = select_evidence(
        [candidate], question="Which setting is supported?", config=docs_selection_config(800),
    )
    untrusted = select_evidence(
        [{**candidate, "authority": "untrusted"}],
        question="Which setting is supported?",
        config=docs_selection_config(800),
    )

    assert official.selection_hash != untrusted.selection_hash
    assert official.candidate_trace_hash != untrusted.candidate_trace_hash


def test_mandatory_overflow_metrics_only_count_selected_coverage():
    tiny_config = SelectionConfig(
        result_kind="patch_context",
        target_tokens=160,
        hard_tokens=160,
        wrapper_reserve_tokens=80,
        max_sources=3,
    )
    decision = select_evidence(
        [_candidate("large", "first fact second fact " + "padding " * 200)],
        question="Apply change",
        config=tiny_config,
        public_requirements=["first fact", "second fact"],
    )

    assert decision.status == "insufficient_evidence"
    assert decision.selected_candidates == ()
    assert decision.metrics["mandatory_covered"] == 0
    assert decision.metrics["mandatory_coverage_millis"] == 0


def test_canonical_authority_conflict_is_disclosed_and_blocks_success():
    candidates = [
        _candidate("required", "The worker must enable isolation.", source="AGENTS.md", doc_scope="project"),
        _candidate("forbidden", "The worker must not enable isolation.", source="AGENTS.md", doc_scope="project"),
    ]
    decision = select_evidence(candidates, question="Configure worker", config=patch_selection_config(1500))

    assert decision.status == "insufficient_evidence"
    assert decision.unresolved_conflicts == ("the worker enable isolation",)
    assert validate_evidence_sufficiency(decision, result_kind="patch_context") == []


def test_evaluator_only_requirement_provenance_is_rejected():
    with pytest.raises(ValueError, match="unsupported evidence requirement provenance"):
        select_evidence(
            [_candidate("source", "hidden fact")],
            question="Apply change",
            config=patch_selection_config(1500),
            public_requirements=[{
                "text": "hidden fact",
                "public_provenance": "hidden_test_answer",
            }],
        )


def test_stable_identity_collision_fails_closed_before_action_packet_rendering():
    candidates = [
        _candidate("same", "The worker must preserve isolation."),
        _candidate("same", "The worker must disable isolation."),
    ]
    decision = select_evidence(
        candidates, question="Update worker",
        config=patch_selection_config(1500),
    )
    packet = build_action_packet(
        question="Update worker", context_pack=candidates, max_tokens=1500,
    )

    assert decision.status == "insufficient_evidence"
    assert "stable_identity_collision:same" in decision.missing_requirements
    assert packet["status"] == "insufficient_evidence"


def test_requested_scope_rejects_candidates_with_missing_identity():
    decision = select_evidence(
        [_candidate("unknown", "Scoped fact.")],
        question="Explain scoped fact",
        config=docs_selection_config(800),
        project_identity="acme/project",
        module_id="runtime",
    )

    assert decision.status == "insufficient_evidence"
    assert any(item.reason_code == "outside_scope" for item in decision.omissions)


def test_exact_identifier_coverage_uses_boundaries_not_substrings():
    decision = select_evidence(
        [
            _candidate("prefix", "Call Auth.loginLegacy() for old clients."),
            _candidate("exact", "Call Auth.login() for current clients."),
        ],
        question="How do I call Auth.login?",
        config=docs_selection_config(800),
    )

    assert decision.status == "ok"
    assert _ids(decision) == ["exact"]


def test_non_legal_query_omits_legal_authority_from_visible_evidence():
    decision = select_evidence(
        [
            _candidate(
                "legal", "configure widget cache mode",
                source="legal/terms.md", authority="legal", retrieval_rank=1,
            ),
            _candidate(
                "config", "Set cache_mode in widget.toml.",
                source="docs/configuration.md", authority="canonical",
                retrieval_rank=2,
            ),
        ],
        question="configure widget cache mode",
        config=docs_selection_config(800),
    )

    assert decision.status == "ok"
    assert _ids(decision) == ["config"]
    assert any(
        item.stable_id == "legal" and item.reason_code == "query_intent_mismatch"
        for item in decision.omissions
    )


def test_legal_intent_can_select_legal_authority():
    decision = select_evidence(
        [
            _candidate(
                "legal", "The governing agreement uses Warsaw jurisdiction.",
                source="legal/terms.md", authority="legal",
            )
        ],
        question="What is the governing agreement jurisdiction?",
        config=docs_selection_config(800),
    )

    assert decision.status == "ok"
    assert _ids(decision) == ["legal"]


def test_patch_selection_omits_prefix_identifier_conflict_after_exact_match():
    decision = select_evidence(
        [
            _candidate(
                "legacy", "def loginLegacy(): pass",
                source="src/legacy_auth.py", symbols=["Auth.loginLegacy"],
                retrieval_rank=1,
            ),
            _candidate(
                "current", "def login(): pass",
                source="src/auth.py", symbols=["Auth.login"], retrieval_rank=2,
            ),
        ],
        question="Update Auth.login",
        config=patch_selection_config(1_500),
        required_target_paths=["src/auth.py"],
    )

    assert decision.status == "ok"
    assert _ids(decision) == ["current"]
    assert any(
        item.stable_id == "legacy"
        and item.reason_code == "query_identifier_conflict"
        for item in decision.omissions
    )


def test_malformed_rank_is_bounded_and_hashes_bind_scores_symbols_and_invalid_rows():
    base = _candidate("base", "Use Client.open().", retrieval_rank="not-an-int")
    first = select_evidence(
        [base], question="Use Client.open", config=docs_selection_config(800)
    )
    changed_score = select_evidence(
        [{**base, "score": 0.9}],
        question="Use Client.open", config=docs_selection_config(800),
    )
    changed_symbols = select_evidence(
        [{**base, "symbols": ["Client.open"]}],
        question="Use Client.open", config=docs_selection_config(800),
    )
    invalid_extra = _candidate("invalid", "bad", display_content_hash="0" * 64)
    with_invalid = select_evidence(
        [base, invalid_extra],
        question="Use Client.open", config=docs_selection_config(800),
    )

    assert first.selected_candidates[0].retrieval_rank == 10_000
    assert len({
        first.candidate_trace_hash,
        changed_score.candidate_trace_hash,
        changed_symbols.candidate_trace_hash,
        with_invalid.candidate_trace_hash,
    }) == 4
    assert first.selection_hash != changed_score.selection_hash
    assert with_invalid.audit_manifest()["omissions"] == [{
        "stable_id": "invalid",
        "reason_code": "invalid_identity",
        "representative_stable_id": None,
    }]


def test_project_usage_negation_does_not_prove_usage():
    question = "When should docs_status be used?"
    requirements = build_requirements(question, profile="project_docs_answer")
    decision = select_evidence(
        [_candidate("negative", "docs_status should not be used for health checks.")],
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )

    assert decision.support_decision.answer_supported is False
    usage = next(
        item for item in requirements
        if item.kind == "proof_obligation" and item.obligation_kind == "usage"
    )
    assert usage.requirement_id in decision.missing_requirements


def test_project_heading_with_colon_does_not_prove_exact_term():
    question = "Explain CONFIG_KEY"
    requirements = build_requirements(question, profile="project_docs_answer")
    decision = select_evidence(
        [_candidate("heading", "CONFIG_KEY:")],
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )

    assert decision.support_decision.answer_supported is False


def test_project_markdown_heading_does_not_prove_exact_term():
    question = "Explain MCP server"
    requirements = build_requirements(question, profile="project_docs_answer")
    decision = select_evidence(
        [_candidate("heading", "### Keep the MCP server responsive")],
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )

    assert decision.support_decision.answer_supported is False


def test_project_request_query_requires_mcp_server_as_well_as_request():
    requirements = build_requirements(
        "How does the MCP server process a tool request?",
        profile="project_docs_answer",
    )

    assert {value.casefold() for value in requirements.retrieval_hints} >= {
        "mcp server", "request",
    }
    relation = next(
        item for item in requirements
        if item.kind == "proof_obligation" and item.relation == "request_handling"
    )
    assert relation.subject == "MCP server"


@pytest.mark.parametrize(
    ("question", "complete", "incomplete", "facet"),
    [
        (
            "How does the MCP server process a tool request?",
            "The MCP server routes each tool request to a handler, which validates and dispatches it.",
            "The MCP server receives a tool request.",
            "request_handling",
        ),
        (
            "What is the architecture of the MCP server?",
            "The server routes requests through the transport to the handler service.",
            "The MCP server architecture has a service.",
            "architecture",
        ),
        (
            "What keeps the MCP server responsive?",
            "A background worker processes queued tasks asynchronously so the event loop does not block.",
            "The MCP server is responsive.",
            "responsiveness",
        ),
    ],
)
def test_project_relation_facets_require_a_concrete_mechanism(
    question, complete, incomplete, facet,
):
    requirements = build_requirements(question, profile="project_docs_answer")
    accepted = select_evidence(
        [_candidate("complete", complete)], question=question,
        config=project_docs_selection_config(800), requirements=requirements,
    )
    rejected = select_evidence(
        [_candidate("incomplete", incomplete)], question=question,
        config=project_docs_selection_config(800), requirements=requirements,
    )

    typed = next(
        item for item in requirements
        if item.kind == "proof_obligation" and item.relation == facet
    )
    assert typed.requirement_id in accepted.support_decision.satisfied_requirement_ids
    assignment = next(
        item for item in accepted.assignments
        if item.requirement_id == typed.requirement_id
    )
    assert assignment.unit_id
    assert assignment.unit_kind in {"sentence", "bullet", "table_row", "key_value", "code"}
    assert assignment.unit_char_start is not None
    assert assignment.unit_char_end is not None
    assert assignment.unit_char_end > assignment.unit_char_start
    assert assignment.unit_content_hash == assignment.projected_content_hash
    assert len(assignment.unit_content_hash or "") == 64
    assert typed.requirement_id in rejected.missing_requirements


def test_requirement_input_limits_are_bounded_and_fail_closed():
    question = "Show code for " + " ".join(
        f"Symbol_{index}" for index in range(20)
    )
    requirements = build_requirements(
        question,
        required_evidence_paths=[f"docs/evidence-{index}.md" for index in range(20)],
        required_target_paths=[f"src/target-{index}.py" for index in range(20)],
        public_requirements=[f"public fact {index}" for index in range(20)],
        library_requirement_contract={
            "code_groups": [[f"fragment_{index}"] for index in range(20)],
        },
        profile="library_docs_answer",
    )
    decision = select_evidence(
        [_candidate("candidate", "Symbol_0 and every public fact are documented.")],
        question=question,
        config=library_docs_selection_config(800),
        requirements=requirements,
    )

    assert len([item for item in requirements if item.kind == "evidence_path"]) == 12
    assert len([item for item in requirements if item.kind == "target_path"]) == 12
    assert len([item for item in requirements if item.requirement_id.startswith("public:")]) == 12
    assert len([item for item in requirements if item.kind == "code_group"]) == 6
    assert {item.requirement_id for item in requirements if item.requirement_id.startswith("input_limit:")} == {
        "input_limit:code_groups", "input_limit:identifiers", "input_limit:paths",
        "input_limit:public_requirements",
    }
    assert decision.support_decision.answer_supported is False
    assert "input_limit:paths" in decision.missing_requirements


def test_project_behavior_question_requires_behavior_for_every_entity():
    question = "What do get_docs_context and docs_status return?"
    requirements = build_requirements(question, profile="project_docs_answer")
    subjects = {
        item.subject for item in requirements
        if item.kind == "proof_obligation" and item.obligation_kind == "behavior"
    }

    assert subjects == {"get_docs_context", "docs_status"}

    decision = select_evidence(
        [_candidate("partial", "get_docs_context returns source-backed context and mentions docs_status.")],
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )
    assert decision.support_decision.answer_supported is False
    missing = next(
        item for item in requirements
        if item.kind == "proof_obligation"
        and item.obligation_kind == "behavior"
        and item.subject == "docs_status"
    )
    assert missing.requirement_id in decision.missing_requirements


def test_project_mechanism_how_question_does_not_require_workflow():
    question = "How does docs_status report index freshness?"
    requirements = build_requirements(question, profile="project_docs_answer")
    assert not any(
        item.kind == "proof_obligation" and item.obligation_kind == "workflow"
        for item in requirements
    )

    decision = select_evidence(
        [_candidate("answer", "docs_status reports index freshness from job records.")],
        question=question,
        config=project_docs_selection_config(800),
        requirements=requirements,
    )
    assert decision.support_decision.answer_supported is True


def test_requirement_set_rejects_conflicting_duplicate_ids():
    with pytest.raises(ValueError, match="conflicting evidence requirement ID: fact"):
        EvidenceRequirementSet((
            EvidenceRequirement("fact", "exact_term", "first"),
            EvidenceRequirement("fact", "exact_term", "second"),
        ))


def test_each_requirement_has_one_deterministic_witness():
    requirements = EvidenceRequirementSet((
        EvidenceRequirement("shared", "exact_term", "shared"),
        EvidenceRequirement("alpha", "exact_term", "alpha"),
        EvidenceRequirement("beta", "exact_term", "beta"),
    ))
    decision = select_evidence(
        [_candidate("second", "shared beta"), _candidate("first", "shared alpha")],
        question="shared alpha beta",
        config=docs_selection_config(800), requirements=requirements,
    )

    shared_witnesses = [
        assignment.evidence_id for assignment in decision.assignments
        if assignment.requirement_id == "shared"
    ]
    assert shared_witnesses == ["first"]


@pytest.mark.parametrize(
    ("question", "candidate", "facet"),
    [
        (
            "Explain the docs_status workflow",
            "docs_status then runs health checks.",
            "workflow:docs_status",
        ),
        (
            "What is the architecture of the MCP server?",
            "The MCP server exists. The service exists. Requests route through transport.",
            "architecture",
        ),
        (
            "What keeps the MCP server responsive?",
            "The MCP server is asynchronous. A worker handles metrics.",
            "responsiveness",
        ),
    ],
)
def test_relation_facets_reject_unrelated_or_single_step_matches(question, candidate, facet):
    requirements = build_requirements(question, profile="project_docs_answer")
    decision = select_evidence(
        [_candidate("partial", candidate)], question=question,
        config=project_docs_selection_config(800), requirements=requirements,
    )

    typed = next(
        item for item in requirements
        if item.kind == "proof_obligation"
        and (item.relation == facet or f"{item.obligation_kind}:{item.subject}" == facet)
    )
    assert typed.requirement_id in decision.missing_requirements
