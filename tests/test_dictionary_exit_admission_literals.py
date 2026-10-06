"""Bounded admission exit: unknown NL is not evidence or rewrite authority."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import re

import pytest

from docmancer.docs.domain import admission_local_binding as binding
from docmancer.docs.domain import admission_meaning as meaning
from docmancer.docs.domain import question_plan_core as core
from docmancer.docs.domain.admission_contract import (
    AdmissionDecision, HardGuards, LocalWitnessDecision, choose_admission,
    choose_need_admission,
)
from docmancer.docs.domain.admission_grammar import MeaningSlot, NEW_RELATIONS
from docmancer.docs.domain.answer_units import extract_answer_units, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references
from docmancer.docs.domain.question_frame_core import QuestionClause
from docmancer.docs.domain.question_retrieval_needs import RetrievalNeed


NL = (
    "What is RelayClient default timeout?",
    "What is RelayClient default retry delay duration when preview is not enabled?",
    "What is RelayClient default lease duration?",
    "What is RelayClient default timeout and retry delay?",
    "RelayClient uses timeouts everywhere. Its default behavior is to raise `Oops` after 7 seconds.",
    "Каков таймаут RelayClient по умолчанию, если режим отключён?",
    "the  Ω\u0301\tquux flurbs 🤖\n未知。",
    "", "   ",
)


@pytest.mark.parametrize("question", NL)
@pytest.mark.parametrize("legacy", [True, False])
def test_direct_unknown_admission_cannot_use_legacy_credit(question, legacy):
    body = 'RelayClient.timeout = "7 seconds"'
    decision, witness = choose_need_admission(
        {"query_text": question, "query_origin": "retrieval_need",
         "need_relation": "default", "need_subject": "RelayClient",
         "qualified": True, "need_local_witness": True},
        query_id="query-need-1", text=body, legacy_qualified=legacy, missing_exact=(),
    )
    assert not decision.admitted and decision.route == "rejected"
    assert decision.reason == "unverified_local_demand"
    assert witness.status == "unknown" and witness.spans == ()
    assert witness.source_key == hashlib.sha256(body.encode()).hexdigest()
    assert decision.matched_need_ids == ()


@pytest.mark.parametrize("question", NL)
def test_default_binding_helpers_do_not_nominate_or_infer_values(question):
    query = {"text": question, "need_subject": "RelayClient", "need_attribute": "timeout"}
    body = "# RelayClient\nThe default timeout is 7 seconds."
    assert binding.default_property(query) is None
    assert binding.bound_default_units(query, body) is None
    assert binding.default_local_witness(query, body) == (None, ())
    assert binding._condition(question) is None
    assert binding._conditioned_clause(question, None) is None
    assert not binding._discourse_value_is_local(question, "timeout")
    assert not binding._value_is_local(re.match(r"(?P<value>.*)", question), "timeout")
    assert re.search(binding._assignment("timeout", "RelayClient"), question) is None


@pytest.mark.parametrize("status", ["unknown", "absent", "matched"])
def test_hard_guards_precede_every_witness(status):
    decision = choose_admission(HardGuards(False, ("stale_evidence",)),
        legacy_qualified=True, witness=LocalWitnessDecision(status, "n", "s", ((0, 4),)))
    assert not decision.admitted and decision.reason == "stale_evidence"


@pytest.mark.parametrize("witness", [
    LocalWitnessDecision("unknown", "n", "s"),
    LocalWitnessDecision("absent", "n", "s"),
    LocalWitnessDecision("matched", "n", "s"),
    LocalWitnessDecision("matched", "", "s", ((0, 4),)),
    LocalWitnessDecision("matched", "n", "", ((0, 4),)),
    LocalWitnessDecision("matched", "n", "s", ((0, 0),)),
    LocalWitnessDecision("matched", "n", "s", ((-1, 4),)),
])
def test_empty_unknown_and_invalid_witnesses_are_not_all_pass(witness):
    assert not choose_admission(HardGuards(True), legacy_qualified=True, witness=witness).admitted


def test_explicit_nonempty_witness_and_immutable_dtos_remain_available():
    witness = LocalWitnessDecision("matched", "n", "s", ((0, 4),))
    result = choose_admission(HardGuards(True), legacy_qualified=False, witness=witness)
    assert result == AdmissionDecision(True, "typed_local", "verified_local_demand", ("n",))
    for obj, attr in ((witness, "status"), (result, "reason"), (HardGuards(True), "allowed")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, None)
    with pytest.raises(ValueError):
        HardGuards(False)


@pytest.mark.parametrize("gap", ["and", "and also", "while also", "as well as", "along with",
    "but", "plus", "then", "also", "и", "и также", "а также", "но", "плюс", "затем", "🤖", "未知"])
def test_conjunctions_and_unknown_unicode_are_unresolved_coverage(gap):
    question = "A " + gap + " B"
    plan = core.QuestionPlan((core.PlannedFacet("definition", "A"),),
        consumed_spans=((0, 1), (len(question)-1, len(question))))
    assert not core._safe_coverage_gap(gap)
    result = core._finalize_full_span_coverage(question, plan)
    assert result.unresolved_parts == ("unresolved_question_clause: " + gap + " ",)
    assert result.parse_trace[-1] == "fail_closed:unconsumed_span"
    assert result.consumed_spans == plan.consumed_spans


@pytest.mark.parametrize("gap", ["", " ", "\t\n", ",;:.!?/", " — – "])
def test_only_structural_punctuation_can_be_uncovered(gap):
    assert core._safe_coverage_gap(gap)
    question = "A" + gap + "B"
    plan = core.QuestionPlan((core.PlannedFacet("definition", "A"),),
        consumed_spans=((0, 1), (len(question)-1, len(question))))
    assert core._finalize_full_span_coverage(question, plan) is plan


@pytest.mark.parametrize("text", ["the Widget", "a Widget", "an API", "  Ω\u0301\t未知\n🤖?!  "])
def test_core_literal_helpers_keep_original_unicode_and_budget(text):
    assert core._clean(text).encode() == text.encode()
    clause = QuestionClause(text, 0, len(text))
    for compound in (False, True):
        assert core._normalized_clause(clause, compound=compound).encode() == text.encode()
    assert core._technical(text)[0] == text
    assert core._clean("Ω" * 200) == "Ω" * 160


def test_span_binding_validation_and_negative_missing_coverage_remain():
    question = "  `Widget`\nΩ."
    clause = QuestionClause(question, 0, len(question))
    plan = core.QuestionPlan((core.PlannedFacet("definition", "Widget"),))
    bound = core._bind_plan_to_clause(plan, clause)
    facet = bound.facets[0]
    assert question[facet.query_span_start:facet.query_span_end] == "Widget"
    assert bound.consumed_spans == ((0, len(question)),)
    assert core._finalize_full_span_coverage(question, plan).unresolved_parts
    with pytest.raises(ValueError):
        replace(facet, query_span_start=-1)
    with pytest.raises(ValueError):
        replace(bound, consumed_spans=((0, 0),))
    with pytest.raises(FrozenInstanceError):
        bound.parse_trace = ()
    assert core._unsafe_free_text("unknown extra request")


@pytest.mark.parametrize("question", NL)
def test_meaning_compilation_keeps_unknown_original_spans_and_no_reflexive_credit(question):
    refs = resolve_references(question, catalog=(), scope=ScopeKey("", "", ""))
    demands = meaning.compile_admission_demands(question, refs)
    if question.strip():
        assert len(demands) == 1
        demand = demands[0]
        assert demand.operator == "unknown" and demand.unsupported_spans == ((0, len(question)),)
        assert demand.need.query_span_text.encode() == question.encode()
        assert not meaning.same_supported_meaning(demand, demand)
    else:
        assert demands == ()
    assert not meaning.questions_have_same_supported_meaning(question, question)


@pytest.mark.parametrize("operator", sorted(NEW_RELATIONS) + ["unknown", "", "default"])
def test_supplied_equal_typed_slots_do_not_certify_nl_equivalence(operator):
    need = RetrievalNeed("n", 0, 6, "Widget", "Widget", operator, "", ())
    slot = MeaningSlot("subject", 0, 6, "Widget", "Widget")
    for arguments in ((), (slot,)):
        demand = meaning.AdmissionDemand(need, operator, arguments, (), ())
        assert not meaning.same_supported_meaning(demand, demand)


@pytest.mark.parametrize("residue", [" 🤖 ", " Ω\u0301 ", " and ", " ; "])
def test_omitted_residue_uses_structural_not_word_only_coverage(monkeypatch, residue):
    question = "A" + residue
    need = RetrievalNeed("n", 0, 1, "A", "", "unresolved", "", ())
    monkeypatch.setattr(meaning, "retrieval_needs", lambda _: (need,))
    refs = resolve_references(question, catalog=(), scope=ScopeKey("", "", ""))
    demands = meaning.compile_admission_demands(question, refs)
    if core._safe_coverage_gap(residue):
        assert len(demands) == 1
    else:
        assert len(demands) == 2
        assert demands[1].need.query_span_text.encode() == residue.encode()
        assert demands[1].unsupported_spans == ((1, len(question)),)


@pytest.mark.parametrize("value", ["false", "17 ms", "^3.11", "/tmp/opencode", "Ω\u0301"])
def test_narrow_typed_literal_evidence_remains_exact(value):
    text = f'Widget.value = "{value}"'
    unit = extract_answer_units(text)[0]
    obligation = ProofObligation("literal", "exact_fact", "Widget", attribute="value",
        subject_kind="config_key", expected_value=value)
    proof = local_proof_for_obligation(obligation, unit)
    assert proof.valid and proof.reason == "explicit_literal_value_only"
    assert unit.text.encode() == text.encode()
    assert unit.content_sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert not local_proof_for_obligation(replace(obligation, expected_value=value + "!"), unit).valid
    assert not local_proof_for_obligation(replace(obligation, subject="Other"), unit).valid


def test_application_adapter_really_calls_default_hook_but_unknown_is_consumer_debt(monkeypatch):
    from docmancer.docs.application import retrieval_need_support as consumer
    calls = []
    real = consumer.default_local_witness
    def observed(query, text):
        calls.append((query, text))
        return real(query, text)
    monkeypatch.setattr(consumer, "default_local_witness", observed)
    query = {"query_origin": "retrieval_need", "need_relation": "default", "text": NL[0]}
    trace = {"qualified": True, "qualification_reason": "legacy"}
    result = consumer.apply_retrieval_need_witness(query, trace, "RelayClient timeout is 7 seconds.")
    assert len(calls) == 1
    assert result == trace  # Record the non-owned unknown-veto debt, not approval proof.
    assert "need_local_witness" not in result


def test_real_qualifier_rejects_old_need_lane_before_default_hook(monkeypatch):
    from docmancer.docs.application import retrieval_need_support as consumer
    from docmancer.docs.domain.evidence_qualification import qualify_evidence
    def forbidden(*args, **kwargs):
        pytest.fail("default adapter is not on this default qualification path")
    monkeypatch.setattr(consumer, "default_local_witness", forbidden)
    result = qualify_evidence({"query_origin": "retrieval_need", "query_text": NL[0],
        "need_relation": "default", "qualified": True, "need_local_witness": True},
        query_id="query-need-1", visible_text="RelayClient default timeout is 7 seconds.")
    assert not result.qualified and result.reason == "query_contract_mismatch"
    assert not result.trace.get("need_local_witness")


def test_public_compiler_does_not_execute_imported_core_coverage_rule(monkeypatch):
    from docmancer.docs.domain import question_plan as compiler
    def forbidden(*args, **kwargs):
        pytest.fail("an imported helper is not proof of compiler execution")
    monkeypatch.setattr(compiler, "_finalize_full_span_coverage", forbidden)
    question = "the  Ω\u0301\tAPI and unknown 🤖"
    plan = compiler.compile_question_plan(question)
    assert not plan.facets and plan.unresolved_parts
    assert plan.clauses == (question,) and not plan.component_scope_complete
