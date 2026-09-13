#!/usr/bin/env python3
"""Offline smoke for the installed wheel's primary three-tool Docs MCP."""
from __future__ import annotations

import asyncio
from contextlib import closing
import json
import os
import sys
import tempfile
import string
import subprocess
import sqlite3
import time
from pathlib import Path

from docmancer.mcp.agent_config import AgentTarget, register_server

TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}
QUESTION = "Which command starts the Docs MCP server?"
NEEDLE = "doc-atlas mcp docs-serve"


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


def validate_context_payload(answer: dict, *, required_fragment: str) -> None:
    assert answer.get("status") == "ok", answer
    kind = answer.get("kind")
    assert kind in {"docs_answer", "docs_context"}, answer
    if kind == "docs_answer":
        assert answer.get("support_status") == "supported", answer
        assert answer.get("answer_supported") is True, answer
        assert answer.get("answer_available") is True, answer
    else:
        assert answer.get("support_status") == "retrieval_only", answer
        assert answer.get("context_status") == "ready", answer
        assert answer.get("answer_supported") is False, answer
        assert answer.get("answer_available") is False, answer
    rendered = json.dumps(answer, sort_keys=True)
    assert required_fragment in rendered, answer
    sources = answer.get("sources") or []
    assert sources, answer
    for source in sources:
        digest = str(source.get("content_sha256") or "")
        assert source.get("path_or_url"), source
        assert source.get("snippet"), source
        assert len(digest) == 64 and all(char in string.hexdigits.lower()[:16] for char in digest), source


def _accept_fixture(project: Path) -> None:
    """Commit only the temporary public fixture, never the caller's repository."""
    for args in (
        ("init", "-q"),
        ("config", "core.autocrlf", "false"),
        ("config", "user.email", "fixture@example.test"),
        ("config", "user.name", "Docs MCP smoke fixture"),
        ("add", "."),
        ("commit", "-qm", "accepted fixture documentation"),
    ):
        subprocess.run(["git", "-C", str(project), *args], check=True, timeout=15)


def _read_fixture_job_state(database: Path, job_id: str) -> tuple[str] | None:
    """Read one state and release its handle before temporary-fixture cleanup."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        return db.execute("SELECT status FROM docs_jobs WHERE job_id = ?", (job_id,)).fetchone()


async def lifecycle_smoke(session: object, root: Path) -> None:
    """Scripted lifecycle checks on the same real installed MCP connection.

    Status/preparation calls here are explicit fixture lifecycle requests, not
    speculative model actions. No live model, network fetch or new polling
    policy is involved. A locally invalid manifest fails before source fetching.
    """
    project = root / "lifecycle-project"
    project.mkdir()
    (project / "README.md").write_text(
        f"# Docs MCP server\n\nThe command that starts the Docs MCP server is `{NEEDLE}`.\n",
        encoding="utf-8", newline="\n",
    )
    _accept_fixture(project)
    original = {"question": QUESTION, "project_path": str(project)}
    initial = payload(await session.call_tool("get_docs_context", original))
    assert not initial.get("answer_supported"), initial
    status_args = {"action": "project", "project_path": str(project), "details": True}
    inspected = payload(await session.call_tool("docs_status", status_args))["project"]
    assert inspected["source_summary"]["indexed"] == 0, inspected
    action = inspected["next_action"]
    assert action.get("tool") == "prepare_docs" and action.get("requires_confirmation") is False, inspected
    guarded = action["arguments_patch"]
    assert guarded["action"] == "sync_project_docs" and guarded["plan_digest"], guarded

    # A legitimate precondition race must fail closed before changing the index.
    (project / "unreviewed.txt").write_text("unreviewed fixture change\n", encoding="utf-8", newline="\n")
    rejected = payload(await session.call_tool("prepare_docs", guarded))
    assert rejected["status"] == "precondition_failed", rejected
    assert rejected["requires_confirmation"] is True, rejected
    dirty = payload(await session.call_tool("docs_status", status_args))["project"]
    assert dirty["requires_confirmation"] is True, dirty
    assert dirty["source_summary"]["indexed"] == 0, dirty
    # No unguarded prepare follows a confirmation-required response.
    _accept_fixture(project)  # fixture author explicitly accepts the new snapshot
    accepted = payload(await session.call_tool("docs_status", status_args))["project"]
    next_action = accepted["next_action"]
    assert next_action["requires_confirmation"] is False, next_action
    synced = payload(await session.call_tool("prepare_docs", next_action["arguments_patch"]))
    assert synced["status"] == "success", synced
    answer = payload(await session.call_tool("get_docs_context", original))
    validate_context_payload(answer, required_fragment=NEEDLE)
    # Exactly the original question is retried once; sufficient evidence stops
    # this task. No extra discovery/status call is made for this ready context.

    # Explicit, local-only invalid-manifest request exercises a real async job.
    manifest = root / "invalid.docs.yaml"
    manifest.write_text("schema_version: 1\ntargets: not-a-list\n", encoding="utf-8")
    started = payload(await session.call_tool("prepare_docs", {
        "action": "prefetch_docs_manifest", "manifest_path": str(manifest),
        "project_path": str(project),
    }))
    assert started["job_id"] and started["status"] == "running", started
    # Infrastructure readiness barrier, not extra host/MCP polling or a new
    # agent policy. Read only status in this fixture's own database so scheduler
    # timing cannot turn the terminal-state check into a flaky sleep-based test.
    database = Path(inspected["diagnostics"]["active_index"]["db_path"]).resolve()
    assert database.is_relative_to(root.resolve()), "fixture database escaped isolation"
    deadline = time.monotonic() + 10
    readiness_reads = 0
    while True:
        state = _read_fixture_job_state(database, started["job_id"])
        readiness_reads += 1
        if state and state[0] == "failed":
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("local invalid-manifest fixture did not reach terminal state")
        await asyncio.sleep(0.01)
    print(f"Lifecycle fixture readiness: {readiness_reads} read-only storage checks; "
          "one MCP job-status call follows (not a model or latency measurement)")
    terminal = payload(await session.call_tool("docs_status", {
        "action": "job", "job_id": started["job_id"],
    }))
    assert terminal["status"] == "failed" and terminal["retryable"] is False, terminal
    assert terminal["counts"]["pages"]["total"] == 0, terminal
    # Terminal failure stops: no retry, cancellation or further polling.
    print("Installed lifecycle smoke: clean guard / confirmation / unchanged retry / "
          "ready stop / async status / terminal stop PASS (scripted, no live model)")


async def smoke() -> None:
    # The parsers below are provider-free release contracts. Import the MCP
    # client only when the installed-artifact smoke is actually executed.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with tempfile.TemporaryDirectory(prefix="docatlas-release-smoke-") as raw:
        root = Path(raw)
        project = root / "project"
        project.mkdir()
        (project / "README.md").write_text(
            f"# Docs MCP server\n\nThe command that starts the Docs MCP server is `{NEEDLE}`.\n"
        )
        user_home = root / "user-home"
        user_home.mkdir()
        docatlas_home = root / "docatlas-home"
        docatlas_home.mkdir()
        env = {
            **os.environ,
            "HOME": str(user_home),
            "USERPROFILE": str(user_home),
            "DOCATLAS_HOME": str(docatlas_home),
            "NO_PROXY": "*",
        }
        params = StdioServerParameters(command="doc-atlas", args=["mcp", "docs-serve"], env=env, cwd=str(root))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert names == TOOLS, f"unexpected public Docs tools: {sorted(names)}"
                canonical_query = {
                    "question": QUESTION,
                    "project_path": str(project),
                }
                assert set(canonical_query) == {"question", "project_path"}
                await session.call_tool("get_docs_context", canonical_query)
                sync = payload(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(project), "with_vectors": False,
                }))
                assert sync.get("status") not in {"error", "failed"}, sync
                answer = payload(await session.call_tool("get_docs_context", canonical_query))
                validate_context_payload(answer, required_fragment=NEEDLE)
                rendered = json.dumps(answer, sort_keys=True)
                assert "README.md" in rendered, answer
                assert NEEDLE in rendered, answer
                from docmancer.docs.interfaces.grounded_mcp_session import GroundedMCPSession
                grounded = await GroundedMCPSession.start(session, arguments=canonical_query,
                    requested_facts={'command': 'How do I start the server?',
                                     'details': 'What additional operational details are documented?'})
                source = next(s for s in grounded.context['sources'] if NEEDLE in s['snippet'])
                grounded.support('command', evidence_id=source['evidence_id'], quote=NEEDLE)
                if source.get('source_uri'):
                    await grounded.read(source['source_uri'], missing_fact_id='details')
                handoff = grounded.finish()
                assert handoff['status'] == 'partial' and handoff['known'][0]['quote'] == NEEDLE
                assert handoff['answer_supported'] is False
                sources = answer.get("sources") or answer.get("selected_sources") or answer.get("context_pack") or []
                assert any(
                    source.get("path_or_url") == "README.md" or source.get("path") == "README.md"
                    for source in sources
                ), answer
                await lifecycle_smoke(session, root)
        config_path = user_home / "opencode.json"
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
                # OpenCode currently requires text fallback, but uses the same
                # canonical tool arguments and payload.
                canonical_query = {
                    "question": QUESTION,
                    "project_path": str(project),
                }
                grounded_text = await GroundedMCPSession.start(session,
                    arguments=canonical_query, structured_supported=False,
                    requested_facts={'command': 'How do I start the server?'})
                text_answer = grounded_text.context
                rendered = json.dumps(text_answer, sort_keys=True)
                assert "README.md" in rendered, text_answer
                assert NEEDLE in rendered, text_answer
                text_source = next(s for s in text_answer['sources'] if NEEDLE in s['snippet'])
                grounded_text.support('command', evidence_id=text_source['evidence_id'], quote=NEEDLE)
                assert grounded_text.finish()['status'] == 'host_assessed_complete'
        assert not (user_home / ".docmancer").exists(), (
            "installed release smoke wrote implicit foreign ~/.docmancer state"
        )
    print("Docs MCP installed-artifact stdio smoke: PASS")


if __name__ == "__main__":
    asyncio.run(smoke())
