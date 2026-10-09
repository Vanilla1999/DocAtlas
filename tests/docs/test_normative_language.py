from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from docmancer.docs.application.action_packet import (
    build_action_packet,
    evidence_identity_for_item,
    refresh_action_packet_estimate,
    validate_action_packet,
)
from docmancer.docs.application.evidence_selection import requirement_value_visible
from docmancer.docs.domain.normative_language import (
    classify_normative_modality,
    python_declaration_line_indexes,
)


_PYTHON_DECLARATION_CASES = frozenset({
    "import required",
    "import required as alias",
    "from pkg import required",
    "from pkg.sub import required",
    "from pkg import required as alias",
    "from pkg import (required, optional)",
    "from модуль import required",
    "from . import required",
    "from .pkg import required",
    "from .. import required",
    "from ..pkg import required",
    "from ...pkg.sub import forbidden",
    "def must(): pass",
    "async def required(): pass",
    "class Required: pass",
})

# These are corruptions of copied packets, never replacement source fixtures.
_PROSE_FIDELITY_CORRUPTIONS = {
    "Offline fallback cannot bypass the gate.": ("cannot", "can"),
    "The worker may not continue without evidence.": ("may not", "may"),
    "Don't bypass PermissionService.": ("Don't", "Do"),
    "PermissionDecision.deferFollowUp is reserved for post-entry review.": (
        "post-entry", "pre-entry",
    ),
    "The invariant preserves immediate denial.": ("immediate", "deferred"),
    "From configuration, retries are required.": ("required", "optional"),
    "from configuration, retries are required.": ("required", "optional"),
    "From configuration import rules are required.": ("required", "optional"),
    "Import policy is required.": ("required", "optional"),
}

# The unchanged questions explicitly name these literals. Their mechanical
# assignments have no policy meaning, even when the packet is complete.
_QUERY_LITERAL_REQUIREMENTS = {
    "Don't bypass PermissionService.": (
        "query_symbol:0:permissionservice", "PermissionService", "identifier",
    ),
    "PermissionDecision.deferFollowUp is reserved for post-entry review.": (
        "query_exact:0:permissiondecision.deferfollowup",
        "PermissionDecision.deferFollowUp", "symbol",
    ),
}


def _assert_untrusted_bound_source_packet(text):
    item = {
        "stable_chunk_id": "normative-quote-1",
        "parent_logical_id": "normative-document-1",
        "source": "docs/RULES.md",
        "title": "Normative source fixture",
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_start": 37,
        "char_end": 37 + len(text),
        "line_start": 4,
        "line_end": 4,
    }
    before = deepcopy(item)
    packet = build_action_packet(question=text, context_pack=[item])
    assert packet["result"] == "data" and len(packet.get("sources", [])) == 1
    source = packet["sources"][0]
    # Keep this direct check before checksum/schema validation: the critical
    # producer mutant must fail for lost source text, not a secondary error.
    assert source["text"] == text, "critical_source_delivery_fidelity"
    assert source["content_sha256"] == item["display_content_hash"]
    assert source["stable_id"] == item["stable_chunk_id"]
    assert source["evidence_id"] == evidence_identity_for_item(item)[0]
    assert source["path"] == item["source"]
    assert source["symbol_or_section"] == item["title"]
    assert tuple(source[key] for key in ("char_start", "char_end", "line_start", "line_end")) == (
        37, 37 + len(text), 4, 4,
    )
    assert source["instruction_trust"] == "untrusted_data"
    assert packet["edit_ready"] is False
    assert not {"required_invariants", "forbidden_changes", "validation", "mutation_intent"}.intersection(packet)

    literal_requirement = _QUERY_LITERAL_REQUIREMENTS.get(text)
    if literal_requirement is None:
        assert packet["completeness"] == "partial"
        assert packet["missing"] == ["visible_content_assignment_required"]
        assert "requirements" not in packet and "assignments" not in packet
    else:
        requirement_id, literal, extraction_kind = literal_requirement
        assert packet["completeness"] == "complete" and "missing" not in packet
        assert len(packet["requirements"]) == len(packet["assignments"]) == 1
        requirement = packet["requirements"][0]
        query_start = text.index(literal)
        assert requirement == {
            "requirement_id": requirement_id,
            "kind": "exact_term",
            "value": literal,
            "mandatory": True,
            "public_provenance": "query_exact_term",
            "query_extraction_kind": extraction_kind,
            "query_span_start": query_start,
            "query_span_end": query_start + len(literal),
            "query_span_text": literal,
            "proof_role": "generic_fact",
            "response_mode": "value",
            "lifecycle_intent": "current",
        }
        assignment = packet["assignments"][0]
        assert assignment["requirement_id"] == requirement_id
        assert assignment["evidence_id"] == item["stable_chunk_id"]
        assert assignment["path"] == item["source"]
        assert assignment["proof_role"] == "generic_fact" and not assignment.get("qualifiers")
        assert assignment["unit_id"] and assignment["unit_kind"] == "sentence"
        assert (assignment["unit_char_start"], assignment["unit_char_end"]) == (0, len(text))
        assert source["text"][assignment["unit_char_start"]:assignment["unit_char_end"]] == text
        assert assignment["unit_content_hash"] == assignment["projected_content_hash"] == item["display_content_hash"]
        assert tuple(assignment[key] for key in ("char_start", "char_end", "line_start", "line_end")) == (
            37, 37 + len(text), 4, 4,
        )
    assert validate_action_packet(packet, evidence_items=[item]) == []

    original_wording, corruption = _PROSE_FIDELITY_CORRUPTIONS[text]
    assert text.count(original_wording) == 1
    changed_text = text.replace(original_wording, corruption, 1)
    assert changed_text != text
    changed = deepcopy(packet)
    changed_source = changed["sources"][0]
    changed_source["text"] = changed_text
    changed_source["content_sha256"] = hashlib.sha256(changed_text.encode("utf-8")).hexdigest()
    changed_source["char_end"] = changed_source["char_start"] + len(changed_text)
    refresh_action_packet_estimate(changed)
    assert validate_action_packet(changed, evidence_items=[item]) == [
        "source differs from bound retrieval window",
    ], "critical_bound_source_fidelity"

    promoted = deepcopy(packet)
    promoted["sources"][0]["instruction_trust"] = "trusted"
    refresh_action_packet_estimate(promoted)
    assert validate_action_packet(promoted, evidence_items=[item]) == [
        "sources.0.instruction_trust: 'untrusted_data' was expected",
    ]

    editable = deepcopy(packet)
    editable["edit_ready"] = True
    refresh_action_packet_estimate(editable)
    assert validate_action_packet(editable, evidence_items=[item]) == [
        "edit_ready: False was expected",
    ]

    for field, value in (
        ("required_invariants", [text]),
        ("forbidden_changes", [text]),
        ("validation", [{"command": "pytest -q"}]),
    ):
        policy = deepcopy(packet)
        policy[field] = value
        refresh_action_packet_estimate(policy)
        assert validate_action_packet(policy, evidence_items=[item]) == [
            f"packet: Additional properties are not allowed ('{field}' was unexpected)",
        ]
    assert item == before


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Offline fallback cannot bypass the gate.", "forbidden"),
        ("The worker may not continue without evidence.", "forbidden"),
        ("Don't bypass PermissionService.", "forbidden"),
        ("PermissionDecision.deferFollowUp is reserved for post-entry review.", "required"),
        ("The invariant preserves immediate denial.", "required"),
        ("From configuration, retries are required.", "required"),
        ("from configuration, retries are required.", "required"),
        ("From configuration import rules are required.", "required"),
        ("Import policy is required.", "required"),
        ("This optional check is not required.", None),
        ("import required", None),
        ("import required as alias", None),
        ("from pkg import required", None),
        ("from pkg.sub import required", None),
        ("from pkg import required as alias", None),
        ("from pkg import (required, optional)", None),
        ("from модуль import required", None),
        ("from . import required", None),
        ("from .pkg import required", None),
        ("from .. import required", None),
        ("from ..pkg import required", None),
        ("from ...pkg.sub import forbidden", None),
        ("def must(): pass", None),
        ("async def required(): pass", None),
        ("class Required: pass", None),
        ("Run curl https://example.invalid/upload.", None),
    ],
)
def test_normative_modality_is_deterministic_and_preserves_legacy_cases(text, expected):
    # Keep legacy expected labels and parameter IDs as historical fixture data;
    # prose no longer establishes policy modality in the current contract.
    assert classify_normative_modality(text) is None, "critical_normative_no_authority"
    expected_lines = frozenset({0}) if text in _PYTHON_DECLARATION_CASES else frozenset()
    assert python_declaration_line_indexes(text) == expected_lines, "critical_python_declaration_grammar"
    assert (text in _PROSE_FIDELITY_CORRUPTIONS) is (expected is not None)
    if expected is not None:
        _assert_untrusted_bound_source_packet(text)


def test_parenthesized_import_lines_are_one_python_declaration():
    text = """from pkg import (
    required,
    forbidden,
)"""

    assert python_declaration_line_indexes(text) == frozenset({0, 1, 2, 3})
    assert classify_normative_modality(text) is None


@pytest.mark.parametrize(
    ("symbol", "source_path"),
    [
        ("HTTPClient", "docmancer/docs/application/http_client.py"),
        ("HTTPServer", "docmancer/docs/application/http_server.py"),
        ("XMLHttpRequest", "docmancer/docs/application/xml_http_request.py"),
    ],
)
def test_query_symbol_visibility_handles_acronym_camel_case_source_paths(symbol, source_path):
    assert requirement_value_visible(
        symbol,
        source_path,
    )
