#!/usr/bin/env python3
"""Real installed-artifact stdio delivery smoke; no mocked retrieval or providers.

--read-only checks the runnable pre-lifecycle delivery surface. It never claims
the indexed/large-packet matrix passed. The full smoke requires the explicit
member lexical lifecycle API and fails closed if that API is unavailable.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from docmancer.mcp.agent_config import AgentTarget, register_server

TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}
QUESTION = "Which command starts the Docs MCP server?"
NEEDLE = "doc-atlas mcp docs-serve"


def payload(result: object) -> dict:
    assert not getattr(result, "isError", False), result
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", [])
    assert len(content) == 1 and isinstance(getattr(content[0], "text", None), str), result
    value = json.loads(content[0].text)
    assert isinstance(value, dict), value
    return value


def text_payload(result: object) -> dict:
    if getattr(result, "structuredContent", None) is not None:
        raise AssertionError("text-only compatibility response included structuredContent")
    return payload(result)


def validate_context_payload(answer: dict, *, required_fragment: str) -> None:
    assert answer.get("status") == "ok", answer
    assert answer.get("kind") in {"docs_answer", "docs_context"}, answer
    if answer["kind"] == "docs_context":
        assert answer.get("support_status") == "retrieval_only", answer
        assert answer.get("context_status") == "ready", answer
        assert answer.get("answer_supported") is False, answer
        assert answer.get("answer_available") is False, answer
    else:
        assert answer.get("support_status") == "supported", answer
        assert answer.get("answer_supported") is True, answer
        assert answer.get("answer_available") is True, answer
    assert required_fragment in json.dumps(answer), answer
    assert answer.get("sources"), answer
    for source in answer["sources"]:
        assert source.get("path_or_url") and source.get("snippet"), source
        digest = source.get("content_sha256", "")
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), source


def validate_patch_payload(answer: dict, *, completeness: str | None = None) -> None:
    assert answer.get("kind") == "patch_context" and answer.get("schema_version") == 4, answer
    assert answer.get("edit_ready") is False, answer
    assert answer.get("result") in {"data", "failure"}, answer
    if completeness is not None:
        assert answer.get("completeness") == completeness, answer
    for source in answer.get("sources", []):
        text = source["text"]
        assert source["content_sha256"] == hashlib.sha256(text.encode()).hexdigest(), source
        assert source["char_end"] - source["char_start"] == len(text), source
        assert source["instruction_trust"] == "untrusted_data", source


def _accept_fixture(project: Path) -> None:
    for args in (("init", "-q"), ("config", "core.autocrlf", "false"),
                 ("config", "user.email", "fixture@example.test"),
                 ("config", "user.name", "Docs MCP smoke fixture"),
                 ("add", "."), ("commit", "-qm", "accepted fixture documentation")):
        subprocess.run(["git", "-C", str(project), *args], stdin=subprocess.DEVNULL,
                       check=True, timeout=15)


def _read_fixture_job_state(database: Path, job_id: str) -> tuple[str] | None:
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        return db.execute("SELECT status FROM docs_jobs WHERE job_id = ?", (job_id,)).fetchone()


def isolated_environment(root: Path) -> dict[str, str]:
    # Do not inherit caller config, credentials, Python overlays or provider flags.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
           if key in os.environ}
    for key, relative in {"HOME": "user-home", "USERPROFILE": "user-home",
                          "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                          "XDG_CACHE_HOME": "cache", "DOCATLAS_HOME": "docatlas-home"}.items():
        path = root / relative
        path.mkdir(exist_ok=True)
        env[key] = str(path)
    env.update({"PYTHONNOUSERSITE": "1", "DOCATLAS_AUTO_VECTORS": "0",
                "DOCATLAS_REGISTRY_API_URL": "http://127.0.0.1:1", "NO_PROXY": "*"})
    return env


async def read_only_delivery(session, project: Path, *, text_only: bool) -> None:
    decode = text_payload if text_only else payload
    names = {tool.name for tool in (await session.list_tools()).tools}
    assert names == TOOLS, names
    canonical_query = {"question": QUESTION, "project_path": str(project)}
    assert set(canonical_query) == {"question", "project_path"}
    result = await session.call_tool("get_docs_context", canonical_query)
    if not text_only:
        assert isinstance(result.structuredContent, dict), result
    docs = decode(result)
    assert docs.get("kind") != "patch_context", docs
    assert not docs.get("edit_ready") and not docs.get("answer_supported"), docs
    patch = decode(await session.call_tool("get_docs_context", {
        **canonical_query, "context_format": "patch_context"}))
    validate_patch_payload(patch)
    assert patch.get("result") == "failure" and not patch.get("sources"), patch
    for extra in ({"mutation_intent": {"operation": "delete", "confirm": True}},
                  {"edit_ready": True}, {"allow_network": True, "consent": True}):
        rejected = await session.call_tool("get_docs_context", {**canonical_query, **extra})
        if not rejected.isError:
            response = decode(rejected)
            assert response.get("status") in {"error", "failed"}, response
    assert (project / "README.md").read_text().endswith(f"`{NEEDLE}`.\n")


async def indexed_delivery(session, project: Path, *, text_only: bool) -> None:
    # A's member lifecycle recipe must supply an explicit validated mutation.
    # Never fall back to status.next_action, clean Git state or unguarded sync.
    raise RuntimeError("BLOCKED: explicit member lexical lifecycle recipe is not yet integrated; "
                       "indexed partial/complete/>32KB and positive scope/version smoke NOT RUN")


async def smoke(*, read_only: bool = False) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import docmancer

    checkout = Path(__file__).resolve().parents[1]
    imported = Path(docmancer.__file__).resolve()
    assert not imported.is_relative_to(checkout), f"smoke imported checkout instead of installed wheel: {imported}"
    executable = shutil.which("doc-atlas")
    assert executable, "installed doc-atlas console script not found"
    with tempfile.TemporaryDirectory(prefix="docatlas-release-smoke-") as raw:
        root = Path(raw)
        env = isolated_environment(root)
        project = root / "project"
        project.mkdir()
        (project / "README.md").write_text(
            f"# Docs MCP server\n\nThe command that starts the Docs MCP server is `{NEEDLE}`.\n",
            encoding="utf-8")
        _accept_fixture(project)
        config_path = root / "user-home" / "opencode.json"
        register_server(AgentTarget("opencode", config_path, "json_opencode_mcp"))
        registrations = json.loads(config_path.read_text())["mcp"]["servers"]
        assert set(registrations) == {"docatlas"}, registrations
        entry = registrations["docatlas"]
        assert "enabled" not in entry and not entry.get("disabled"), entry
        for text_only in (False, True):
            params = StdioServerParameters(command=executable, args=entry["command"][1:],
                env={**env, **(entry["environment"] if text_only else {})}, cwd=str(root))
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    await read_only_delivery(session, project, text_only=text_only)
                    if not read_only:
                        await indexed_delivery(session, project, text_only=text_only)
        assert not (root / "user-home" / ".docmancer").exists()
    if read_only:
        print("Installed read-only stdio delivery: PASS (structured/text, empty patch, unauthorized fields). "
              "Indexed lifecycle/partial/complete/>32KB/scope/version NOT RUN.")
    else:
        print("Docs MCP installed-artifact stdio smoke: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true")
    asyncio.run(smoke(read_only=parser.parse_args().read_only))
