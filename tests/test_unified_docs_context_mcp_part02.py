"""Split tests from test_unified_docs_context_mcp.py; shared helpers remain in the façade module."""
from tests import _shared_test_unified_docs_context_mcp as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})


def test_patch_retrieval_issues_ignore_docs_answer_completeness():
    from docmancer.docs.interfaces.mcp.context_tools import bounded_patch_retrieval_issues

    payload = {
        "status": "success",
        "answer_available": False,
        "answer_type": "navigation_only",
        "answer_completeness": {
            "status": "partial",
            "source_search_required": True,
            "source_search_status": "required",
        },
        "lanes": {"project": {"status": "success"}},
    }

    assert bounded_patch_retrieval_issues(payload) == []


def test_patch_retrieval_issues_keep_operational_failures():
    from docmancer.docs.interfaces.mcp.context_tools import bounded_patch_retrieval_issues

    payload = {
        "status": "partial",
        "requires_confirmation": True,
        "lanes": {
            "project": {"status": "failed"},
            "dependency": {"status": "success"},
        },
    }

    assert bounded_patch_retrieval_issues(payload) == [
        "Documentation retrieval is incomplete (status=partial).",
        "Documentation retrieval requires explicit user confirmation before editing.",
        "Required documentation lanes are incomplete: project.",
    ]

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
        trust_contract={"sources": {"selected": [], "rejected": [], "risky": []}},
        retrieval_routing=routing,
    )

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return original

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context", {"question": "Explain docs"},
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
                trust_contract={"sources": {"selected": [], "rejected": [], "risky": []}},
            )

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {
            "question": question, "library": "runtime",
        },
        cast(Any, Facade()),
    ))

    assert result.get("reason_code") != "invalid_model_visible_projection"
    assert estimate_projection_tokens(result) <= 1_500
    assert result["decision_hash"] == selection.support_decision.decision_hash
    assert result["answer_supported"] is True
    assert "support_envelope" not in result


def test_get_docs_context_default_answer_reports_compaction_without_debug_noise():
    from docmancer.docs.application.model_visible_projection import estimate_projection_tokens

    large = "x" * 120_000

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return UnifiedDocsContextResult(
                question=question,
                context_pack=[{"doc_scope": "project", "path": "docs/ScanDoc.md", "content": large}],
                trust_contract={"sources": {"selected": [{"path": "docs/ScanDoc.md", "snippet": large}], "rejected": [], "risky": []}},
            )

    result = handle_context_tool("get_docs_context", {"question": "find current web API camera implementation", "project_path": "/repo"}, Facade())

    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert estimate_projection_tokens(result) <= 1_500
    assert "context_pack" not in result
    assert "output_contract" not in result


def test_get_docs_context_aligns_selected_source_risk_with_primary_snippet():
    from docmancer.docs.interfaces.mcp.context_tools import _align_trust_contract_with_snippets, _answer_payload

    result = _answer_payload(_align_trust_contract_with_snippets({
        "status": "success",
        "answer_available": True,
        "primary_snippet": {
            "source": "https://riverpod.dev/docs/3.0_migration",
            "risk_flags": ["not_exact_version"],
            "version_binding": "latest_fallback",
            "exact_version_match": False,
        },
        "trust_contract": {"sources": {
            "selected": [{
                "source": "https://riverpod.dev/docs/3.0_migration",
                "risk_flags": [],
                "version_binding": "exact_version_url",
            }],
            "rejected": [],
            "risky": [],
        }},
    }))

    selected = result["trust_contract"]["sources"]["selected"][0]
    assert selected["risk_flags"] == ["not_exact_version"]
    assert selected["version_binding"] == "latest_fallback"
    assert selected["exact_version_match"] is False


def test_get_docs_context_preserves_nested_selected_source_path():
    from docmancer.docs.interfaces.mcp.context_tools import _answer_payload

    result = _answer_payload({
        "status": "success",
        "answer_available": False,
        "trust_contract": {"sources": {
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
        }},
    })

    assert result["trust_contract"]["sources"]["selected"] == [{
        "source": {
            "path": "ARCHITECTURE.md",
            "title": "ARCHITECTURE",
            "source_class": "project_doc",
        },
        "risk_flags": [],
    }]
