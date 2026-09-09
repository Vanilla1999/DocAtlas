from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


def _aliases(question: str):
    return build_project_retrieval_aliases(question)


def test_docs_mcp_sequence_keeps_generic_workflow_and_normal_flow_probes():
    aliases = _aliases(
        "What is the recommended sequence of MCP tool calls for answering a normal project documentation question?"
    )
    workflow = [row for row in aliases if row.intent_id == "docs_mcp_workflow"]

    assert workflow
    assert any(
        all(name in row.text for name in ("get_docs_context", "prepare_docs", "docs_status"))
        for row in workflow
    )
    assert any("normal flow" in row.text.casefold() for row in workflow)
    assert all("packs" not in row.text.casefold() for row in workflow)


def test_generic_docs_mcp_workflow_question_still_has_a_surface_level_probe():
    workflow = [
        row for row in _aliases("Как устроен полный процесс работы Docs MCP?")
        if row.intent_id == "docs_mcp_workflow"
    ]

    assert workflow
    assert any(
        "docs mcp server workflow" in row.text.casefold()
        and "get_docs_context" in row.text
        and "prepare_docs" in row.text
        and "docs_status" in row.text
        for row in workflow
    )


def test_current_docs_mcp_tool_policy_targets_default_use_without_inventing_policy_for_location():
    for tool, question in (
        ("get_docs_context", "When should an agent use get_docs_context?"),
        ("prepare_docs", "When is an agent allowed to call prepare_docs?"),
        ("docs_status", "What requests should use docs_status, and when must it not be used?"),
    ):
        aliases = _aliases(question)
        policy = [row for row in aliases if row.intent_id == "docs_mcp_tool_policy"]
        assert policy
        assert any(tool in row.text and "default use" in row.text.casefold() for row in policy)
        assert "overview" in policy[0].preferred_catalog_roles

    prepare = [
        row for row in _aliases("When is an agent allowed to call prepare_docs?")
        if row.intent_id == "docs_mcp_tool_policy"
    ]
    assert any("allowed lifecycle action" in row.text.casefold() for row in prepare)
    assert any("network approval confirmation" in row.text.casefold() for row in prepare)
    assert not any("must not" in row.text.casefold() for row in prepare)

    status_policy = [
        row for row in _aliases("What requests should use docs_status, and when must it not be used?")
        if row.intent_id == "docs_mcp_tool_policy"
    ]
    assert any("must not" in row.text.casefold() for row in status_policy)

    assert not any(
        row.intent_id == "docs_mcp_tool_policy"
        for row in _aliases("Where is prepare_docs implemented in this repository?")
    )


def test_product_overview_splits_identity_from_purpose_without_answer_hardcoding():
    overview = [
        row for row in _aliases(
            "What is DocAtlas, and what core problem is it designed to solve for coding agents?"
        )
        if row.intent_id == "product_overview"
    ]

    assert any("documentation context runtime" in row.text.casefold() for row in overview)
    assert any("product purpose problem" in row.text.casefold() for row in overview)


def test_implementation_location_is_a_relation_not_any_code_symbol_or_config_location():
    aliases = _aliases("Where is the public Docs MCP server implemented in this repository?")
    locations = [row for row in aliases if row.intent_id == "implementation_location"]

    assert locations
    assert len(locations) == 1
    assert "mcp docs server area responsibility" in locations[0].text.casefold()
    assert all("docmancer/mcp/docs_server.py" not in row.text for row in locations)
    assert "project_architecture" in locations[0].preferred_catalog_roles
    assert not any(
        row.intent_id == "implementation_location"
        for row in _aliases("What are the public tools exposed by the Docs MCP server?")
    )
    config = _aliases("Where is the project docs configuration located?")
    assert any(row.intent_id == "project_docs_config_location" for row in config)
    assert not any(row.intent_id == "implementation_location" for row in config)


def test_product_boundaries_use_relation_not_the_known_inventory():
    boundaries = [
        row for row in _aliases("What systems does DocAtlas explicitly not replace?")
        if row.intent_id == "product_boundaries"
    ]

    assert boundaries
    assert any(
        "product boundaries" in row.text.casefold()
        and "does not replace" in row.text.casefold()
        for row in boundaries
    )
    forbidden_answers = ("memory", "lsp", "static analysis", "web search")
    assert all(
        answer not in row.text.casefold()
        for row in boundaries
        for answer in forbidden_answers
    )


def test_fail_closed_definition_targets_context_contract_not_incident_diagnostics():
    aliases = _aliases("What does fail-closed behavior mean in the DocAtlas documentation workflow?")

    assert any(row.intent_id == "fail_closed_workflow" for row in aliases)
    assert any("insufficient_evidence" in row.text.casefold() for row in aliases)
    assert any("safe retrieval-only context" in row.text.casefold() for row in aliases)
    assert not any(row.intent_id == "troubleshooting" for row in aliases)


def test_product_claims_targets_claim_status_not_the_document_title():
    aliases = _aliases(
        "What claims about DocAtlas are not currently demonstrated according to the product brief?"
    )
    claims = [row for row in aliases if row.intent_id == "product_claims"]

    assert claims
    assert any("product claims evidence status demonstrated" in row.text.casefold() for row in claims)
    assert all("product brief" not in row.text.casefold() for row in claims)
    assert not any(
        row.intent_id == "product_claims"
        for row in _aliases("Which product brief file should I edit?")
    )


def test_sync_alias_preserves_only_states_explicitly_asked_by_the_user():
    aliases = _aliases(
        'What does prepare_docs(action="sync_project_docs") do to new, changed, stale, and deleted project documentation?'
    )
    sync = [row for row in aliases if row.intent_id == "project_docs_sync"]

    assert sync
    assert all("overview" in row.preferred_catalog_roles for row in sync)
    assert not any(row.intent_id == "troubleshooting" for row in aliases)
    state_probe = next(
        row for row in sync
        if all(state in row.text.casefold() for state in ("new", "changed", "stale", "deleted"))
    )
    assert "sync_project_docs" not in state_probe.text
    assert "project docs" in state_probe.text.casefold()

    generic = next(
        row for row in _aliases("How do I sync project documentation?")
        if row.intent_id == "project_docs_sync"
    )
    assert all(state not in generic.text.casefold() for state in ("new", "changed", "stale", "deleted"))
