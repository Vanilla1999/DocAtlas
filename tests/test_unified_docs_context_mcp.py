"""Split test module; helpers live in _shared_test_unified_docs_context_mcp.py."""
from tests import _shared_test_unified_docs_context_mcp as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})
import pytest

def test_get_docs_context_registered_in_mcp_tool_list():
    names = [tool["name"] for tool in TOOLS]
    assert "get_docs_context" in names


def test_get_docs_context_schema():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_docs_context")
    schema = tool["inputSchema"]
    assert schema["required"] == ["question"]
    assert {"allow_network", "force_refresh", "prefetch_auto", "prepare_project_docs"}.isdisjoint(schema["properties"])
    assert set(schema["properties"]) == {
        "question", "project_path", "library", "libraries", "ecosystem",
        "version", "source_type", "docs_url", "module", "module_path",
        "scope", "mode", "lookup_queries",
    }
    assert schema["properties"]["scope"]["enum"] == ["project", "module", "all"]
    assert schema["properties"]["mode"]["enum"] == [
        "auto", "project", "library", "dependency", "mixed",
    ]


def test_get_docs_context_output_schema_accepts_only_current_statuses():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_docs_context")

    for status in ("ok", "truncated", "insufficient_evidence", "failed"):
        jsonschema.validate({"status": status}, tool["outputSchema"])

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"status": "success"}, tool["outputSchema"])


def test_multi_library_context_requires_every_library_support_decision():
    class Decision:
        def __init__(self, supported: bool, library: str):
            self.answer_supported = supported
            self.missing_requirement_ids = () if supported else (f"{library}:required",)
            self.satisfied_requirement_ids = (f"{library}:required",) if supported else ()
            self.mandatory_requirement_ids = (f"{library}:required",)
            self.mandatory_coverage = 1.0 if supported else 0.0
            self.selected_evidence_ids = (f"{library}:evidence",) if supported else ()

    class Facade:
        def __init__(self, unsupported: set[str] | None = None):
            self.unsupported = unsupported or set()

        def get_docs(self, library, topic=None, **kwargs):
            supported = library not in self.unsupported
            return DocsResult(
                library_id=f"test:{library}@1:api",
                library=library,
                version="1",
                topic=topic,
                refreshed=False,
                stale_before_refresh=False,
                warning=None,
                last_refreshed_at=None,
                results=[DocsChunk(title=library, content=f"{library} exact API evidence", source=f"https://docs.example/{library}", url=f"https://docs.example/{library}")],
                support_decision=cast(Any, Decision(supported, library)),
            )

    supported = UnifiedDocsContextService(Facade()).get_docs_context(
        "How do alpha and beta work?",
        libraries=["alpha", "beta"],
        mode="library",
        allow_network=True,
    )
    incomplete = UnifiedDocsContextService(Facade({"beta"})).get_docs_context(
        "How do alpha and beta work?",
        libraries=["alpha", "beta"],
        mode="library",
        allow_network=True,
    )

    assert supported.answer_supported is False
    assert supported.support_status == "insufficient_evidence"
    assert supported.reason_code == "canonical_lane_decision_missing"
    assert incomplete.answer_supported is False
    assert incomplete.reason_code == "canonical_lane_decision_missing"
    assert incomplete.missing_requirement_ids == ["beta:required"]
    assert incomplete.decision_hash is None


def test_docmancer_agent_quickstart_resource_exists():
    from docmancer.mcp.docs_server import MCP_RESOURCES

    resources = {resource["uri"]: resource for resource in MCP_RESOURCES}
    assert "docmancer://agent/quickstart" in resources

    text = resources["docmancer://agent/quickstart"]["text"]
    assert "Docmancer is a local documentation/context router" in text
    assert "not a code auditor" in text
    assert "get_docs_context" in text
    assert "bounded structured" in text


def test_library_workflow_resource_uses_canonical_three_tool_workflow():
    from docmancer.mcp.docs_server import MCP_RESOURCES

    resource = next(
        resource for resource in MCP_RESOURCES
        if resource["uri"] == "docmancer://workflow/library-docs"
    )
    text = resource["text"]

    assert "get_docs_context" in text
    assert "mode=\"library\"" in text
    assert "get_docs_context" in text
    assert "prepare_docs" in text
    assert "docs_status" in text


@pytest.mark.parametrize("lookup_queries", [
    ["   "],
    ["same", "SAME"],
    ["one", "two", "three", "four", "five", "six"],
])
def test_get_docs_context_rejects_invalid_lookup_queries(lookup_queries):
    result = handle_context_tool(
        "get_docs_context",
        {"question": "How?", "project_path": "/repo", "lookup_queries": lookup_queries},
        object(),
    )

    assert result["error"]["reason_code"] == "invalid_lookup_queries"


def test_handler_exception_redacts_secret_even_in_debug_mode():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            raise RuntimeError("Authorization: Bearer super-secret")

    payload = call_docs_tool_payload(
        "get_docs_context", {"question": "How?"}, cast(Any, Facade()),
    )

    assert "super-secret" not in json.dumps(payload)
    assert payload["error"]["message"] == "handler_exception: request failed"


def test_missing_kotlin_corpus_uses_prepare_docs_through_real_application_boundary():
    class Facade:
        def resolve_library(self, library, ecosystem, version, docs_url, docs_url_template, source_type):
            return LibraryInfo(
                library_id="kotlin:kotlin@1.8.1:web",
                library=library,
                ecosystem=ecosystem,
                version=version,
                source_type="web",
                status="available",
                local=False,
            )

    payload = call_docs_tool_payload(
        "get_docs_context",
        {"question": "coroutines", "library": "kotlin", "ecosystem": "kotlin", "version": "1.8.1"},
        UnifiedDocsContextService(Facade()),
    )

    assert payload["kind"] == "docs_answer"
    assert payload["status"] == "insufficient_evidence"
    assert payload["recommended_next_action"]["tool"] == "prepare_docs"
    assert payload["recommended_next_action"]["arguments_patch"] == {
        "action": "prefetch_library_docs",
        "library": "kotlin",
        "question": "coroutines",
        "ecosystem": "kotlin",
        "version": "1.8.1",
    }


def test_bounded_context_preserves_docs_layout_inspection_decision_packet():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "not_found",
                "answer_available": False,
                "next_action": {
                    "tool": "prepare_docs",
                    "type": "prepare_docs",
                    "arguments_patch": {
                        "action": "inspect_docs_target",
                        "target": {
                            "library": "sample",
                            "docs_url": "https://docs.example/api/",
                            "allowed_domains": ["docs.example"],
                        },
                        "max_pages": 3,
                    },
                    "observations": {"source_status": "partial", "indexed_chunks": 0},
                    "security_scope": {
                        "allowed_domains": ["docs.example"],
                        "scope_expansion_allowed": False,
                    },
                    "decision_options": [
                        {"id": "inspect_registered_scope", "requires_confirmation": True},
                        {"id": "stop_with_partial_results", "requires_confirmation": False},
                    ],
                    "agent_question": "Inspect the registered scope without indexing?",
                    "requires_confirmation": True,
                },
            }

    payload = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {
            "question": "How does Sample work?",
            "library": "sample",
        },
        cast(Any, Facade()),
    ))

    action = payload["recommended_next_action"]
    assert action["arguments_patch"]["action"] == "inspect_docs_target"
    assert action["observations"]["indexed_chunks"] == 0
    assert action["security_scope"]["scope_expansion_allowed"] is False
    assert action["decision_options"][0]["id"] == "inspect_registered_scope"
    assert action["agent_question"] == "Inspect the registered scope without indexing?"
    assert action["auto_execute"] is False


def test_project_mode_does_not_rewrite_network_retry_as_dependency_prefetch():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "not_found",
                "answer_available": False,
                "next_action": {
                    "tool": "get_docs_context",
                    "arguments_patch": {
                        "question": question,
                        "project_path": "/repo",
                        "allow_network": True,
                    },
                },
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {
            "question": "local architecture",
            "project_path": "/repo",
            "mode": "project",
        },
        cast(Any, Facade()),
    ))

    assert result["status"] == "insufficient_evidence"
    assert "recommended_next_action" not in result


def test_mixed_mode_can_rewrite_network_retry_as_dependency_prefetch():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "not_found",
                "answer_available": False,
                "next_action": {
                    "tool": "get_docs_context",
                    "arguments_patch": {"allow_network": True},
                },
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {
            "question": "dependency API",
            "project_path": "/repo",
            "mode": "mixed",
        },
        cast(Any, Facade()),
    ))

    assert result["recommended_next_action"]["arguments_patch"] == {
        "action": "prefetch_project_dependency_docs",
        "project_path": "/repo",
    }


def test_project_preflight_recovery_precedes_dependency_prefetch():
    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context",
                "status": "not_found",
                "requires_confirmation": True,
                "next_action": {
                    "type": "ask_user_to_update_or_confirm_project_docs",
                    "requires_confirmation": True,
                    "confirmation_reason": "project_docs_preflight",
                    "tool_after_confirmation": "sync_project_docs",
                    "arguments_patch_after_confirmation": {
                        "project_path": "/repo",
                        "with_vectors": True,
                    },
                },
                "next_actions": [{
                    "tool": "prefetch_project_dependency_docs",
                    "requires_confirmation": True,
                    "reason": "Dependency docs may require network access.",
                }],
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context",
        {
            "question": "local architecture",
            "project_path": "/repo",
            "mode": "project",
        },
        cast(Any, Facade()),
    ))

    assert result["recommended_next_action"]["tool"] == "prepare_docs"
    assert result["recommended_next_action"]["arguments_patch"] == {
        "action": "sync_project_docs",
        "project_path": "/repo",
        "with_vectors": True,
    }


def test_mcp_public_surface_exposes_canonical_three_tools():
    names = {tool["name"] for tool in TOOLS}
    assert names == {"get_docs_context", "prepare_docs", "docs_status"}


def test_context_tools_filter_only_unified_tool():
    assert [tool["name"] for tool in context_tools(TOOLS)] == ["get_docs_context"]


def test_document_content_policy_survives_bounded_projection():
    from docmancer.docs.interfaces.mcp.context_tools import _answer_payload

    result = _answer_payload({"status": "success", "answer_available": False})
    assert result["document_content_policy"] == {
        "role": "cited_untrusted_document_data",
        "actionable": False,
        "actions_source": "typed_top_level_fields_only",
    }
    assert result.get("next_action") is None
    assert result.get("next_actions") in (None, [])


def test_bounded_delivery_records_exact_model_visible_bytes_end_to_end():
    from docmancer.docs.domain.retrieval_routing import new_routing_record, route_initial_stages

    routing = new_routing_record(
        route_initial_stages(
            question="Explain docs", mode="project-only",
            dependency_requested=False, project_doc_items=[],
        ),
        project_docs_used=True,
        dependency_docs_used=False,
    )

    class Facade:
        def get_docs_context(self, question, **kwargs):
            return {
                "tool": "get_docs_context", "status": "success", "context_available": True,
                "context_pack": [], "trust_contract": {"selected": [], "rejected": [], "risky": []},
                "diagnostics": {"retrieval_routing": routing},
            }

    result = cast(dict[str, Any], handle_context_tool(
        "get_docs_context", {"question": "Explain docs"},
        cast(Any, Facade()),
    ))

    assert routing["model_visible_bytes"] == len(canonical_projection_bytes(result))
