from docmancer.docs.domain.project_retrieval_intent import build_project_retrieval_aliases


def _aliases(question: str):
    return build_project_retrieval_aliases(question)


def test_docs_mcp_sequence_targets_the_public_contract_flow():
    aliases = _aliases(
        "What is the recommended sequence of MCP tool calls for answering a normal project documentation question?"
    )
    workflow = [row for row in aliases if row.intent_id == "docs_mcp_workflow"]

    assert workflow
    assert any("public tool contract normal flow sequence" in row.text.casefold() for row in workflow)
    assert all("packs" not in row.text.casefold() for row in workflow)


def test_current_docs_mcp_tool_policy_targets_default_use_without_inventing_policy_for_location():
    for tool, question in (
        ("get_docs_context", "When should an agent use get_docs_context?"),
        ("prepare_docs", "When is an agent allowed to call prepare_docs?"),
        ("docs_status", "What requests should use docs_status, and when must it not be used?"),
    ):
        aliases = _aliases(question)
        policy = [row for row in aliases if row.intent_id == "docs_mcp_tool_policy"]
        assert policy
        assert any(tool in row.text and "public tool contract default use" in row.text.casefold() for row in policy)

    assert not any(
        row.intent_id == "docs_mcp_tool_policy"
        for row in _aliases("Where is prepare_docs implemented in this repository?")
    )


def test_implementation_location_is_a_relation_not_any_code_symbol_or_config_location():
    aliases = _aliases("Where is the public Docs MCP server implemented in this repository?")
    locations = [row for row in aliases if row.intent_id == "implementation_location"]

    assert len(locations) == 1
    assert "docs mcp server implementation location source path" in locations[0].text.casefold()
    assert "project_architecture" in locations[0].preferred_catalog_roles
    assert not any(
        row.intent_id == "implementation_location"
        for row in _aliases("What are the public tools exposed by the Docs MCP server?")
    )
    config = _aliases("Where is the project docs configuration located?")
    assert any(row.intent_id == "project_docs_config_location" for row in config)
    assert not any(row.intent_id == "implementation_location" for row in config)


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
    sync = next(row for row in aliases if row.intent_id == "project_docs_sync")

    for state in ("new", "changed", "stale", "deleted"):
        assert state in sync.text.casefold()

    generic = next(
        row for row in _aliases("How do I sync project documentation?")
        if row.intent_id == "project_docs_sync"
    )
    assert all(state not in generic.text.casefold() for state in ("new", "changed", "stale", "deleted"))
