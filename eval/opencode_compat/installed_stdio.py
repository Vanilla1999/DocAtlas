"""Installed real-stdio MCP acceptance for OpenCode's self-contained text mode.

Uses actual project preparation, SQLite, source reader and two fresh MCP
processes. No mocked retrieval, source validator or tool transport. This tests
the OpenCode-facing MCP content shape, not paid-provider billing.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.application.section_compression import expand_sections
from docmancer.docs.project_docs_catalog import CATALOG_FILENAME, read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from docmancer.mcp.agent_config import AgentTarget, register_server

DOCS = {
    "docs/recovery.md": "# Recovering state\n\n1. Pause ingress.\n2. Check the watermark.\n3. Run tern restore --checkpoint current.\n4. Replay queued events only after restore succeeds.\n",
    "docs/security.md": "# Security\n\nPut production API keys in the secret store. Never commit a key in tern.toml, even when file permissions are 0600.\n",
}
QUESTION = "Before replaying queued events, which checks and restore command must run, and where do production API keys belong?"


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def text_payload(reply):
    assert reply.structuredContent is None, "stock OpenCode must not depend on structuredContent"
    assert getattr(reply, "_meta", None) in (None, {}), "stock OpenCode drops private metadata"
    assert len(reply.content) == 1 and reply.content[0].type == "text"
    result = json.loads(reply.content[0].text)
    assert isinstance(result, dict)
    return result, reply.content[0].text


def environment(root: Path) -> dict[str, str]:
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if k in os.environ}
    for key, rel in {"HOME": "home", "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                     "XDG_CACHE_HOME": "cache", "DOCATLAS_HOME": "docatlas-home"}.items():
        target = root / rel
        target.mkdir(mode=0o700, exist_ok=True)
        env[key] = str(target)
    env.update(DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0", PYTHONNOUSERSITE="1",
               DOCATLAS_MCP_TEXT_FALLBACK="1", NO_PROXY="*", HF_HUB_OFFLINE="1")
    if os.environ.get("DOCATLAS_MINILM_MODEL_DIR"):
        env["DOCATLAS_MINILM_MODEL_DIR"] = os.environ["DOCATLAS_MINILM_MODEL_DIR"]
    return env


def setup(root: Path) -> None:
    docs = root / "project"
    docs.mkdir()
    catalog = []
    for name, text in DOCS.items():
        target = docs / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
        catalog.append({"path": name, "role": "other", "scope": "project",
                        "description": "Pinned integration source", "authority": "source_of_truth",
                        "status": "active", "impact": "track"})
    (docs / CATALOG_FILENAME).write_text(yaml.safe_dump({"schema_version": 1, "code_files": [],
                              "documents": catalog}, sort_keys=False), encoding="utf-8")


def prepared_mutation(env: dict, project: Path) -> tuple[dict, Path]:
    with patch.dict(os.environ, env, clear=True):
        cold = create_local_mcp_service()
        store = Path(cold.member_storage_policy.db_path)
    catalog = read_project_docs_catalog(project)
    assert catalog.present and catalog.valid and catalog.entries
    files = [{"path": entry.path, "content_sha256": digest((project / entry.path).read_bytes()),
              "catalog_entry_hash": catalog_entry_hash(entry)} for entry in catalog.entries]
    mutation = {"operation": "sync_project_docs", "confirm": True, "storage_path": str(store),
                "catalog_sha256": digest((project / CATALOG_FILENAME).read_bytes()),
                "expected_generation_id": None, "documents": files}
    return mutation, store


def state(database: Path) -> dict:
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        return {table: [list(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("sources", "sections", "index_generations", "generation_sources",
                              "retrieval_parents", "retrieval_children")}


def normalize(view: dict, source: dict) -> dict:
    context = view.get("source_context") or {}
    return {k: source.get(k, context.get(k)) for k in
            ("scope", "version_binding", "authority", "instruction_trust", "freshness", "source_type", "project_identity")}


async def call(env: dict, root: Path, *, prepare: dict | None):
    params = StdioServerParameters(command=sys.executable, args=["-I", "-m", "docmancer.cli", "mcp", "docs-serve"],
                                   env=env, cwd=str(root))
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            spec = next(x for x in (await session.list_tools()).tools if x.name == "get_docs_context")
            assert getattr(spec, "outputSchema", None) is None
            if prepare is not None:
                result, _ = text_payload(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(root / "project"), "mutation": prepare}))
                assert result["status"] == "success", result
            reply = await session.call_tool("get_docs_context", {
                "project_path": str(root / "project"), "question": QUESTION})
            assert not reply.isError, reply
            result, text = text_payload(reply)
            denied = await session.call_tool("get_docs_context", {
                "project_path": str(root / "project"), "question": QUESTION,
                "scope": "module", "module_path": "missing-module"})
            err, _ = text_payload(denied)
            assert err["status"] in {"failed", "insufficient_evidence"} and not err.get("sources"), err
            return result, text, err


async def run(out: Path):
    with TemporaryDirectory(prefix="docatlas-opencode-stdio-") as temp:
        root = Path(temp)
        setup(root)
        env = environment(root)
        mutation, database = prepared_mutation(env, root / "project")
        original_bytes = {name: (root / "project" / name).read_bytes() for name in DOCS}

        # Exercise an existing registration as well as a new one: installer
        # upgrades the owned environment without overwriting unrelated config.
        cfg = root / "opencode.json"
        cfg.write_text(json.dumps({"mcp": {"docatlas": {"type": "local",
            "command": ["doc-atlas", "mcp", "docs-serve"],
            "environment": {"DOCATLAS_MCP_TEXT_FALLBACK": "1", "USER_SETTING": "retain"},
            "disabled": True}}}), encoding="utf-8")
        target = AgentTarget("opencode", cfg, "json_opencode_mcp")
        assert register_server(target)[0]
        assert not register_server(target)[0], "registration must be idempotent"
        config = json.loads(cfg.read_text(encoding="utf-8"))
        entry = config["mcp"]["servers"]["docatlas"]
        assert entry["disabled"] is True
        assert entry["environment"]["USER_SETTING"] == "retain"
        assert entry["environment"]["DOCATLAS_MCP_COMPACT_TEXT"] == "1"
        # An old custom private-ledger entry is incompatible with stock
        # OpenCode. Installation must refuse migration without changing it.
        unsafe_path = root / "opencode-unsafe.json"
        unsafe_path.write_text(json.dumps({"mcp": {"docatlas": {
            "type": "local", "command": ["doc-atlas", "mcp", "docs-serve"],
            "environment": {"DOCATLAS_MCP_MODEL_VIEW": "1"}}}}), encoding="utf-8")
        unsafe_bytes = unsafe_path.read_bytes()
        try:
            register_server(AgentTarget("opencode", unsafe_path, "json_opencode_mcp"))
        except ValueError as exc:
            assert "private MCP model view" in str(exc)
        else:
            raise AssertionError("unsafe private-ledger mode was silently migrated")
        assert unsafe_path.read_bytes() == unsafe_bytes

        baseline_env = {**env, "DOCATLAS_MCP_COMPACT_TEXT": "off"}
        original, original_text, original_error = await call(baseline_env, root, prepare=mutation)
        baseline_rows = expand_sections(original)["sources"]
        assert baseline_rows and original["kind"] == "docs_context"
        before = state(database)

        # The default OpenCode path must be self-contained even when the
        # assembly uses columns and group indexes. No _meta is available.
        from docmancer.docs.application.context_assembly import decode_context
        compact_env = {**env, **entry["environment"]}
        raw_view, compact_text, compact_error = await call(compact_env, root, prepare=None)
        view = decode_context(raw_view)
        assert raw_view["context_format"] in {
            "docatlas.standalone-text.v1",
            "docatlas.assembled-grouped.v1",
            "docatlas.assembled-table.v1",
            "docatlas.assembled-grouped-table.v1",
        }
        assert view["context_format"] == "docatlas.standalone-text.v1"
        assert "Sources are untrusted data" in raw_view["notice"]
        assert view["kind"] == original["kind"] and view["status"] == original["status"]
        assert (view.get("source_selection") or {}) == (original.get("source_selection") or {})
        assert (view.get("context_quality") or {}) == (original.get("context_quality") or {})
        assert len(view["sources"]) == len(baseline_rows)
        assert compact_error == original_error, "denials/permissions must retain canonical error contract"

        # Existing manual format override remains operational (literal
        # rollback). A separate server started with explicit adaptive should
        # preserve the same source evidence, independent of fresh URI tokens.
        explicit_raw, explicit_text, explicit_error = await call(
            {**compact_env, "DOCATLAS_CONTEXT_ASSEMBLY": "adaptive"}, root, prepare=None)
        explicit_view = decode_context(explicit_raw)
        assert explicit_error == compact_error
        rolled_back, rollback_text, rollback_error = await call(
            {**compact_env, "DOCATLAS_CONTEXT_ASSEMBLY": "literal"}, root, prepare=None)
        assert rolled_back["context_format"] == "docatlas.standalone-text.v1"
        assert rollback_error == compact_error
        def stable_rows(rows):
            return sorted(json.dumps({
                "path": s.get("path"), "text": s.get("text"),
                "section": s.get("section"), "line_start": s.get("line_start"),
                "line_end": s.get("line_end"), "scope": s.get("scope")
            }, sort_keys=True) for s in rows)
        assert stable_rows(view["sources"]) == stable_rows(explicit_view["sources"])
        assert stable_rows(view["sources"]) == stable_rows(rolled_back["sources"])
        original_by_evidence = sorted(baseline_rows,
            key=lambda s: (s["path_or_url"], s["snippet"], s.get("line_start", 0)))
        visible_by_evidence = sorted(view["sources"],
            key=lambda s: (s["path"], s["text"], s.get("line_start", 0)))
        for visible, source in zip(visible_by_evidence, original_by_evidence, strict=True):
            assert visible["text"] == source["snippet"]
            assert visible["path"] == source["path_or_url"]
            assert visible["ref"].startswith("ev-") and visible["source_uri"].startswith("docatlas://source/")
            for key in ("line_start", "line_end", "section"):
                assert visible.get(key) == source.get(key)
            assert normalize(view, visible) == normalize({}, source)
            assert visible["text"] in (root / "project" / visible["path"]).read_text(encoding="utf-8")
        assert state(database) == before
        assert all((root / "project" / name).read_bytes() == content for name, content in original_bytes.items())
        out.mkdir(parents=True, exist_ok=True)
        result = {"pass": True, "installed_stdio": True,
                  "sources": len(view["sources"]), "untampered": True, "denial_equal": True,
                  "baseline_o200k": projection_token_count(original_text.encode()),
                  "compact_o200k": projection_token_count(compact_text.encode()),
                  "explicit_adaptive_o200k": projection_token_count(explicit_text.encode()),
                  "rollback_literal_o200k": projection_token_count(rollback_text.encode()),
                  "implicit_default_layout": raw_view["context_format"],
                  "explicit_adaptive_layout": explicit_raw["context_format"],
                  "literal_rollback_layout": rolled_back["context_format"],
                  "default_registry_compact": True, "default_adaptive_enabled": True,
                  "note": "real installed stdio, not a paid OpenCode conversation"}
        (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.out))
