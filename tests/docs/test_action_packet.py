from __future__ import annotations

import json

from docmancer.docs.application.action_packet import (
    build_action_packet,
    estimate_action_packet_tokens,
    validate_action_packet,
)
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.models import ProjectContextResult
from docmancer.mcp.docs_server import TOOLS


def test_bounded_direct_is_one_existing_tool_call_and_returns_only_action_packet():
    tool = next(item for item in TOOLS if item["name"] == "get_docs_context")
    assert tool["inputSchema"]["properties"]["delivery_strategy"]["enum"] == ["bounded_direct"]
    assert len(TOOLS) == 3

    class Backend:
        calls = 0

        def get_project_context(self, project_path, question, **kwargs):
            self.calls += 1
            return ProjectContextResult(
                project_path=project_path,
                question=question,
                context_pack=[{
                    "doc_scope": "project",
                    "path": "AGENTS.md",
                    "heading_path": "Checks",
                    "authority": "canonical",
                    "content": "You must run pytest tests/docs/test_action_packet.py.",
                }],
                trust_contract={"selected": [{"source": "AGENTS.md"}], "rejected": [], "risky": []},
            )

    backend = Backend()
    result = handle_context_tool("get_docs_context", {
        "question": "Implement bounded retrieval",
        "project_path": "/repo",
        "delivery_strategy": "bounded_direct",
        "output_mode": "full",
    }, UnifiedDocsContextService(backend))

    assert backend.calls == 1
    assert set(result) == {"tool", "delivery_strategy", "action_packet", "document_content_policy"}
    assert "context_pack" not in json.dumps(result)
    assert result["action_packet"]["status"] == "ok"
    assert result["action_packet"]["validation"]["tests"][0]["text"].endswith("test_action_packet.py.")
    assert validate_action_packet(result["action_packet"]) == []


def test_action_packet_is_deterministic_deduplicated_authority_filtered_and_cited():
    items = [
        {
            "doc_scope": "project", "source_class": "project_doc", "path": "AGENTS.md",
            "heading_path": "Architecture", "authority": "canonical",
            "content": "The formatter must preserve whole facts. Do not expose raw retrieval.",
        },
        {
            "doc_scope": "project", "source_class": "project_doc", "path": "AGENTS.md",
            "heading_path": "Architecture", "authority": "canonical", "content": "duplicate",
        },
        {
            "doc_scope": "project", "source_class": "source_evidence", "path": "docmancer/api.py",
            "title": "API", "symbols": ["get_docs_context"],
            "content": "This supporting evidence must not become an agent invariant.",
        },
        {
            "doc_scope": "project", "source_class": "project_doc", "path": "OLD.md",
            "title": "Old", "content": "Never use this stale rule.", "freshness": "stale",
        },
    ]
    first = build_action_packet(question="Bound the context", context_pack=reversed(items))
    second = build_action_packet(question="Bound the context", context_pack=items)

    assert first == second
    assert [row["path"] for row in first["source_of_truth"]] == ["AGENTS.md", "docmancer/api.py"]
    assert first["source_of_truth"][0]["authority"] == "canonical"
    assert first["target_surface"]["likely_files"][0]["path"] == "docmancer/api.py"
    assert first["target_surface"]["symbols"][0]["name"] == "get_docs_context"
    assert not any("supporting evidence" in item["text"] for item in first["required_invariants"])
    evidence_ids = {row["evidence_id"] for row in first["source_of_truth"]}
    for fact in [
        *first["required_invariants"], *first["forbidden_changes"],
        *first["target_surface"]["symbols"], *first["target_surface"]["likely_files"],
    ]:
        assert set(fact["evidence_ids"]) <= evidence_ids
    assert validate_action_packet(first) == []


def test_action_packet_truncates_whole_items_and_fails_closed_without_evidence():
    content = "\n".join(f"Rule {index} must preserve complete invariant number {index}." for index in range(100))
    packet = build_action_packet(
        question="Apply every relevant invariant",
        context_pack=[{
            "doc_scope": "project", "path": "AGENTS.md", "heading_path": "Rules",
            "authority": "canonical", "content": content,
        }],
        max_tokens=300,
    )

    assert packet["status"] == "insufficient_evidence"
    assert packet["omitted_counts"]["required_invariants"] > 0
    assert packet["estimated_tokens"] == estimate_action_packet_tokens(packet) <= 300
    assert all(item["text"].endswith(".") for item in packet["required_invariants"])
    assert validate_action_packet(packet) == []

    empty = build_action_packet(question="Unknown task", context_pack=[])
    assert empty["status"] == "insufficient_evidence"
    assert empty["missing_evidence"]
    assert validate_action_packet(empty) == []

    conflict = build_action_packet(question="Choose a rule", context_pack=[
        {"path": "AGENTS.md", "heading_path": "Rule", "authority": "canonical", "content": "This must be A."},
        {"path": "AGENTS.md", "heading_path": "Rule", "authority": "canonical", "content": "This must be B."},
    ])
    assert conflict["status"] == "insufficient_evidence"
    assert conflict["uncertainties"] == [{
        "type": "authority_conflict", "path": "AGENTS.md", "symbol_or_section": "Rule",
    }]
    assert "unknown fields: invented" in validate_action_packet({**empty, "invented": True})
