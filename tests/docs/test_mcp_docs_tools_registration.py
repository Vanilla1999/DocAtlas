from __future__ import annotations

from pathlib import Path

from docmancer.docs.interfaces.mcp.context_tools import CONTEXT_TOOL_NAMES
from docmancer.docs.interfaces.mcp.docs_tools import LIBRARY_TOOL_NAMES
from docmancer.docs.interfaces.mcp.prefetch_tools import PREFETCH_TOOL_NAMES
from docmancer.docs.interfaces.mcp.project_tools import PROJECT_TOOL_NAMES
from docmancer.mcp.docs_server import CONTEXT_TOOLS, LIBRARY_TOOLS, PREFETCH_TOOLS, PROJECT_TOOLS, TOOLS


def test_mcp_grouped_tool_registration_preserves_tool_names():
    grouped_names = {tool["name"] for tool in [*CONTEXT_TOOLS, *LIBRARY_TOOLS, *PREFETCH_TOOLS, *PROJECT_TOOLS]}
    all_names = {tool["name"] for tool in TOOLS}

    assert grouped_names == all_names
    assert {tool["name"] for tool in CONTEXT_TOOLS} == CONTEXT_TOOL_NAMES
    assert {tool["name"] for tool in LIBRARY_TOOLS} == LIBRARY_TOOL_NAMES
    assert {tool["name"] for tool in PREFETCH_TOOLS} == PREFETCH_TOOL_NAMES
    assert {tool["name"] for tool in PROJECT_TOOLS} == PROJECT_TOOL_NAMES


def test_mcp_grouped_tool_registration_keeps_original_order_within_groups():
    positions = {tool["name"]: index for index, tool in enumerate(TOOLS)}

    for group in (CONTEXT_TOOLS, LIBRARY_TOOLS, PREFETCH_TOOLS, PROJECT_TOOLS):
        assert [positions[tool["name"]] for tool in group] == sorted(positions[tool["name"]] for tool in group)


def test_mcp_exposes_prefetch_library_docs():
    assert "prefetch_library_docs" in {tool["name"] for tool in TOOLS}


def test_mcp_get_library_docs_guides_retry_before_webfetch():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_library_docs")

    assert "Registered sources do not require docs_url" in tool["description"]
    assert "call inspect_project_docs first" in tool["description"]
    assert "repo-specific architecture" in tool["description"]
    assert "never WebFetch registered docs before that retry" in tool["description"]


def test_mcp_exposes_prefetch_project_docs():
    assert "prefetch_project_docs" in {tool["name"] for tool in TOOLS}
    tool = next(tool for tool in TOOLS if tool["name"] == "prefetch_project_docs")
    assert "async" in tool["inputSchema"]["properties"]
    assert "dependency docs" in tool["description"]
    assert "not project-owned README/docs/wiki files" in tool["description"]
    assert "May fetch from the network" in tool["description"]


def test_mcp_exposes_prefetch_project_dependency_docs_alias():
    tool = next(tool for tool in TOOLS if tool["name"] == "prefetch_project_dependency_docs")

    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "Alias for prefetch_project_docs" in tool["description"]
    assert "dependency documentation from project manifests/lockfiles" in tool["description"]
    assert "May fetch from the network" in tool["description"]


def test_mcp_exposes_prefetch_docs_targets():
    assert "prefetch_docs_targets" in {tool["name"] for tool in TOOLS}


def test_mcp_exposes_inspect_project_docs_with_discovery_first_guidance():
    tool = next(tool for tool in TOOLS if tool["name"] == "inspect_project_docs")

    assert "Call this first" in tool["description"]
    assert "Context7-like" in tool["description"]
    assert "reason_code" in tool["description"]
    assert "next_action" in tool["description"]
    assert "Follow next_action" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_ingest_project_docs():
    tool = next(tool for tool in TOOLS if tool["name"] == "ingest_project_docs")

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
    tool = next(tool for tool in TOOLS if tool["name"] == "sync_project_docs")

    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "Canonical lifecycle action" in tool["description"]
    assert "remove orphaned/stale indexed docs" in tool["description"]
    assert "with_vectors" in tool["inputSchema"]["properties"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_bootstrap_project_docs_with_safe_stops():
    tool = next(tool for tool in TOOLS if tool["name"] == "bootstrap_project_docs")

    assert tool["inputSchema"]["required"] == ["project_path"]
    assert "never writes repository files" in tool["description"]
    assert "never fetches dependency docs from the network" in tool["description"]
    assert "confirmation_required" in tool["description"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_get_project_docs_with_project_scoped_guidance():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_project_docs")

    assert "project-scoped filters" in tool["description"]
    assert "before WebFetch" in tool["description"]
    assert "reason_code" in tool["description"]
    assert "next_action" in tool["description"]
    assert "next_actions" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path", "query"]
    assert "details" in tool["inputSchema"]["properties"]


def test_mcp_exposes_get_project_context_with_trust_contract():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_project_context")

    assert "Trust Contract" in tool["description"]
    assert "selected, rejected, and risky sources" in tool["description"]
    assert "after inspect_project_docs" in tool["description"]
    assert "sync_project_docs" in tool["description"]
    assert tool["inputSchema"]["required"] == ["project_path", "question"]
    assert "mode" in tool["inputSchema"]["properties"]
    assert "libraries" in tool["inputSchema"]["properties"]
    assert "details" in tool["inputSchema"]["properties"]


def test_agent_templates_include_project_docs_discovery_guidance():
    template_dir = Path(__file__).resolve().parents[2] / "docmancer" / "templates"

    for name in ("skill.md", "claude_code_skill.md", "claude_desktop_skill.md"):
        text = (template_dir / name).read_text(encoding="utf-8")
        assert "Project Docs Discovery with MCP" in text
        assert "inspect_project_docs(project_path=\".\")" in text
        assert "expects Context7-like help" in text
        assert "prefetch_project_docs` fetches exact dependency docs" in text
        assert "Official project docs should remain files in the repo" in text
        assert "Do not skip `inspect_project_docs`" in text
        assert "docs/INDEX.md" in text
        assert "canonical map of project-owned docs" in text
        assert "verification loop" in text
        assert "confirm expected files are cited" in text


def test_project_docs_workflow_documents_index_template_and_verification_loop():
    docs = Path(__file__).resolve().parents[2] / "docs" / "project-docs-mcp-workflow.md"
    text = docs.read_text(encoding="utf-8")

    assert "## Maintained docs index" in text
    assert "docs/INDEX.md" in text
    assert "# Documentation Index" in text
    assert "canonical map of maintained project-owned documentation" in text
    assert "Generated or tooling docs to ignore" in text
    assert "indexed_source_not_discovered" in text
    assert "## Verification loop" in text
    assert "inspect_project_docs(project_path)" in text
    assert "sync_project_docs(project_path, with_vectors=true)" in text
    assert "Confirm the expected files are cited" in text
    assert "get_project_context(project_path" in text


def test_mcp_docs_server_documents_index_and_smoke_test_loop():
    docs = Path(__file__).resolve().parents[2] / "docs" / "mcp-docs-server.md"
    text = docs.read_text(encoding="utf-8")

    assert "## Maintained docs index and verification" in text
    assert "docs/INDEX.md" in text
    assert "canonical map of official project-owned docs" in text
    assert "inspect_project_docs(project_path)" in text
    assert "sync_project_docs(project_path, with_vectors=true)" in text
    assert "confirm expected files appear" in text
    assert "indexed_source_not_discovered" in text
    assert "Treat maintained `docs/INDEX.md` as the canonical map" in text


def test_mcp_exposes_docs_job_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "get_docs_job_status" in names
    assert "list_docs_jobs" in names
    assert "cancel_docs_job" in names


def test_mcp_exposes_manifest_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "validate_docs_manifest" in names
    assert "prefetch_docs_manifest" in names


def test_mcp_exposes_lifecycle_tools():
    names = {tool["name"] for tool in TOOLS}
    assert "inspect_library_docs" in names
    assert "remove_library_docs" in names
    assert "prune_library_docs" in names
