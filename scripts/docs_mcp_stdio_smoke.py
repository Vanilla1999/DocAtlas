#!/usr/bin/env python3
"""Offline smoke for the installed wheel's primary three-tool Docs MCP."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}
QUESTION = "What does the project README say about deterministic offline release checks?"
NEEDLE = "The amber lighthouse invariant requires deterministic offline release checks."


def payload(result: object) -> dict:
    content = getattr(result, "content", [])
    if not content or not hasattr(content[0], "text"):
        raise AssertionError(f"missing JSON tool response: {result!r}")
    return json.loads(content[0].text)


async def smoke() -> None:
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
                query = {"question": QUESTION, "project_path": str(project), "mode": "project"}
                await session.call_tool("get_docs_context", query)
                sync = payload(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(project), "with_vectors": False,
                }))
                assert sync.get("status") not in {"error", "failed"}, sync
                answer = payload(await session.call_tool("get_docs_context", query))
                rendered = json.dumps(answer, sort_keys=True)
                assert "README.md" in rendered, answer
                sources = answer.get("selected_sources") or []
                assert any(source.get("path") == "README.md" for source in sources), answer
    print("Docs MCP installed-artifact stdio smoke: PASS")


if __name__ == "__main__":
    asyncio.run(smoke())
