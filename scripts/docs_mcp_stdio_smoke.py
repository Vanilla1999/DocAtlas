#!/usr/bin/env python3
"""Offline smoke for the installed wheel's primary three-tool Docs MCP."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from docmancer.mcp.agent_config import AgentTarget, register_server

TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}
QUESTION = "What does the project README say about deterministic offline release checks?"
NEEDLE = "The amber lighthouse invariant requires deterministic offline release checks."


def payload(result: object) -> dict:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", [])
    if not content or not hasattr(content[0], "text"):
        raise AssertionError(f"missing JSON tool response: {result!r}")
    return json.loads(content[0].text)


def text_payload(result: object) -> dict:
    if getattr(result, "structuredContent", None) is not None:
        raise AssertionError("text-only compatibility response included structuredContent")
    content = getattr(result, "content", [])
    if not content or not hasattr(content[0], "text"):
        raise AssertionError(f"missing JSON text-only tool response: {result!r}")
    return json.loads(content[0].text)


async def smoke() -> None:
    # The parsers below are provider-free release contracts. Import the MCP
    # client only when the installed-artifact smoke is actually executed.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with tempfile.TemporaryDirectory(prefix="docatlas-release-smoke-") as raw:
        root = Path(raw)
        project = root / "project"
        project.mkdir()
        (project / "README.md").write_text(f"# Release contract\n\n{NEEDLE}\n")
        home = root / "home"
        home.mkdir()
        env = {**os.environ, "HOME": str(home), "DOCMANCER_HOME": str(home), "NO_PROXY": "*"}
        params = StdioServerParameters(command="doc-atlas", args=["mcp", "docs-serve"], env=env, cwd=str(root))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert names == TOOLS, f"unexpected public Docs tools: {sorted(names)}"
                # Canonical public default: advertised fields only.  Do not
                # accidentally exercise the hidden compatibility projection.
                canonical_query = {
                    "question": QUESTION,
                    "project_path": str(project),
                    "mode": "project",
                }
                compatibility_query = {**canonical_query, "output_mode": "compact"}
                assert set(canonical_query) == {"question", "project_path", "mode"}
                await session.call_tool("get_docs_context", canonical_query)
                sync = payload(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(project), "with_vectors": False,
                }))
                assert sync.get("status") not in {"error", "failed"}, sync
                answer = payload(await session.call_tool("get_docs_context", canonical_query))
                rendered = json.dumps(answer, sort_keys=True)
                assert "README.md" in rendered, answer
                assert NEEDLE in rendered, answer
                sources = answer.get("sources") or answer.get("selected_sources") or answer.get("context_pack") or []
                assert any(
                    source.get("path_or_url") == "README.md" or source.get("path") == "README.md"
                    for source in sources
                ), answer
                compatibility_answer = payload(
                    await session.call_tool("get_docs_context", compatibility_query)
                )
                assert compatibility_answer.get("output_mode") == "compact", compatibility_answer
        config_path = home / "opencode.json"
        register_server(AgentTarget("opencode", config_path, "json_opencode_mcp"))
        registrations = json.loads(config_path.read_text())["mcp"]
        assert "docmancer" not in registrations, registrations
        entry = registrations["docatlas"]
        assert entry["environment"]["DOCATLAS_MCP_TEXT_FALLBACK"] == "1", entry
        command = entry["command"]
        opencode_params = StdioServerParameters(
            command=command[0],
            args=command[1:],
            env={**env, **entry["environment"]},
            cwd=str(root),
        )
        async with stdio_client(opencode_params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                # Text fallback remains a separate compatibility smoke.
                compatibility_query = {
                    "question": QUESTION,
                    "project_path": str(project),
                    "mode": "project",
                    "output_mode": "compact",
                }
                text_answer = text_payload(
                    await session.call_tool("get_docs_context", compatibility_query)
                )
                rendered = json.dumps(text_answer, sort_keys=True)
                assert "README.md" in rendered, text_answer
                assert NEEDLE in rendered, text_answer
    print("Docs MCP installed-artifact stdio smoke: PASS")


if __name__ == "__main__":
    asyncio.run(smoke())
