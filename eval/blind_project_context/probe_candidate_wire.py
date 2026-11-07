"""Installed stdio candidate delivery through the real public docs tool.

One independent authored document; no benchmark/holdout access or component mocks.
"""
import asyncio
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pytest import MonkeyPatch

from docmancer.docs.application.context_assembly import decode_context
from docmancer.docs.application.projection_tokenizer import projection_token_count
from tests._fixture_member_transaction import indexed_fixture_member_service


async def run(*, source_tree=False):
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="step10-wire-", dir="/tmp/opencode") as directory, MonkeyPatch.context() as env:
        root = Path(directory)
        env.setenv("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT", "1")
        env.setenv("DOCATLAS_EXPERIMENT_MINI_PATH", "/tmp/opencode/step10-mini-assets")
        env.setenv("DOCATLAS_CONTEXT_COMPRESSION", "off")
        env.setenv("DOCATLAS_MCP_MODEL_VIEW", "1")
        env.setenv("DOCATLAS_MCP_COMPACT_TEXT", "1")
        env.delenv("DOCATLAS_MCP_TEXT_FALLBACK", raising=False)
        if source_tree:
            env.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[2]))
        else:
            env.delenv("PYTHONPATH", raising=False)
        project = root / "project"
        source_path = "docs/" + "/".join(f"procedure-{n}-" + "x" * 80 for n in range(6)) + "/retry.md"
        (project / source_path).parent.mkdir(parents=True)
        (project / "pyproject.toml").write_text('[project]\nname="wire-probe"\nversion="0.1"\n')
        # Long legitimate heading catches a hidden legacy 300-character source
        # projection rejection without changing the required procedure facts.
        source = "# Retry procedure " + "documented procedure " * 16 + "\r\nRetry only after a terminal job status.\r\nA cancellation acknowledgement is not terminal.\r\n"
        (project / source_path).write_bytes(source.encode())
        (project / "docatlas.project-docs.yaml").write_text(
            f"schema_version: 1\ndocuments:\n  - path: {source_path}\n    role: runbook\n"
            "    scope: project\n    authority: source_of_truth\n    status: active\n"
            "    description: Retry procedure\n")
        service, _ = indexed_fixture_member_service(root, env, project, (source_path,))
        config = root / "host.json"
        config.write_text(json.dumps(service.config.model_dump(mode="json")))
        config.chmod(0o600)
        params = StdioServerParameters(command=str(Path(sys.executable).with_name("doc-atlas")),
            args=["mcp", "docs-serve", "--config", str(config)], env=dict(os.environ), cwd=str(root))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools = await session.list_tools()
                source_tool = next(tool for tool in tools.tools if tool.name == "read_docs_source")
                assert source_tool.outputSchema is None
                response = await session.call_tool("get_docs_context", {
                    "question": "When may I retry a cancelled job?", "project_path": str(project),
                    "source_path": source_path, "scope": "project"})
                assert not response.isError, response
                assert response.structuredContent is None and len(response.content) == 1, response
                wire = response.content[0].text
                packet = decode_context(json.loads(wire))
                assert packet["sources"] and "source_selection" in packet, packet
                assert "".join(row["text"] for row in packet["sources"]).encode() == source.encode(), packet
                assert all(row["path"] == source_path for row in packet["sources"])
                assert projection_token_count(wire.encode()) <= 50000
                uri = packet["sources"][0]["source_uri"]
                source_read = await session.call_tool("read_docs_source", {"uri": uri})
                assert source_read.structuredContent is None and len(source_read.content) == 1
                assert json.loads(source_read.content[0].text) == {"status": "complete", "reason_code": "end_of_source"}
                replay = await session.call_tool("read_docs_source", {"uri": uri})
                assert replay.structuredContent is None and len(replay.content) == 1
                assert json.loads(replay.content[0].text)["status"] == "source_unavailable"
                invalid = await session.call_tool("get_docs_context", {"question": "When may I retry?"})
                assert invalid.isError and invalid.structuredContent is None
                error = json.loads(invalid.content[0].text)
                assert error["error"]["reason_code"] == "docs_context_target_missing", error
        return {"status": "pass", "boundary": ("source-tree" if source_tree else "installed") + " doc-atlas stdio MCP + real MiniLM + SQLite + filesystem",
                "tool_calls": 4, "native_source_read_and_replay": True, "wire_tokens": projection_token_count(wire.encode()),
                "source_bytes": len(source.encode()), "single_text_no_structured_duplicate": True,
                "legacy_flag_conflict_bypassed": True, "seconds": round(time.monotonic() - started, 3)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tree", action="store_true", help="Explicit source override when shared installed wheel is stale")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(source_tree=args.source_tree)), indent=2))
