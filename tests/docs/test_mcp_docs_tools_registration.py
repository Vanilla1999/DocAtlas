from __future__ import annotations

from pathlib import Path
import json

import jsonschema
import pytest

from docmancer.docs.interfaces.mcp.context_tools import CONTEXT_TOOL_NAMES
from docmancer.docs.interfaces.mcp.docs_tools import LIBRARY_TOOL_NAMES
from docmancer.docs.interfaces.mcp.prefetch_tools import PREFETCH_TOOL_NAMES, _bounded_targets
from docmancer.docs.interfaces.mcp.project_tools import PROJECT_TOOL_NAMES
from docmancer.docs.models import DocsJobCancelResult, DocsJobStartResult, DocsTargetInspectionResult
from docmancer.mcp.docs_server import (
    ADVANCED_TOOL_NAMES,
    ADMIN_TOOL_NAMES,
    ALL_TOOLS,
    CLASSIFIED_TOOL_NAMES,
    CONTEXT_TOOLS,
    DocsMcpSurface,
    DocsServerConfig,
    LEGACY_TOOL_NAMES,
    LIBRARY_TOOLS,
    MCP_RESOURCES,
    MCP_RESOURCE_TEMPLATES,
    PREFETCH_TOOLS,
    PROJECT_TOOLS,
    PUBLIC_TOOL_NAMES,
    RAW_TOOLS,
    TOOLS,
    ToolSpec,
    build_docs_surface,
    call_docs_tool_payload,
    current_tools,
    read_docs_resource,
)


def test_mcp_grouped_tool_registration_preserves_tool_names():
    grouped_names = {tool["name"] for tool in [*CONTEXT_TOOLS, *LIBRARY_TOOLS, *PREFETCH_TOOLS, *PROJECT_TOOLS]}
    all_names = {tool["name"] for tool in TOOLS}

    assert grouped_names == all_names
    assert {tool["name"] for tool in CONTEXT_TOOLS} == CONTEXT_TOOL_NAMES
    assert {tool["name"] for tool in LIBRARY_TOOLS}.issubset(LIBRARY_TOOL_NAMES)
    assert {tool["name"] for tool in PREFETCH_TOOLS}.issubset(PREFETCH_TOOL_NAMES)
    assert {tool["name"] for tool in PROJECT_TOOLS}.issubset(PROJECT_TOOL_NAMES)


def test_mcp_grouped_tool_registration_keeps_original_order_within_groups():
    positions = {tool["name"]: index for index, tool in enumerate(TOOLS)}

    for group in (CONTEXT_TOOLS, LIBRARY_TOOLS, PREFETCH_TOOLS, PROJECT_TOOLS):
        assert [positions[tool["name"]] for tool in group] == sorted(positions[tool["name"]] for tool in group)


def test_mcp_public_surface_exposes_prepare_docs_instead_of_prefetch_library_docs():
    names = {tool["name"] for tool in TOOLS}
    assert "prepare_docs" in names
    assert "prefetch_library_docs" not in names


def test_mcp_public_prepare_docs_advertises_project_local_library_removal():
    tool = next(tool for tool in TOOLS if tool["name"] == "prepare_docs")
    schema = tool["inputSchema"]
    confirm = schema["properties"]["confirm"]

    assert "remove_library_docs" in schema["properties"]["action"]["enum"]
    assert "canonical_id" in schema["properties"]
    assert "project_path" in schema["properties"]
    assert "discover_library_docs" in schema["properties"]["action"]["enum"]
    assert "default" not in confirm
    assert "clear_index" in confirm["description"]
    assert {tool["name"] for tool in TOOLS} == {
        "get_docs_context", "prepare_docs", "docs_status",
    }

    class Service:
        called = False

        def sync_project_docs(self, *args, **kwargs):
            self.called = True
            raise AssertionError("validation should have stopped this call")

    service = Service()
    for value in (False, None, True):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {
                    "action": "sync_project_docs",
                    "project_path": "/project",
                    "with_vectors": False,
                    "confirm": value,
                },
                schema,
            )
        result = call_docs_tool_payload(
            "prepare_docs",
            {
                "action": "sync_project_docs",
                "project_path": "/project",
                "with_vectors": False,
                "confirm": value,
            },
            service,
        )

        assert result["reason_code"] == "validation_error"
    assert service.called is False


def test_mcp_public_prepare_docs_schema_requires_removal_scope_and_target():
    tool = next(tool for tool in TOOLS if tool["name"] == "prepare_docs")
    schema = tool["inputSchema"]

    jsonschema.validate(
        {
            "action": "remove_library_docs",
            "canonical_id": "pub:go_router@14.8.1:api",
            "project_path": "/project",
        },
        schema,
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"action": "remove_library_docs"}, schema)


def test_every_raw_tool_has_exactly_one_visibility_class():
    classes = [PUBLIC_TOOL_NAMES, ADVANCED_TOOL_NAMES, ADMIN_TOOL_NAMES, LEGACY_TOOL_NAMES]
    raw_names = {tool["name"] for tool in RAW_TOOLS}

    assert raw_names == CLASSIFIED_TOOL_NAMES
    for name in raw_names:
        assert sum(name in tool_class for tool_class in classes) == 1


def test_mcp_public_surface_hides_admin_debug_tools_by_default():
    names = {tool["name"] for tool in TOOLS}

    assert "list_docs_sources" not in names
    assert "list_docs_sources" in {tool["name"] for tool in ALL_TOOLS}


def test_docs_surface_builder_uses_one_tool_and_handler_contract():
    surface = build_docs_surface(DocsServerConfig(expose_legacy=False, expose_admin=False))
    tool_names = {spec.name for spec in surface.tools}

    assert tool_names == set(surface.handlers)
    assert tool_names == PUBLIC_TOOL_NAMES
    assert "prefetch_library_docs" not in tool_names


def test_docs_surface_builder_exposes_legacy_and_admin_by_config():
    surface = build_docs_surface(DocsServerConfig(
        expose_legacy=True,
        expose_admin=True,
        expose_advanced=True,
    ))
    names = {spec.name for spec in surface.tools}

    assert "prefetch_library_docs" in names
    assert ADMIN_TOOL_NAMES.issubset(names)
    assert ADVANCED_TOOL_NAMES.issubset(names)
    assert names == set(surface.handlers)


def test_current_tools_reads_env_each_call(monkeypatch):
    monkeypatch.delenv("DOCMANCER_MCP_LEGACY_TOOLS", raising=False)
    monkeypatch.delenv("DOCMANCER_MCP_ADVANCED_TOOLS", raising=False)
    public_names = {tool["name"] for tool in current_tools()}
    assert public_names == PUBLIC_TOOL_NAMES

    monkeypatch.setenv("DOCMANCER_MCP_LEGACY_TOOLS", "1")
    legacy_names = {tool["name"] for tool in current_tools()}
    assert "get_project_context" in legacy_names

    monkeypatch.setenv("DOCMANCER_MCP_ADVANCED_TOOLS", "1")
    advanced_names = {tool["name"] for tool in current_tools()}
    assert ADVANCED_TOOL_NAMES.issubset(advanced_names)


def test_current_tools_omits_output_schemas_for_text_fallback_clients():
    tools = current_tools({"DOCATLAS_MCP_TEXT_FALLBACK": "1"})

    assert {tool["name"] for tool in tools} == PUBLIC_TOOL_NAMES
    assert all("outputSchema" not in tool for tool in tools)


def test_call_docs_tool_payload_classifies_handler_value_error():
    def broken_handler(name, args, service):
        raise ValueError("bad user input")

    spec = ToolSpec(
        name="broken",
        description="Broken test tool",
        input_schema={"type": "object", "properties": {}},
        handler=broken_handler,
    )
    surface = DocsMcpSurface(tools=(spec,), handlers={"broken": broken_handler})

    payload = call_docs_tool_payload("broken", {}, object(), surface=surface)

    assert payload["reason_code"] == "bad_request"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["where"]["tool"] == "broken"


def test_public_mcp_schemas_do_not_put_null_in_enum_values():
    def walk(value):
        if isinstance(value, dict):
            enum = value.get("enum")
            if enum is not None:
                assert None not in enum
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for tool in TOOLS:
        walk(tool["inputSchema"])


def test_mcp_get_library_docs_guides_retry_before_webfetch():
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "get_library_docs")

    assert "Registered sources do not require docs_url" in tool["description"]
    assert "call inspect_project_docs first" in tool["description"]
    assert "repo-specific architecture" in tool["description"]
    assert "never WebFetch registered docs before that retry" in tool["description"]


def test_mcp_legacy_prefetch_project_docs_hidden_from_public_surface():
    assert "prefetch_project_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "prefetch_project_docs")
    assert "async" in tool["inputSchema"]["properties"]
    assert "DEPRECATED" in tool["description"]
    assert "prefetch_project_dependency_docs" in tool["description"]
    assert "May fetch from the network" in tool["description"]


def test_mcp_exposes_prefetch_project_dependency_docs_alias():
    assert "prefetch_project_dependency_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "prefetch_project_dependency_docs")

    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "DEPRECATED" not in tool["description"]
    assert "dependency documentation from project manifests/lockfiles" in tool["description"]
    assert "May fetch from the network" in tool["description"]


def test_mcp_hides_low_level_target_prefetch_from_public_surface():
    assert "prepare_docs" in {tool["name"] for tool in TOOLS}
    assert "prefetch_docs_targets" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in TOOLS if tool["name"] == "prepare_docs")
    assert "prefetch_docs_targets" not in tool["inputSchema"]["properties"]["action"]["enum"]


def test_mcp_exposes_bounded_inspection_through_prepare_docs():
    tool = next(tool for tool in TOOLS if tool["name"] == "prepare_docs")

    assert "inspect_docs_target" in tool["inputSchema"]["properties"]["action"]["enum"]
    assert tool["inputSchema"]["properties"]["max_pages"]["maximum"] == 5
    assert "target" in tool["inputSchema"]["properties"]

    class Service:
        received = None

        def inspect_docs_target(self, target, *, max_pages):
            self.received = (target, max_pages)
            return DocsTargetInspectionResult(
                status="ok",
                reason_code="docs_layout_observed",
                target=target,
                observations={"indexed": False, "scope_expanded": False},
            )

    service = Service()
    payload = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "inspect_docs_target",
            "target": {"library": "sample", "docs_url": "https://docs.example/api/"},
            "max_pages": 3,
        },
        service,
    )

    assert service.received == ({
        "library": "sample",
        "docs_url": "https://docs.example/api/",
        "allowed_domains": ["docs.example"],
        "path_prefixes": ["/api/"],
        "max_pages": 50,
    }, 3)
    assert payload["observations"]["indexed"] is False
    assert payload["action"] == "inspect_docs_target"


def test_prepare_docs_rejects_unbounded_inspection_before_service_call():
    result = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "inspect_docs_target",
            "target": {"library": "sample", "docs_url": "https://docs.example/api/"},
            "max_pages": 6,
        },
        object(),
    )

    assert result["reason_code"] == "validation_error"


def test_mcp_exposes_inspect_project_docs_with_discovery_first_guidance():
    assert "inspect_project_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "inspect_project_docs")

    assert "Call this first" in tool["description"]
    assert "Context7-like" in tool["description"]
    assert "reason_code" in tool["description"]
    assert "next_action" in tool["description"]
    assert "follow next_action" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_ingest_project_docs():
    assert "ingest_project_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "ingest_project_docs")

    assert "Legacy low-level index operation" in tool["description"]
    assert "Prefer sync_project_docs" in tool["description"]
    assert "does not ingest source code" in tool["description"]
    assert "does not ingest" in tool["description"]
    assert "dependency docs" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "skip_known" in tool["inputSchema"]["properties"]
    assert "with_vectors" in tool["inputSchema"]["properties"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_sync_project_docs():
    assert "sync_project_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "sync_project_docs")

    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "Canonical lifecycle action" in tool["description"]
    assert "remove orphaned/stale indexed docs" in tool["description"]
    assert "with_vectors" in tool["inputSchema"]["properties"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_bootstrap_project_docs_with_safe_stops():
    assert "bootstrap_project_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "bootstrap_project_docs")

    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "never writes repository files" in tool["description"]
    assert "never fetches dependency docs from the network" in tool["description"]
    assert "confirmation_required" in tool["description"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_get_project_docs_with_project_scoped_guidance():
    assert "get_project_docs" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "get_project_docs")

    assert "project-scoped filters" in tool["description"]
    assert "before WebFetch" in tool["description"]
    assert "reason_code" in tool["description"]
    assert "next_action" in tool["description"]
    assert "next_actions" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path", "query"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_get_project_context_with_trust_contract():
    assert "get_project_context" not in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "get_project_context")

    assert "Trust Contract" in tool["description"]
    assert "selected, rejected, and risky sources" in tool["description"]
    assert "after inspect_project_docs" in tool["description"]
    assert "sync_project_docs" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path", "question"]
    assert "mode" in tool["inputSchema"]["properties"]
    assert "libraries" in tool["inputSchema"]["properties"]
    assert tool["inputSchema"]["properties"]["output_mode"]["enum"] == ["answer", "compact", "debug", "full"]
    assert "details" in tool["inputSchema"]["properties"]


def test_agent_templates_include_three_tool_selection_guidance():
    from importlib.resources import files
    from docmancer.cli.commands import _get_template_content

    canonical = files("docmancer.templates").joinpath("agent_contract.md").read_text(encoding="utf-8").strip()
    for name in (
        "skill.md", "claude_code_skill.md", "claude_desktop_skill.md",
        "cursor_agents_md.md", "copilot_instructions.md", "project_bootstrap.md",
    ):
        raw = files("docmancer.templates").joinpath(name).read_text(encoding="utf-8")
        assert raw.count("{{CANONICAL_AGENT_CONTRACT}}") == 1
        assert "get_docs_context" not in raw.replace("{{CANONICAL_AGENT_CONTRACT}}", "")
        text = _get_template_content(name)
        assert text.count(canonical) == 1
        assert "get_docs_context" in text
        assert "prepare_docs" in text
        assert "docs_status" in text
        assert "retry the original `get_docs_context` question unchanged" in text
        assert "repository code search" in text
        assert "legacy direct documentation tools" in text


def test_project_docs_workflow_documents_index_template_and_verification_loop():
    docs = Path(__file__).resolve().parents[2] / "docs" / "project-docs-mcp-workflow.md"
    text = docs.read_text(encoding="utf-8")

    assert "## Maintained project-doc catalog" in text
    assert "docatlas.project-docs.yaml" in text
    assert "schema_version: 1" in text
    assert "indexes only validated catalog entries" in text
    assert "cold-start fallback" in text
    assert "fail closed with warnings" in text
    assert "## Verification loop" in text
    assert "inspect_project_docs(project_path)" in text
    assert "prepare_docs(action=\"sync_project_docs\"" in text
    assert "Confirm the expected files are cited" in text
    assert "get_docs_context(project_path=" in text


def test_mcp_docs_server_documents_index_and_smoke_test_loop():
    docs = Path(__file__).resolve().parents[2] / "docs" / "mcp-docs-server.md"
    text = docs.read_text(encoding="utf-8")

    assert "## Project documentation" in text
    assert "get_docs_context" in text
    assert "prepare_docs(action=\"sync_project_docs\"" in text
    assert "## Response and source rules" in text
    assert "docs_status" in text
    assert "does not generate or commit official documentation" in text


def test_mcp_exposes_docs_job_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "docs_status" in names
    assert "docs_job" not in names
    assert "get_docs_job_status" not in names
    assert "list_docs_jobs" not in names
    assert "cancel_docs_job" not in names


def test_prepare_docs_keeps_async_job_cancellation_on_public_surface():
    tool = next(tool for tool in TOOLS if tool["name"] == "prepare_docs")
    assert "cancel_docs_job" in tool["inputSchema"]["properties"]["action"]["enum"]
    assert "job_id" in tool["inputSchema"]["properties"]

    class Service:
        def cancel_docs_job(self, job_id):
            return DocsJobCancelResult(
                job_id=job_id,
                status="cancel_requested",
                message="Cancellation requested.",
            )

    missing = call_docs_tool_payload(
        "prepare_docs",
        {"action": "cancel_docs_job"},
        Service(),
    )
    cancelled = call_docs_tool_payload(
        "prepare_docs",
        {"action": "cancel_docs_job", "job_id": "job-1"},
        Service(),
    )

    assert missing["reason_code"] == "validation_error"
    assert cancelled == {
        "job_id": "job-1",
        "status": "cancel_requested",
        "message": "Cancellation requested.",
        "action": "cancel_docs_job",
        "tool": "prepare_docs",
    }


def test_prepare_docs_rejects_unscoped_library_removal_before_service_call():
    class Service:
        called = False

        def remove_library_docs(self, canonical_id):
            self.called = True
            raise AssertionError("validation should have stopped this call")

    service = Service()

    result = call_docs_tool_payload(
        "prepare_docs",
        {"action": "remove_library_docs", "canonical_id": "pub:go_router@14.8.1:api"},
        service,
    )

    assert result["reason_code"] == "validation_error"
    assert "project_path" in result["message"]
    assert service.called is False


def test_admin_remove_library_docs_rejects_unscoped_removal_before_service_call():
    class Service:
        called = False

        def remove_library_docs(self, canonical_id):
            self.called = True
            raise AssertionError("validation should have stopped this call")

    service = Service()
    surface = build_docs_surface(DocsServerConfig(expose_admin=True))

    result = call_docs_tool_payload(
        "remove_library_docs",
        {"canonical_id": "pub:go_router@14.8.1:api"},
        service,
        surface=surface,
    )

    assert result["reason_code"] == "validation_error"
    assert service.called is False


def test_admin_remove_library_docs_rejects_non_project_owned_scope_before_service_call(tmp_path):
    class Service:
        called = False

        def remove_library_docs(self, canonical_id):
            self.called = True
            raise AssertionError("validation should have stopped this call")

    service = Service()
    surface = build_docs_surface(DocsServerConfig(expose_admin=True))

    result = call_docs_tool_payload(
        "remove_library_docs",
        {
            "canonical_id": "pub:go_router@14.8.1:api",
            "project_path": str(tmp_path),
        },
        service,
        surface=surface,
    )

    assert result["reason_code"] == "validation_error"
    assert "project_path" in result["message"]
    assert service.called is False


def test_prepare_docs_rejects_unknown_and_action_irrelevant_fields_before_service_call():
    class Service:
        called = False

        def prefetch_docs(self, *args, **kwargs):
            self.called = True
            raise AssertionError("validation should have stopped this call")

    service = Service()
    unknown = call_docs_tool_payload(
        "prepare_docs",
        {"action": "prefetch_library_docs", "library": "kotlin", "unexpected": True},
        service,
    )
    irrelevant = call_docs_tool_payload(
        "prepare_docs",
        {"action": "sync_project_docs", "project_path": "/repo", "library": "kotlin"},
        service,
    )
    unsupported_dry_run = call_docs_tool_payload(
        "prepare_docs",
        {"action": "prefetch_library_docs", "library": "kotlin", "dry_run": True},
        service,
    )

    assert unknown["reason_code"] == "validation_error"
    assert irrelevant["reason_code"] == "validation_error"
    assert unsupported_dry_run["reason_code"] == "validation_error"
    assert service.called is False


def test_prepare_docs_rejects_invalid_types_before_service_call():
    class Service:
        called = False

        def prune_library_docs(self, **kwargs):
            self.called = True
            raise AssertionError("validation should have stopped this call")

        def prefetch_docs_targets(self, *args, **kwargs):
            self.called = True
            raise AssertionError("validation should have stopped this call")

    service = Service()
    invalid_days = call_docs_tool_payload(
        "prepare_docs",
        {"action": "prune_library_docs", "older_than_days": {}},
        service,
    )
    invalid_target = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "prefetch_docs_targets",
            "targets": [{"docs_url": "https://example.com", "max_pages": "bad"}],
        },
        service,
    )
    missing_target_library = call_docs_tool_payload(
        "prepare_docs",
        {"action": "prefetch_docs_targets", "targets": [{"docs_url": "https://example.com"}]},
        service,
    )

    assert invalid_days["reason_code"] == "validation_error"
    assert invalid_target["reason_code"] == "validation_error"
    assert missing_target_library["reason_code"] == "validation_error"
    assert service.called is False


def test_prepare_docs_forwards_bounded_incremental_sync_contract():
    from docmancer.docs.models import ProjectDocsSyncResult, ProjectMetadata

    class Service:
        received = None

        def sync_project_docs(self, project_path, **kwargs):
            self.received = (project_path, kwargs)
            return ProjectDocsSyncResult(status="success", project=ProjectMetadata(project_path=project_path))

    service = Service()
    result = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "sync_project_docs",
            "project_path": "/repo",
            "with_vectors": False,
            "changed_paths": ["docs/guide.md"],
            "deleted_paths": ["docs/old.md"],
            "renamed_paths": [{"old_path": "docs/a.md", "new_path": "docs/b.md"}],
        },
        service,
    )

    assert result["status"] == "success"
    assert service.received == (
        "/repo",
        {
            "with_vectors": False,
            "changed_paths": ["docs/guide.md"],
            "deleted_paths": ["docs/old.md"],
            "renamed_paths": [{"old_path": "docs/a.md", "new_path": "docs/b.md"}],
        },
    )


def test_prepare_docs_compacts_large_project_sync_inventory():
    from docmancer.docs.models import ProjectDocsSyncResult, ProjectMetadata

    class Service:
        def sync_project_docs(self, project_path, **_kwargs):
            return ProjectDocsSyncResult(
                status="success",
                project=ProjectMetadata(project_path=project_path),
                indexed_sources=[{"path": f"docs/{index}.md", "content": "x" * 500} for index in range(500)],
                current_count=500,
                diagnostics={"vector_sync": {
                    "status": "success", "requested": True, "verified": 500,
                    "backfilled": 2, "extra_points": 0, "collection": "project-vectors",
                    "retrieval_mode": "dense",
                }},
            )

    result = call_docs_tool_payload(
        "prepare_docs",
        {"action": "sync_project_docs", "project_path": "/repo"},
        Service(),
    )

    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 32_000
    assert result["summary"]["current_count"] == 500
    assert "indexed_sources" not in result
    assert result["vector_sync"] == {
        "status": "success", "requested": True, "verified": 500,
        "backfilled": 2, "extra_points": 0, "collection": "project-vectors",
        "retrieval_mode": "dense",
    }


def test_prepare_docs_rejects_malformed_incremental_sync_paths():
    class Service:
        def sync_project_docs(self, *_args, **_kwargs):
            raise AssertionError("validation should have stopped this call")

    malformed = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "sync_project_docs",
            "project_path": "/repo",
            "renamed_paths": [{"old_path": "docs/a.md"}],
        },
        Service(),
    )

    assert malformed["reason_code"] == "validation_error"


def test_prepare_docs_preserves_singular_version_for_library_prefetch():
    class Service:
        received = None

        def prefetch_docs(self, library, **kwargs):
            self.received = {"library": library, **kwargs}
            return DocsJobStartResult(job_id="job-1", status="running", message="started")

    service = Service()
    payload = call_docs_tool_payload(
        "prepare_docs",
        {
            "action": "prefetch_library_docs",
            "library": "kotlin",
            "ecosystem": "kotlin",
            "version": "1.8.1",
            "question": "coroutine cancellation",
        },
        service,
    )

    assert payload["status"] == "running"
    assert service.received["versions"] == ["1.8.1"]
    assert service.received["query"] == "coroutine cancellation"
    assert service.received["async_"] is True


def test_prepare_docs_rejects_synchronous_remote_prefetch():
    payload = call_docs_tool_payload(
        "prepare_docs",
        {"action": "prefetch_library_docs", "library": "kotlin", "async": False},
        object(),
    )

    assert payload["reason_code"] == "validation_error"


def test_prepare_docs_refresh_returns_a_background_job():
    class Service:
        received = None

        def prefetch_docs(self, library, **kwargs):
            self.received = {"library": library, **kwargs}
            return DocsJobStartResult(job_id="job-1", status="running", message="started")

    service = Service()
    payload = call_docs_tool_payload(
        "prepare_docs",
        {"action": "refresh_library_docs", "library": "kotlin", "version": "1.8.1"},
        service,
    )

    assert payload["status"] == "running"
    assert service.received["force_refresh"] is True
    assert service.received["async_"] is True


def test_mcp_exposes_three_public_tools_with_mutually_exclusive_guidance():
    tools = {tool["name"]: tool for tool in TOOLS}

    assert set(tools) == PUBLIC_TOOL_NAMES
    context_tool = tools["get_docs_context"]
    assert "Default source-grounded" in context_tool["description"]
    assert 'module_path always implies module scope' in context_tool["description"]
    assert 'make two bounded calls (module then project)' in context_tool["description"]
    assert 'scope=all without module filters' in context_tool["description"]
    context_properties = context_tool["inputSchema"]["properties"]
    assert "ambiguous names fail closed" in context_properties["module"]["description"]
    assert "always implies module scope" in context_properties["module_path"]["description"]
    assert "repo-level docs only" in context_properties["scope"]["description"]
    assert "project-pinned dependency docs" in context_properties["mode"]["description"]
    output_properties = context_tool["outputSchema"]["properties"]
    assert output_properties["module_candidates"]["maxItems"] == 8
    assert output_properties["module_candidates"]["items"]["required"] == ["module_path"]
    assert "Call only from get_docs_context" in tools["prepare_docs"]["description"]
    assert "explicitly asks" in tools["docs_status"]["description"]
    assert tools["docs_status"]["inputSchema"]["required"] == ["action"]
    assert "discovered module identities" in (
        tools["docs_status"]["inputSchema"]["properties"]["details"]["description"]
    )
    assert tools["docs_status"]["inputSchema"]["properties"]["action"]["enum"] == [
        "project",
        "library",
        "jobs",
        "job",
    ]


def test_docs_status_validates_required_action_arguments():
    class Service:
        def list_docs_jobs(self, **kwargs):
            return []

        def get_docs_job_status(self, job_id):
            return None

    project = call_docs_tool_payload(
        "docs_status",
        {"action": "project"},
        Service(),
    )
    job = call_docs_tool_payload(
        "docs_status",
        {"action": "job"},
        Service(),
    )
    jobs = call_docs_tool_payload(
        "docs_status",
        {"action": "jobs"},
        Service(),
    )

    assert project["reason_code"] == "project_path_required"
    assert job["reason_code"] == "job_id_required"
    assert jobs == {"tool": "docs_status", "action": "jobs", "jobs": []}


def test_mcp_exposes_manifest_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "prepare_docs" in names
    assert "validate_docs_manifest" not in names
    assert "prefetch_docs_manifest" not in names


def test_mcp_exposes_lifecycle_tools():
    names = {tool["name"] for tool in TOOLS}
    all_names = {tool["name"] for tool in ALL_TOOLS}
    assert "list_docs_sources" not in names
    assert "list_docs_sources" in all_names
    assert "inspect_library_docs" not in names
    assert "remove_library_docs" not in names
    assert "prune_library_docs" not in names


def test_mcp_exposes_discoverable_resources_and_templates():
    resource_uris = {resource["uri"] for resource in MCP_RESOURCES}
    template_uris = {template["uriTemplate"] for template in MCP_RESOURCE_TEMPLATES}

    assert "docmancer://workflow/project-docs" in resource_uris
    assert "docmancer://schema/trust-contract" in resource_uris
    assert "docmancer://workflow/library-docs" in resource_uris
    assert "docmancer://workflow/project-docs/{project_path}" in template_uris
    assert "docmancer://library/{ecosystem}/{library}/{version}" in template_uris


def test_maintained_agent_docs_prefer_public_docs_workflow():
    repo = Path(__file__).resolve().parents[2]
    docs = [
        repo / "AGENTS.md",
        repo / "README.md",
        repo / "SKILL.md",
        repo / "docs" / "AGENT_DOCS_WORKFLOW.md",
        repo / "docs" / "PROJECT_MAP.md",
        repo / "docs" / "mcp-docs-server.md",
        repo / "docs" / "project-docs-demo.md",
        repo / "docs" / "project-docs-mcp-workflow.md",
        repo / "wiki" / "Architecture.md",
    ]
    joined = "\n".join(path.read_text() for path in docs)

    assert "prepare_docs(action=\"sync_project_docs\"" in joined
    assert "get_docs_context(" in joined
    assert "docs_status" in joined
    assert "exactly three" in joined
    assert "bootstrap_project_docs(project_path" not in joined
    assert "sync_project_docs(project_path" not in joined
    assert "get_project_context(project_path" not in joined


def test_mcp_read_resource_returns_workflow_and_schema_guidance():
    workflow = read_docs_resource("docmancer://workflow/project-docs")
    library_workflow = read_docs_resource("docmancer://workflow/library-docs")
    schema = read_docs_resource("docmancer://schema/trust-contract")
    selection = read_docs_resource("docmancer://agent/tool-selection")
    templated = read_docs_resource("docmancer://workflow/project-docs//repo")
    library_templated = read_docs_resource("docmancer://library/python/mcp/latest")

    assert workflow is not None
    assert "get_docs_context" in workflow["text"]
    assert "next_action" in workflow["text"]
    assert "trust_contract.sources" in workflow["text"]
    assert library_workflow is not None
    assert "get_docs_context" in library_workflow["text"]
    assert "mode=\"library\"" in library_workflow["text"]
    assert "response_style=\"snippet-first\"" not in library_workflow["text"]
    assert "Legacy tools" in library_workflow["text"]
    assert "resolve_library_id" not in library_workflow["text"].split("Legacy tools")[0]
    assert "get_library_docs" not in library_workflow["text"].split("Legacy tools")[0]
    assert "Do not use WebFetch" in library_workflow["text"]
    assert schema is not None
    assert '"schema_version": "trust-contract-1.2"' in schema["text"]
    assert '"selected"' in schema["text"]
    assert selection is not None
    assert "Natural documentation" in selection["text"]
    assert "get_docs_context" in selection["text"]
    assert "prepare_docs" in selection["text"]
    assert "docs_status" in selection["text"]
    assert templated is not None
    assert 'project_path="/repo"' in templated["text"]
    assert "get_docs_context" in templated["text"]
    assert library_templated is not None
    assert 'library="mcp"' in library_templated["text"]
    assert 'ecosystem="python"' in library_templated["text"]
    assert "get_docs_context" in library_templated["text"]
    assert "prepare_docs" in library_templated["text"]
    assert "resolve_library_id" not in library_templated["text"].split("Do not assume legacy")[0]
    assert read_docs_resource("docmancer://missing") is None


def test_mcp_prefetch_targets_infers_allowed_domains_from_explicit_urls():
    targets = _bounded_targets([{"library": "go_router", "docs_url": "https://pub.dev/packages/go_router"}])

    assert targets[0]["allowed_domains"] == ["pub.dev"]
