from __future__ import annotations

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import (
    PROJECT_ANSWER_CONTRACT_SCHEMA,
    PROJECT_ANSWER_CONTRACT_SCHEMA_V2,
    ProofObligation,
    build_project_answer_contract,
    can_authorize_docs_answer,
)


def _obligations(question: str):
    contract = build_project_answer_contract(question)
    return contract, contract.proof_obligations


def _unit(text: str) -> AnswerUnit:
    import hashlib
    return AnswerUnit(
        unit_id="contract-v3", kind="sentence", text=text,
        char_start=0, char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(), proposition=True,
    )


def test_v3_purpose_contracts_extract_bounded_subject_context_and_technical_aliases():
    quarantine, rows = _obligations("What is the quarantine feature in index cleanup?")
    assert quarantine.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA
    assert len(rows) == 1
    assert (rows[0].kind, rows[0].subject, rows[0].context, rows[0].response_mode) == (
        "purpose", "quarantine", "index cleanup", "purpose",
    )

    flag, rows = _obligations("What is allow_incomplete in clear-index?")
    assert flag.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA
    assert len(rows) == 1
    assert rows[0].kind == "purpose"
    assert rows[0].subject == "--allow-incomplete"
    assert rows[0].subject_kind == "cli_flag"
    assert {"--allow-incomplete", "allow_incomplete"}.issubset(rows[0].subject_aliases)
    assert rows[0].context == "clear-index"

    home, rows = _obligations("What is DOCATLAS_HOME used for?")
    assert home.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA
    assert len(rows) == 1
    assert (rows[0].kind, rows[0].subject_kind, rows[0].response_mode) == (
        "purpose", "env_var", "purpose",
    )
    assert rows[0].subject == "DOCATLAS_HOME"


def test_v3_supported_values_and_coordinated_effects_are_explicit_mandatory_facets():
    scopes, rows = _obligations("Which scopes does clear-index support?")
    assert scopes.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA
    assert len(rows) == 1
    assert (rows[0].kind, rows[0].subject, rows[0].attribute) == (
        "inventory", "clear-index", "scope",
    )
    assert rows[0].item_kind == "scope"
    assert rows[0].response_mode == "names"
    assert rows[0].subject_kind == "cli_command"

    effects, rows = _obligations("What does clear-index delete and preserve?")
    assert effects.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA
    assert len(rows) == 2
    assert [row.kind for row in rows] == ["effect", "effect"]
    assert [row.relation for row in rows] == ["delete", "preserve"]
    assert all(row.mandatory and row.subject == "clear-index" for row in rows)


def test_v2_questions_remain_on_the_frozen_contract_schema():
    contract = build_project_answer_contract("How many public MCP tools does DocAtlas expose?")
    assert contract.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA_V2
    assert len(contract.proof_obligations) == 1
    assert contract.proof_obligations[0].kind == "inventory"
    assert contract.proof_obligations[0].response_mode == "count"


def test_v3_does_not_reclassify_frozen_v2_config_questions():
    expected = {
        "What is the default query budget in docmancer.yaml?": (
            "fdc51fc235885c6af48517d9a85f653793ab3a5410d9e02c0a90a7d02d98ad20",
            "872c4a962af59af8078cfc62075a04c56b6bcfce7aed6c4a191ae61027196313",
        ),
        "What is the default indexing provider in docmancer.yaml?": (
            "5a5b5fdd3cfc118d625d0d6c6e776a201a6116dff7ca38374c0f6030353d0577",
            "e55ff49411a7977dd77e9573a2580701ce69fa6496cc95dac63e35f3da4e5286",
        ),
    }
    for question, (contract_hash, requirements_hash) in expected.items():
        contract = build_project_answer_contract(question)
        requirements = build_requirements(question, profile="project_docs_answer")
        assert contract.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA_V2
        assert contract.contract_hash == contract_hash
        assert requirements.requirements_hash == requirements_hash


def test_answer_authorization_requires_a_query_bound_pascal_identity():
    assert can_authorize_docs_answer(
        build_project_answer_contract("What is OrdersDraftStore?")
    ) is True
    for broad_subject in ("Storage", "Project", "Architecture", "Readme"):
        assert can_authorize_docs_answer(
            build_project_answer_contract(f"What is {broad_subject}?")
        ) is False


def test_named_behavior_preserves_requested_operation_qualifier():
    obligation = build_project_answer_contract(
        "What does OrderSubmission return?"
    ).proof_obligations[0]
    assert obligation.expected_value == "return"
    assert obligation.target is None
    assert local_proof_for_obligation(
        obligation, _unit("OrderSubmission validates drafts."),
    ).valid is False
    assert local_proof_for_obligation(
        obligation, _unit("OrderSubmission returns a submission ID."),
    ).valid is True


def test_filesystem_path_tokens_cannot_supply_behavior_subject_predicate_or_value():
    obligation = ProofObligation(
        obligation_id="behavior:docatlas",
        kind="behavior",
        subject="DocAtlas",
    )

    proof = local_proof_for_obligation(
        obligation,
        _unit("Call logs are written to ~/.docatlas/mcp/calls.jsonl."),
    )

    assert proof.valid is False
