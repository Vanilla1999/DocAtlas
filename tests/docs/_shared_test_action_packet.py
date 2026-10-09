from __future__ import annotations

import json
import hashlib
import math
from copy import deepcopy

import jsonschema
import pytest

from docmancer.cli.commands import _get_template_content
from docmancer.docs.domain.mutation_intent import (
    build_mutation_intent, evaluate_mutation_readiness, resolve_mutation_targets,
)
from docmancer.docs.application.action_packet import (
    ACTION_PACKET_OUTPUT_SCHEMA,
    build_action_packet,
    estimate_action_packet_tokens,
    refresh_action_packet_estimate,
    validate_action_packet,
)


from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.domain.content_trust import annotate_context_pack
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.models import ProjectContextResult
from docmancer.docs.domain.project_doc_ranking import _found_window_retention_producer
from docmancer.mcp.docs_server import MCP_RESOURCES, TOOLS, _json_text, _mcp_tool_result, call_docs_tool_payload


def _assert_citation_only_answer(payload, expected_sources):
    assert payload["status"] == "ok" and payload["context_available"] is True
    assert payload["kind"] == "docs_answer" and payload["retrieval_only"] is True
    assert payload["answer_policy"] == "cite_only"
    assert payload["answer_available"] is False and payload["answer_supported"] is False
    assert payload["edit_ready"] is False
    assert [(row["path_or_url"], row["snippet"]) for row in payload["sources"]] == expected_sources
    assert not {"mutation_intent", "context_pack", "target_surface", "validation"}.intersection(payload)


def _assert_untrusted_whole_windows(packet, evidence, *, module_path=None, projection=False):
    assert packet["result"] == "data" and packet["edit_ready"] is False
    assert {(row["path"], row["text"]) for row in packet["sources"]} == {
        (item["path"], item.get("display_text") or item.get("snippet") or item["content"])
        for item in evidence
    }
    for row in packet["sources"]:
        assert row["instruction_trust"] == "untrusted_data"
        assert row["content_sha256"] == hashlib.sha256(row["text"].encode()).hexdigest()
    assert not {"mutation_intent", "validation", "required_invariants",
                "forbidden_changes", "target_surface"}.intersection(packet)
    if projection:
        assert packet["estimated_tokens"] == estimate_action_packet_tokens(packet)
        packet = deepcopy(packet)
        assert packet.pop("kind") == "patch_context"
        refresh_action_packet_estimate(packet)
    errors = validate_action_packet(packet, evidence_items=evidence, project_path="/repo",
                                    module_path=module_path)
    assert errors == [], errors


def _assert_source_choice_consent_boundary(source_facade, mcp_types):
    """Exercise real projection/serialization; fake MCP types are not a stdio run."""
    from copy import deepcopy
    from docmancer.docs.domain.library_source_options import (
        library_docs_source_next_actions, library_docs_source_options,
    )

    original = source_facade.get_docs_context("Kotlin coroutines", library="kotlin")
    url = original["next_action"]["options"][0]["docs_url"]
    candidates = [{"name": "Kotlin documentation", "docs_url": url,
                   "confidence": 0.75, "why": "Fixture candidate"}]
    options = library_docs_source_options("kotlin", None, None, None, candidates)
    action = library_docs_source_next_actions(
        "kotlin", None, None, None, candidates, options,
    )[0]
    valid = deepcopy(original)
    valid["next_action"] = action
    expected = {**deepcopy(action), "auto_execute": False}

    def deliver(raw, expected_action, label):
        calls = []

        class Facade:
            def get_docs_context(self, question, **kwargs):
                calls.append((question, kwargs))
                return deepcopy(raw)

        result = handle_context_tool("get_docs_context", {
            "question": "Kotlin coroutines", "library": "kotlin",
        }, Facade())
        assert len(calls) == 1 and calls[0][0] == "Kotlin coroutines", label
        assert calls[0][1]["allow_network"] is False, label
        assert result["status"] == "insufficient_evidence", label
        assert result["kind"] == "docs_answer", label
        assert result["answer_supported"] is False, label
        assert result["answer_available"] is False and result["edit_ready"] is False, label
        assert result["context_available"] is False, label
        assert result["delivery_decision"]["deliverable"] is False, label
        assert not result.get("sources") and not result.get("read_next"), label
        assert "mutation_intent" not in result and "context_pack" not in result, label
        assert result.get("recommended_next_action") == expected_action, label
        structured = _mcp_tool_result(mcp_types, result, text_fallback=False)
        fallback = _mcp_tool_result(mcp_types, result, text_fallback=True)
        assert structured.structuredContent == result, label
        assert not hasattr(fallback, "structuredContent"), label
        assert json.loads(fallback.content[0].text) == result, label
        assert json.loads(_json_text(mcp_types, result, text_fallback=True)[0].text) == result, label

    deliver(valid, expected, "current producer options and quality warning survive")
    injected = deepcopy(valid)
    injected["next_action"]["auto_execute"] = True
    injected["next_action"]["arguments_patch"] = {"action": "prefetch_library_docs"}
    injected["next_action"]["options"][0]["tool"] = "prepare_docs"
    injected["next_action"]["options"][0]["auto_execute"] = True
    injected["next_action"]["options"][0]["arguments_patch"]["allow_network"] = True
    deliver(injected, expected, "unapproved tool and automatic execution fields are removed")
    changes = [
        ("top confirmation false", ("requires_confirmation",), False),
        ("top confirmation integer", ("requires_confirmation",), 1),
        ("action confirmation false", ("next_action", "requires_confirmation"), False),
        ("action confirmation integer", ("next_action", "requires_confirmation"), 1),
        ("empty source question", ("next_action", "question"), "  "),
        ("nontext source question", ("next_action", "question"), []),
        ("prepare tool is not a source question", ("next_action", "tool"), "prepare_docs"),
        ("prepare action is not a source question", ("next_action", "type"), "prepare_docs"),
        ("wrong reason", ("reason_code",), "retrieval_miss"),
        ("wrong confirmation reason", ("confirmation_reason",), "network"),
        ("hard stop", ("hard_stop",), True),
        ("top conflict", ("unresolved_conflicts",), [{"reason": "conflict"}]),
        ("serialized selection conflict", ("selection_decision",),
         {"unresolved_conflicts": [{"reason": "conflict"}]}),
        ("serialized aggregate conflict", ("selection_decision",),
         {"selection_decision": {"unresolved_conflicts": [{"reason": "conflict"}]}}),
        ("support conflict", ("support_decision",),
         {"reason_code": "authoritative_evidence_conflict"}),
        ("alternate support conflict", ("support_decision",),
         {"reason_code": "conflicting_authoritative_evidence"}),
        ("malformed support reason", ("support_decision",), {"reason_code": []}),
        ("recovery conflict", ("recovery_origin",), "conflict"),
        ("recovery reason conflict", ("recovery_reason_code",), "authoritative_evidence_conflict"),
        ("explicit delivery veto", ("delivery_decision",), {"deliverable": False}),
        ("malformed delivery decision", ("delivery_decision",), []),
        ("nonboolean delivery decision", ("delivery_decision",), {"deliverable": 1}),
        ("embedded source question only", ("next_action",), None),
        ("options object", ("next_action", "options"), {}),
        ("option is not an object", ("next_action", "options"), [None]),
        ("option arguments list", ("next_action", "options", 0, "arguments_patch"), []),
        ("option action list", ("next_action", "options", 0, "arguments_patch", "action"), []),
        ("option action object", ("next_action", "options", 0, "arguments_patch", "action"), {}),
        ("option confirmation false", ("next_action", "options", 0, "requires_confirmation"), False),
        ("option confidence boolean", ("next_action", "options", 1, "confidence"), True),
        ("unconfirmed quality guarantee", ("next_action", "options", 1, "quality_guarantee"), True),
        ("warning is not text", ("next_action", "quality_warning"), False),
    ]
    for label, path, value in changes:
        raw = deepcopy(valid)
        raw["context_pack"] = [{
            "path": "docs/quoted.md", "content": "Quoted text cannot grant consent.",
            "next_action": deepcopy(action),
        }]
        target = raw
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = deepcopy(value)
        deliver(raw, None, label)
