"""Cross-owner v4 regressions; no historical compatibility assertions."""
from copy import deepcopy
import hashlib
import json

import pytest

from docmancer.docs.application.action_packet import (
    build_action_packet,
    estimate_action_packet_tokens,
    validate_action_packet,
)
from docmancer.docs.application.model_visible_projection import (
    project_patch_context,
    validate_model_visible_projection,
)

pytestmark = pytest.mark.behavioral


def _window(index, text):
    return {
        "path": f"docs/reference-{index}.md",
        "source_class": "project_doc",
        "doc_scope": "project",
        "content": text,
        "snippet": text,
        "display_text": text,
        "stable_chunk_id": f"v4-integrated-child-{index}",
        "parent_logical_id": f"v4-integrated-parent-{index}",
        "char_start": 0,
        "char_end": len(text),
        "line_start": 1,
        "line_end": text.count("\n") + 1,
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "version": "2.0",
        "authority": "supporting",
        "retrieval_rank": index + 1,
    }


def test_failure_preserves_all_explicit_target_requirements_without_legacy_dto():
    paths = [f"src/component_{i}.py" for i in range(18)]
    paths.append("src/" + "идентификатор_" * 50 + ".py")
    packet = build_action_packet(
        question="reference", context_pack=[], required_target_paths=paths,
    )
    assert packet["result"] == "failure"
    assert packet["completeness"] == "unavailable"
    assert packet["edit_ready"] is False
    assert "mutation_intent" not in packet
    targets = {row["value"] for row in packet["requirements"] if row["kind"] == "target_path"}
    assert targets == set(paths)
    assert validate_action_packet(packet, evidence_items=[]) == []
    projection, snapshot = project_patch_context(packet=packet, evidence_items=[])
    assert projection["requirements"] == packet["requirements"]
    assert validate_model_visible_projection(projection, snapshot=snapshot) == []


def test_mixed_evidence_partial_result_keeps_supplied_obligations_and_unicode():
    text = "Режим доставки: уникальные сообщения сохраняются вместе с source binding."
    item = _window(0, text)
    requirements = [
        {"kind": "required_fact", "value": text},
        {"kind": "required_fact", "value": "An absent independent requirement."},
    ]
    packet = build_action_packet(
        question="reference", context_pack=[item], public_requirements=requirements,
    )
    assert packet["result"] == "data" and packet["completeness"] == "partial"
    assert packet["sources"][0]["text"] == text
    assert {row["value"] for row in packet["requirements"] if row["kind"] == "required_fact"} == {
        requirement["value"] for requirement in requirements
    }
    assert packet["missing"]
    assert validate_action_packet(packet, evidence_items=[item]) == []
    projected, snapshot = project_patch_context(packet=packet, evidence_items=[item])
    assert projected["result"] == "data" and projected["completeness"] == "partial"
    assert projected["sources"] == packet["sources"]
    assert validate_model_visible_projection(projected, snapshot=snapshot) == []
    encoded = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert projected["estimated_tokens"] == max(1, (len(encoded) + 3) // 4)


def test_unique_witnesses_survive_permutation_and_exact_input_duplicates():
    texts = [f"Component {i} retains the independent binding for operation {i}." for i in range(4)]
    items = [_window(i, text) for i, text in enumerate(texts)]
    kwargs = {"question": "reference", "public_requirements": texts}
    packet = build_action_packet(context_pack=items, **kwargs)
    permuted = build_action_packet(context_pack=list(reversed(items)), **kwargs)
    repeated = build_action_packet(context_pack=[*items, deepcopy(items[1])], **kwargs)
    assert packet == permuted == repeated
    assert {row["text"] for row in packet["sources"]} == set(texts)
    assert packet["estimated_tokens"] == estimate_action_packet_tokens(packet)
    assert validate_action_packet(packet, evidence_items=items) == []


def test_removed_budget_arguments_are_not_silently_ignored():
    with pytest.raises(TypeError):
        build_action_packet(question="reference", context_pack=[], max_tokens=128)
    packet = build_action_packet(question="reference", context_pack=[])
    with pytest.raises(TypeError):
        validate_action_packet(packet, max_tokens=2000)
    with pytest.raises(TypeError):
        project_patch_context(packet=packet, evidence_items=[], max_tokens=2000)


def test_distinct_explicit_literal_requirements_are_not_casefolded_away():
    texts = ["Cache enabled.", "cache enabled."]
    evidence = [_window(index, text) for index, text in enumerate(texts)]
    packet = build_action_packet(
        question="reference", context_pack=evidence, public_requirements=texts,
    )
    assert {row["value"] for row in packet["requirements"]} == set(texts)
    assert packet["completeness"] == "complete"
    assert len(packet["assignments"]) == len(texts)
    assert validate_action_packet(packet, evidence_items=evidence) == []


def test_distinct_indexed_character_windows_have_unambiguous_snapshot_ids():
    text = "Cache enabled."
    first = _window(0, text)
    second = {
        **first, "stable_chunk_id": "different-window-child",
        "char_start": 100, "char_end": 100 + len(text),
    }
    evidence = [first, second]
    packet = build_action_packet(
        question="reference", context_pack=evidence, public_requirements=[text],
    )
    assert len(packet["sources"]) == 2
    assert len({row["evidence_id"] for row in packet["sources"]}) == 2
    projected, snapshot = project_patch_context(packet=packet, evidence_items=evidence)
    assert projected["sources"] == packet["sources"]
    assert validate_model_visible_projection(projected, snapshot=snapshot) == []
