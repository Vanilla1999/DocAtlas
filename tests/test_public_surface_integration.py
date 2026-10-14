"""Real CLI processes and MCP stdio sessions, with isolated storage and no models.

This is a public boundary smoke, not a substitute for indexed delivery or the
full installed-artifact matrix. Existing indexed/MCP quality gates remain active.
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from scripts.docs_mcp_stdio_smoke import isolated_environment, read_only_delivery


def test_public_cli_and_cold_stdio_contract_without_implicit_preparation(record_property):
    """Four CLI processes, four MCP sessions; no preparation or model calls."""
    receipts = []
    with tempfile.TemporaryDirectory(prefix=".docatlas-public-surface-", dir=Path.home()) as raw:
        root = Path(raw)
        env = isolated_environment(root)
        for arguments in (("--help",), ("--version",), ("query", "--help"),
                          ("mcp", "docs-serve", "--help")):
            process = subprocess.run(
                [sys.executable, "-I", "-m", "docmancer.cli", *arguments],
                cwd=root, env=env, capture_output=True, text=True, timeout=30, check=True,
            )
            assert process.stdout.strip(), arguments
            if arguments == ("--version",):
                assert importlib.metadata.version("doc-atlas") in process.stdout
            if arguments == ("mcp", "docs-serve", "--help"):
                assert "docs-serve" in process.stdout
            receipts.append({"boundary": "cli", "arguments": arguments, "returncode": process.returncode})

        async def matrix():
            for text_only in (False, True):
                for advanced in (False, True):
                    case = root / f"stdio-{int(text_only)}-{int(advanced)}"
                    case.mkdir(mode=0o700)
                    server_env = isolated_environment(case)
                    server_env.update({"DOCATLAS_MCP_ADVANCED_TOOLS": str(int(advanced)),
                                       "DOCATLAS_MCP_ADMIN_TOOLS": "0"})
                    if text_only:
                        server_env["DOCATLAS_MCP_TEXT_FALLBACK"] = "1"
                    project = case / "project"
                    project.mkdir()
                    source = project / "README.md"
                    original = b"# Transport\n\nThe command is `doc-atlas mcp docs-serve`.\n"
                    source.write_bytes(original)
                    with (case / "server.stderr").open("w") as errors:
                        parameters = StdioServerParameters(
                            command=sys.executable, args=["-I", "-m", "docmancer.cli", "mcp", "docs-serve"],
                            env=server_env, cwd=str(case),
                        )
                        async with stdio_client(parameters, errlog=errors) as streams:
                            async with ClientSession(*streams) as session:
                                await session.initialize()
                                await read_only_delivery(session, project, text_only=text_only, advanced=advanced)
                    assert source.read_bytes() == original
                    assert not (Path(server_env["DOCATLAS_HOME"]) / "mcp-members").exists()
                    assert not (Path(server_env["HOME"]) / ".docmancer").exists()
                    receipts.append({"boundary": "stdio", "text_only": text_only,
                                     "advanced": advanced, "implicit_preparations": 0})
        asyncio.run(asyncio.wait_for(matrix(), timeout=120))
    record_property("public_surface", json.dumps(receipts, ensure_ascii=False))
