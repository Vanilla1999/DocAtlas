"""Split tests from test_unified_docs_context_mcp.py; shared helpers remain in the façade module."""
from tests import _shared_test_unified_docs_context_mcp as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_bounded_delivery_updates_original_unified_result_telemetry_record():
    from docmancer.docs.domain.retrieval_routing import new_routing_record, route_initial_stages
    from docmancer.docs.models import UnifiedDocsContextResult

    routing = new_routing_record(
        route_initial_stages(
            question="Explain docs", mode="project-only",
            dependency_requested=False, project_doc_items=[],
        ),
        project_docs_used=True,
        dependency_docs_used=False,
    )
    original = UnifiedDocsContextResult(
        status="success", context_available=True, context_pack=[],
        trust_contract={"selected": [], "rejected": [], "risky": []},
        retrieval_routing=routing,
    )

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return original

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context", {"question": "Explain docs", "delivery_strategy": "bounded_direct"},
        cast(Any, Facade()),
    ))

    assert original.retrieval_routing["model_visible_bytes"] == len(
        canonical_projection_bytes(result)
    )


def test_bounded_library_delivery_at_256_tokens_uses_compact_support_summary():
    from docmancer.docs.application.evidence_selection import (
        library_docs_selection_config,
        select_evidence,
    )
    from docmancer.docs.application.model_visible_projection import (
        estimate_projection_tokens,
    )

    question = "Compare create_task with gather and explain how the scheduled task result is obtained"
    candidate = {
        "stable_id": "runtime-witness", "source": "docs/runtime.md",
        "content": "Compare create_task with gather; obtain the scheduled task result from create_task.",
    }
    selection = select_evidence(
        [candidate], question=question, config=library_docs_selection_config(800),
    )

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return SimpleNamespace(
                status="success", answer_available=True,
                selection_profile="library_docs_answer",
                selection_decision=selection, context_pack=[candidate],
                trust_contract={"selected": [], "rejected": [], "risky": []},
            )

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {
            "question": question, "library": "runtime",
            "delivery_strategy": "bounded_direct", "packet_tokens": 256,
        },
        cast(Any, Facade()),
    ))

    assert result.get("reason_code") != "invalid_model_visible_projection"
    assert estimate_projection_tokens(result) <= 256
    assert result["decision_hash"] == selection.support_decision.decision_hash
    assert result["answer_supported"] is False
    assert "support_envelope" not in result


def test_get_docs_context_default_answer_reports_compaction_without_debug_noise():
    large = "x" * 120_000

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return UnifiedDocsContextResult(
                question=question,
                context_pack=[{"doc_scope": "project", "path": "docs/ScanDoc.md", "content": large}],
                trust_contract={"selected": [{"path": "docs/ScanDoc.md", "snippet": large}], "rejected": [], "risky": []},
            )

    result = handle_context_tool("get_docs_context", {"question": "find current web API camera implementation", "project_path": "/repo"}, Facade())

    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert result["output_mode"] == "answer"
    assert result["response_truncated"] is True
    assert result["mcp_compaction"]["truncated"] is True
    assert result["output_contract"]["truncated"] is True
    assert result["output_contract"]["complete"] is False
    assert result["output_contract"]["safe_to_use_as_complete_context"] is False
    assert result["output_contract"]["retry_with"] == {"output_mode": "debug", "page_size": 5, "narrow_query": True}
    assert "context_pack" not in result
    assert any(isinstance(warning, dict) and warning.get("code") == "mcp_response_truncated" for warning in result.get("warnings", []))
    assert not any(isinstance(warning, dict) and str(warning.get("code") or "").startswith("mcp_compact_output_") for warning in result.get("warnings", []))


def test_get_docs_context_debug_output_keeps_compaction_diagnostics():
    large = "x" * 120_000

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return UnifiedDocsContextResult(
                question=question,
                context_pack=[{"doc_scope": "project", "path": "docs/ScanDoc.md", "content": large}],
                trust_contract={"selected": [{"path": "docs/ScanDoc.md", "snippet": large}], "rejected": [], "risky": []},
            )

    result = handle_context_tool("get_docs_context", {"question": "find current web API camera implementation", "project_path": "/repo", "output_mode": "debug"}, Facade())

    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert result["mcp_compaction"]["truncated"] is True
    assert result["output_contract"]["truncated"] is True


def test_get_docs_context_aligns_selected_source_risk_with_primary_snippet():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "success",
                "answer_available": True,
                "primary_snippet": {
                    "source": "https://riverpod.dev/docs/3.0_migration",
                    "source_url": "https://riverpod.dev/docs/3.0_migration",
                    "risk_flags": ["not_exact_version"],
                    "version_binding": "latest_fallback",
                    "exact_version_match": False,
                },
                "trust_contract": {
                    "selected": [{
                        "source": "https://riverpod.dev/docs/3.0_migration",
                        "risk_flags": [],
                        "version_binding": "exact_version_url",
                    }],
                    "rejected": [],
                    "risky": [],
                },
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {"question": "Riverpod ref.watch AsyncValue", "library": "flutter_riverpod"},
        Facade(),
    ))

    selected = result["selected_sources"][0]
    assert selected["risk_flags"] == ["not_exact_version"]
    assert selected["version_binding"] == "latest_fallback"
    assert selected["exact_version_match"] is False


def test_get_docs_context_answer_flattens_nested_selected_source_path():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "success",
                "answer_available": True,
                "trust_contract": {
                    "selected": [{
                        "source": {
                            "path": "ARCHITECTURE.md",
                            "title": "ARCHITECTURE",
                            "source_class": "project_doc",
                        },
                        "risk_flags": [],
                    }],
                    "rejected": [],
                    "risky": [],
                },
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {"question": "architecture", "project_path": "/repo", "mode": "project"},
        cast(Any, Facade()),
    ))

    assert result["selected_sources"] == [{
        "path": "ARCHITECTURE.md",
        "title": "ARCHITECTURE",
        "source_class": "project_doc",
        "risk_flags": [],
    }]


def test_get_docs_context_answer_mode_marks_navigation_only_payload_not_answer_available():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "success",
                "answer_available": True,
                "trust_contract": {
                    "selected": [{"path": "ARCHITECTURE.md", "title": "Architecture"}],
                    "rejected": [],
                    "risky": [],
                },
                "next_actions": [{"action": "search_project_sources", "tool": "code_search"}],
                "ingestion_diagnostics": {"project": {"repo_map": {"selected_files": 1}}},
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {"question": "How does DI work?", "project_path": "/repo", "mode": "project"},
        cast(Any, Facade()),
    ))

    assert result["answer_available"] is False
    assert result["answer_type"] == "navigation_only"
    assert result["safe_to_answer"] is False
    assert result["required_next_step"] == "read_or_search_suggested_sources"
    assert result["not_a_code_auditor"] is True
    assert "Do not treat this as a complete answer" in result["agent_instruction"]
    assert "ingestion_diagnostics" not in result
    assert result["next_actions"] == [{"action": "search_project_sources", "tool": "code_search"}]


def test_get_docs_context_navigation_only_has_agent_instruction():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "success",
                "answer_available": True,
                "trust_contract": {
                    "selected": [{"path": "ARCHITECTURE.md", "title": "Architecture"}],
                    "rejected": [],
                    "risky": [],
                },
                "next_actions": [{"action": "search_project_sources", "tool": "code_search"}],
                "ingestion_diagnostics": {"project": {"repo_map": {"selected_files": 1}}},
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {"question": "How does DI work?", "project_path": "/repo", "mode": "project"},
        cast(Any, Facade()),
    ))

    assert result["answer_available"] is False
    assert result["answer_type"] == "navigation_only"
    assert result["safe_to_answer"] is False
    assert result["required_next_step"] == "read_or_search_suggested_sources"
    assert "Do not treat this as a complete answer" in result["agent_instruction"]


def test_get_docs_context_direct_answer_has_agent_instruction():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "success",
                "answer_available": True,
                "primary_snippet": {
                    "source": "docs/API.md",
                    "content": "Use FooClient.create()",
                },
                "trust_contract": {
                    "selected": [{"path": "docs/API.md"}],
                    "rejected": [],
                    "risky": [],
                },
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {"question": "How to create FooClient?", "project_path": "/repo"},
        cast(Any, Facade()),
    ))

    assert result["answer_type"] == "direct"
    assert result["safe_to_answer"] is True
    assert result["required_next_step"] == "answer_from_returned_context"


def test_answer_mode_cannot_manufacture_support_from_a_snippet():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "success",
                "answer_available": True,
                "answer_supported": False,
                "support_status": "insufficient_evidence",
                "reason_code": "required_evidence_missing",
                "missing_requirement_ids": ["result_access"],
                "satisfied_requirement_ids": ["comparison"],
                "mandatory_requirement_ids": ["comparison", "result_access"],
                "mandatory_coverage": 0.5,
                "selected_evidence_ids": ["partial"],
                "decision_hash": "decision-1",
                "primary_snippet": {
                    "source": "docs/partial.md",
                    "content": "A comparison without result-access evidence.",
                },
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {"question": "Compare the APIs and retrieve the result", "library": "example"},
        cast(Any, Facade()),
    ))

    assert result["answer_supported"] is False
    assert result["answer_available"] is False
    assert result["reason_code"] == "required_evidence_missing"
    assert result["mandatory_requirement_ids"] == ["comparison", "result_access"]
    assert result["mandatory_coverage"] == 0.5
