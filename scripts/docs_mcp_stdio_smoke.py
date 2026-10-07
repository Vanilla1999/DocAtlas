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
import time

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
    from docmancer.docs.application.action_packet import (
        estimate_action_packet_tokens, refresh_action_packet_estimate, validate_action_packet,
    )

    assert answer.get("kind") == "patch_context" and answer.get("schema_version") == 4, answer
    assert answer.get("estimated_tokens") == estimate_action_packet_tokens(answer), answer
    # Only the documented projection envelope is removed. Unknown fields remain
    # visible to the strict validator. Keep returned sources/assignments intact.
    packet = {key: value for key, value in answer.items()
              if key not in {"kind", "recommended_next_action", "source_search_status"}}
    assert packet.get("sources") is answer.get("sources")
    assert packet.get("assignments") is answer.get("assignments")
    refresh_action_packet_estimate(packet)
    errors = validate_action_packet(packet)
    assert not errors, errors
    if completeness is not None:
        assert answer.get("completeness") == completeness, answer


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


async def indexed_delivery(session, project: Path, *, text_only: bool) -> list[str]:
    decode = text_payload if text_only else payload
    blockers = []
    store, mutation = initialize_fixture_members(project)
    before = fixture_database_state(store.db_path)
    before_files = fixture_database_fingerprint(store.db_path)
    rejected = await session.call_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project)})
    if not rejected.isError:
        denied = decode(rejected)
        assert denied.get("status") != "success", denied
    assert fixture_database_state(store.db_path) == before, "missing grant modified fixture DB"
    after_files = fixture_database_fingerprint(store.db_path)
    if after_files != before_files:
        blockers.append(f"missing-grant rejection changed database bytes: before={before_files}, after={after_files}")

    first = await session.call_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project), "mutation": mutation})
    if first.isError:
        blockers.append(f"public MCP rejected explicit member grant: {first.content}; indexed evidence bytes NOT OBSERVED")
        return blockers
    synced = decode(first)
    if synced.get("status") != "success":
        blockers.append(f"explicit member grant unavailable on public MCP: {synced}; indexed evidence bytes NOT OBSERVED")
        return blockers
    metrics = synced["metrics"]
    assert metrics["transaction"] == "committed" and metrics["generation_id"].startswith("gen-"), synced
    assert metrics["derived_writes"] > 0, synced
    committed = fixture_database_state(store.db_path)
    mutation["expected_generation_id"] = metrics["generation_id"]
    repeated = decode(await session.call_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project), "mutation": mutation}))
    assert repeated["status"] == "success" and repeated["metrics"]["derived_writes"] == 0, repeated
    assert fixture_database_state(store.db_path) == committed, "unchanged member repeat wrote DB rows"
    forged = {**mutation, "catalog_sha256": "0" * 64}
    rejected = await session.call_tool("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(project), "mutation": forged})
    if not rejected.isError:
        assert decode(rejected).get("status") != "success", rejected
    assert fixture_database_state(store.db_path) == committed, "stale grant modified fixture DB"

    canonical_query = {"question": QUESTION, "project_path": str(project)}
    answer = decode(await session.call_tool("get_docs_context", canonical_query))
    validate_context_payload(answer, required_fragment=NEEDLE)
    assert answer["kind"] == "docs_context" and answer["estimated_tokens"] <= 800, answer
    rendered = json.dumps(answer)
    assert NEEDLE in rendered
    assert "README.md" in rendered, answer
    outcomes = {}
    queries = {
        "complete": {**canonical_query, "question": "What command is documented as `doc-atlas mcp docs-serve`?"},
        "partial": {**canonical_query, "question": "What command is documented as `doc-atlas mcp docs-serve` and `AbsentFixtureConstraint`?"},
        "project_scope": {**canonical_query, "scope": "project"},
        "all_scope": {**canonical_query, "scope": "all"},
        "module_mismatch": {**canonical_query, "scope": "module", "module_path": "missing-module"},
        "version_mismatch": {**canonical_query, "version": "99.0.0"},
        "large": {**canonical_query, "question": "Inspect " + " ".join(f"`validate_protocol_{i}`" for i in range(12)),
                  "tokens": 20000},
    }
    for name, query in queries.items():
        response = decode(await session.call_tool("get_docs_context", {**query, "context_format": "patch_context"}))
        validate_patch_payload(response)
        for row in response.get("sources", []):
            source_path = (project / row["path"]).resolve()
            assert source_path.is_relative_to(project) and source_path.is_file(), row
            assert row["text"] in source_path.read_text(encoding="utf-8"), "returned window differs from actual fixture source"
        outcomes[name] = {"result": response["result"], "completeness": response["completeness"],
                          "source_bytes": sum(len(row["text"].encode()) for row in response.get("sources", [])),
                          "missing": response.get("missing", [])}
        if name in {"complete", "partial"} and (response["result"] != "data" or response["completeness"] != name):
            blockers.append(f"{name} real retrieval returned {outcomes[name]}")
        if name in {"project_scope", "all_scope"}:
            assert all(row["path"] in {"README.md", "protocols.md"} for row in response.get("sources", [])), response
            if response["result"] != "data":
                blockers.append(f"positive {name} returned {outcomes[name]}")
        if name in {"module_mismatch", "version_mismatch"}:
            assert response["completeness"] != "complete", response
        if name == "large" and outcomes[name]["source_bytes"] <= 32768:
            blockers.append(f">32KB necessary evidence not delivered: {outcomes[name]}; fixture protocols.md="
                            f"{(project / 'protocols.md').stat().st_size} bytes")
    print(f"Installed {'text' if text_only else 'structured'} indexed delivery observations: {json.dumps(outcomes, sort_keys=True)}")
    await invalid_manifest_lifecycle(session, project, store.db_path, decode)
    assert fixture_database_state(store.db_path) == committed, "read delivery changed member rows"
    blockers.append("positive exact-version and positive module-scope evidence fixture not established; negative bindings checked only")
    return blockers


def initialize_fixture_members(project: Path):
    """Explicit fixture-author initialization, not an MCP mutation side effect."""
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
    from docmancer.docs.project_docs_catalog import read_project_docs_catalog

    # Distinct validation programs, not repeated padding. Each implementation
    # has its own required bindings and terminal return expression.
    programs = []
    for index in range(12):
        lines = [f"def validate_protocol_{index}(record):"]
        for field in range(36):
            lines += [f'    if record["binding_{index}_{field}"] != "protocol-{index}-value-{field}":',
                      f'        raise ValueError("invalid protocol {index} binding {field}")']
        lines.append(f'    return record["binding_{index}_35"]')
        programs.append("```python\n" + "\n".join(lines) + "\n```")
    (project / "protocols.md").write_text("# Protocol validation\n\n" + "\n\n".join(programs), encoding="utf-8")
    (project / "docatlas.yaml").write_text("index:\n  db_path: .docatlas/docatlas.db\n", encoding="utf-8")
    catalog = {"schema_version": 1, "code_files": [], "documents": [
        {"path": path, "role": "overview", "scope": "project", "description": "Fixture"}
        for path in ("README.md", "protocols.md")]}
    catalog_path = project / "docatlas.project-docs.yaml"
    catalog_path.write_text(json.dumps(catalog, sort_keys=True), encoding="utf-8")
    _accept_fixture(project)
    store = SQLiteStore(project / ".docatlas" / "docatlas.db")
    with store._connect() as conn:
        assert store._active_generation_id(conn) is None
    entries = {entry.path: entry for entry in read_project_docs_catalog(project).entries}
    mutation = {"operation": "sync_project_docs", "confirm": True,
        "storage_path": str(store.db_path), "expected_generation_id": None,
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "documents": [{"path": path, "content_sha256": hashlib.sha256((project / path).read_bytes()).hexdigest(),
                       "catalog_entry_hash": catalog_entry_hash(entries[path])} for path in entries]}
    return store, mutation


def fixture_database_state(database: Path) -> dict:
    """Read-only member state; excludes lifecycle job rows deliberately."""
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
        return {table: conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in ("sources", "sections", "index_generations", "generation_sources",
                              "retrieval_children", "retrieval_children_fts")}


def fixture_database_fingerprint(database: Path) -> dict[str, str]:
    return {suffix: hashlib.sha256(path.read_bytes()).hexdigest()
            for suffix in ("", "-wal", "-shm", "-journal")
            if (path := Path(str(database) + suffix)).exists()}


async def invalid_manifest_lifecycle(session, project: Path, database: Path, decode) -> None:
    manifest = project.parent / f"{project.name}-invalid.docs.yaml"
    manifest.write_text("schema_version: 1\ntargets: not-a-list\n", encoding="utf-8")
    started = decode(await session.call_tool("prepare_docs", {
        "action": "prefetch_docs_manifest", "manifest_path": str(manifest), "project_path": str(project)}))
    assert started["status"] == "running" and started["job_id"], started
    # Fixture-only infrastructure barrier. One MCP status call follows terminal
    # failure; this is not model polling or permission inferred from status.
    deadline = time.monotonic() + 10
    while _read_fixture_job_state(database, started["job_id"]) != ("failed",):
        if time.monotonic() >= deadline:
            raise TimeoutError("local invalid manifest fixture did not reach failed state")
        await asyncio.sleep(0.01)
    terminal = decode(await session.call_tool("docs_status", {"action": "job", "job_id": started["job_id"],
                                                             "project_path": str(project)}))
    assert terminal["status"] == "failed" and terminal["retryable"] is False, terminal
    assert terminal["counts"]["pages"]["total"] == 0, terminal


async def smoke(*, read_only: bool = False) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import docmancer

    checkout = Path(__file__).resolve().parents[1]
    imported = Path(docmancer.__file__).resolve()
    assert not imported.is_relative_to(checkout), f"smoke imported checkout instead of installed wheel: {imported}"
    executable = shutil.which("doc-atlas")
    assert executable, "installed doc-atlas console script not found"
    temporary_parent = "/tmp/opencode" if sys.platform.startswith("linux") and Path("/tmp/opencode").is_dir() else None
    with tempfile.TemporaryDirectory(prefix="docatlas-release-smoke-", dir=temporary_parent) as raw:
        root = Path(raw)
        env = isolated_environment(root)
        config_path = root / "user-home" / "opencode.json"
        register_server(AgentTarget("opencode", config_path, "json_opencode_mcp"))
        registrations = json.loads(config_path.read_text())["mcp"]["servers"]
        assert set(registrations) == {"docatlas"}, registrations
        entry = registrations["docatlas"]
        assert "enabled" not in entry and not entry.get("disabled"), entry
        blockers = []
        for text_only in (False, True):
            project = root / ("project-text" if text_only else "project-structured")
            project.mkdir()
            (project / "README.md").write_text(
                f"# Docs MCP server\n\nThe command that starts the Docs MCP server is `{NEEDLE}`.\n", encoding="utf-8")
            _accept_fixture(project)
            params = StdioServerParameters(command=executable, args=entry["command"][1:],
                env={**env, **(entry["environment"] if text_only else {})}, cwd=str(root))
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    await read_only_delivery(session, project, text_only=text_only)
                    if not read_only:
                        blockers.extend(await indexed_delivery(session, project, text_only=text_only))
        assert not (root / "user-home" / ".docmancer").exists()
        if blockers:
            raise RuntimeError("BLOCKED full installed delivery matrix: " + "\n".join(blockers))
    if read_only:
        print("Installed read-only stdio delivery: PASS (structured/text, empty patch, unauthorized fields). "
              "Indexed lifecycle/partial/complete/>32KB/scope/version NOT RUN.")
    else:
        print("Docs MCP installed-artifact stdio smoke: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true")
    asyncio.run(smoke(read_only=parser.parse_args().read_only))
