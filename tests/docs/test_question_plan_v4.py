from __future__ import annotations


from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
    build_project_answer_contract,
    can_authorize_docs_answer,
)
from docmancer.docs.domain.technical_terms import coerce_technical_term, technical_term_present


def _rows(question: str):
    contract = build_project_answer_contract(question)
    assert contract.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA_V4
    return contract, contract.proof_obligations


def _unit(text: str, *, kind: str = "sentence") -> AnswerUnit:
    import hashlib
    return AnswerUnit(
        unit_id="unit-test",
        kind=kind,
        text=text,
        char_start=0,
        char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        proposition=True,
    )


def test_code_symbol_aliases_may_widen_retrieval_but_not_proof_shape():
    symbol = coerce_technical_term("foo_bar", "code_symbol")
    assert technical_term_present(symbol, "The foo bar feature is enabled.", require_kind_shape=True) is False
    assert technical_term_present(symbol, "The `foo_bar` symbol is enabled.", require_kind_shape=True) is True


def test_code_block_units_preserve_exact_source_spans_for_projection():
    from docmancer.docs.domain.answer_units import extract_answer_units, materialize_answer_units

    source = "   ```bash\n   python -m example \\n     --flag\n   ```\n\n"
    units = extract_answer_units(source)
    block = next(unit for unit in units if unit.kind == "code_block")
    assert source[block.char_start:block.char_end] == block.text
    assert materialize_answer_units(source, (block,)) == block.text
