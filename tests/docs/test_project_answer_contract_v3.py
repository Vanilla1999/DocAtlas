from __future__ import annotations

from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import ProofObligation


def _unit(text: str) -> AnswerUnit:
    import hashlib
    return AnswerUnit(
        unit_id="contract-v3", kind="sentence", text=text,
        char_start=0, char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(), proposition=True,
    )


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
