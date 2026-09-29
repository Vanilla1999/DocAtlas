"""M0 — RED: first packet must carry the negative-name rule without read_next.

Three end-to-end tests through the real handler + projection pipeline:

1. Mixed RU+EN question  — expected ASSERTION_FAIL (lexical mismatch).
2. Pure RU question       — expected ASSERTION_FAIL (no candidates or mismatch).
3. English control        — expected PASS.

Plus a packaging positive control that re-runs the projector on the English
query's own projector input to verify the finalizer can fit the gold passage
into a valid <=800-token DTO.  This isolates packaging capacity from retrieval.
"""
from __future__ import annotations

import pytest

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens


GOLD_PHRASES = (
    "only *CLI option* names to set the `False` value",
    "use a space and a single `/` and pass the negative name after",
)

MIXED_RU_QUESTION = (
    "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
)
PURE_RU_QUESTION = (
    "Как записать только отрицательное имя логического параметра: "
    "важен ли пробел перед косой чертой?"
)
EN_QUESTION = (
    "How to declare only the negative name for a boolean option: "
    "is the space before / significant?"
)


def _typer_project(tmp_path):
    _, _, manifest = load_protocol()
    docs = documents_for("typer", manifest)
    root = tmp_path / "project"
    write_project(root, docs)
    return root


def _call(service, root, question):
    request = {"question": question, "project_path": str(root), "scope": "all"}
    payload, trace = observe_call(service, request)
    return payload, trace


def _assert_gold_in_first_packet(payload):
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    for phrase in GOLD_PHRASES:
        assert phrase in visible, f"gold phrase missing from first packet: {phrase!r}"
    assert docs_context_budget_tokens(payload) <= 800
    assert payload["answer_supported"] is False
    assert payload.get("edit_ready", False) is False


# ---------------------------------------------------------------------------
# Test 1 — mixed RU+EN question (expected RED)
# ---------------------------------------------------------------------------
def test_mixed_russian_first_packet_carries_negative_name_rule(tmp_path):
    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        payload, _trace = _call(service, root, MIXED_RU_QUESTION)
    _assert_gold_in_first_packet(payload)


# ---------------------------------------------------------------------------
# Test 2 — pure RU question (expected RED)
# ---------------------------------------------------------------------------
def test_pure_russian_first_packet_carries_negative_name_rule(tmp_path):
    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        payload, _trace = _call(service, root, PURE_RU_QUESTION)
    _assert_gold_in_first_packet(payload)


# ---------------------------------------------------------------------------
# Test 3 — English control (expected PASS)
# ---------------------------------------------------------------------------
def test_english_first_packet_control(tmp_path):
    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        payload, _trace = _call(service, root, EN_QUESTION)
    _assert_gold_in_first_packet(payload)


# ---------------------------------------------------------------------------
# Packaging positive control — finalizer can fit the gold passage (diagnostic)
# ---------------------------------------------------------------------------
def test_packaging_control_english_projector_output(tmp_path):
    """Re-run the projector on the English query's own projector input.

    If the English control passes, this is redundant.  If it fails, this test
    helps localise: if the projector input contains a gold phrase but the
    output does not, the issue is packaging, not retrieval.  If the projector
    input lacks the gold passage, the issue is retrieval (BLOCKED here).
    """
    from docmancer.docs.application import docs_context_projection as projection

    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        _payload, trace = _call(service, root, EN_QUESTION)

    inputs = trace.get("stages", {}).get("projector_inputs", [])
    assert len(inputs) == 1, f"expected exactly 1 projector input, got {len(inputs)}"
    projector_input = inputs[0]

    # Check whether retrieval delivered the gold passage to the projector.
    input_text = "\n".join(
        str(c.get("display_text") or c.get("text") or "")
        for c in (projector_input.get("context_pack") or [])
    )
    if not any(phrase in input_text for phrase in GOLD_PHRASES):
        pytest.skip(
            "retrieval did not deliver gold passage to projector; "
            "packaging capacity not testable (BLOCKED at retrieval)"
        )

    # Re-run the projector in isolation.
    out, snapshot = projection.project_docs_context(
        retrieval=projector_input, max_tokens=800
    )
    visible = "\n\n".join(s["snippet"] for s in out.get("sources", []))
    for phrase in GOLD_PHRASES:
        assert phrase in visible, f"packaging lost gold phrase: {phrase!r}"
    assert docs_context_budget_tokens(out) <= 800
