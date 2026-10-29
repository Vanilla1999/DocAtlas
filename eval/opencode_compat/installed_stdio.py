"""Installed real-stdio MCP acceptance for OpenCode's self-contained text mode.

Uses actual project preparation, SQLite, source reader and fresh MCP
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
    "docs/replay-watermark.md": "# Recovery watermark\n\nBefore replaying queued events, confirm the journal watermark is at least as new as the selected snapshot.\n",
    "docs/restore-identity.md": "# Restore identity\n\nBefore restore, confirm the checkpoint identifier is authorized for this project and release.\n",
    "docs/restore-source.md": "# Restore source\n\nRecord the checkpoint content hash before restore so the restored data has an auditable origin.\n",
    "docs/replay-order.md": "# Replay order\n\nReplay queued events only after the restore completes and checkpoint validation succeeds.\n",
    "docs/ingress-gate.md": "# Ingress gate\n\nPause ingress before recovery and reopen it only after reconciliation of queued events is complete.\n",
    "docs/recovery-logging.md": "# Recovery audit\n\nRecord the incident ID, restore checkpoint and replay status in the recovery audit log.\n",
    "docs/security-rotation.md": "# Key rotation\n\nProduction API keys must be stored in the secret store; rotate them after an exposure incident.\n",
    "docs/secure-restoration.md": "# Access review\n\nRecovery operators should verify their approved project access before replaying events or reading secrets.\n",
}
QUESTION = "Before replaying queued events, which checks and restore command must run, and where do production API keys belong?"
LARGE_QUESTION = "What is Black's default line length?"


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


def setup(root: Path, documents: dict[str, str] | None = None) -> None:
    docs = root / "project"
    docs.mkdir()
    catalog = []
    for name, text in (DOCS if documents is None else documents).items():
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


async def call(env: dict, root: Path, *, prepare: dict | None,
               question: str = QUESTION, expect_delivery_error: bool = False,
               check_denial: bool = True, errlog=None):
    params = StdioServerParameters(command=sys.executable, args=["-I", "-m", "docmancer.cli", "mcp", "docs-serve"],
                                   env=env, cwd=str(root))
    options = {"errlog": errlog} if errlog is not None else {}
    async with stdio_client(params, **options) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            spec = next(x for x in (await session.list_tools()).tools if x.name == "get_docs_context")
            assert getattr(spec, "outputSchema", None) is None
            if prepare is not None:
                result, _ = text_payload(await session.call_tool("prepare_docs", {
                    "action": "sync_project_docs", "project_path": str(root / "project"), "mutation": prepare}))
                assert result["status"] == "success", result
            reply = await session.call_tool("get_docs_context", {
                "project_path": str(root / "project"), "question": question})
            result, text = text_payload(reply)
            assert bool(reply.isError) is expect_delivery_error, {
                "isError": reply.isError, "status": result.get("status"),
                "utf8_bytes": len(text.encode("utf-8")), "error": result.get("error"),
            }
            if not check_denial:
                return result, text, None
            denied = await session.call_tool("get_docs_context", {
                "project_path": str(root / "project"), "question": question,
                "scope": "module", "module_path": "missing-module"})
            err, _ = text_payload(denied)
            assert err["status"] in {"failed", "insufficient_evidence"} and not err.get("sources"), err
            return result, text, err


async def large_packet_check(out: Path) -> dict:
    """One frozen real question, not a reconstruction of the user's B01 trace.

    Compression is explicitly disabled for this supported runtime route. Three
    retrieval calls compare complete legacy delivery, guarded delivery, and
    the trace-off result. Only the isolated fixture is prepared or written.
    """
    repo = Path(__file__).resolve().parents[2]
    source = repo / "eval/prepared_model_comparison40/sources/black"
    expected = json.loads((repo / "eval/context_assembly/questions20.json").read_text())["source_sha256"]
    documents = {path.relative_to(source).as_posix(): path.read_text(encoding="utf-8")
                 for path in source.rglob("*.md")}
    assert len(documents) == 3
    for name, text in documents.items():
        assert digest(text.encode("utf-8")) == expected["black/" + name]
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="docatlas-opencode-large-") as temp:
        root = Path(temp)
        setup(root, documents)
        env = {**environment(root), "DOCATLAS_CONTEXT_COMPRESSION": "off",
               "DOCATLAS_MCP_MODEL_VIEW": "off", "DOCATLAS_TRACE": "0"}
        mutation, database = prepared_mutation(env, root / "project")
        with (out / "B01-baseline-stderr.log").open("w") as stderr:
            baseline, raw_text, _ = await call(
                {**env, "DOCATLAS_MCP_COMPACT_TEXT": "off"}, root,
                prepare=mutation, question=LARGE_QUESTION, check_denial=False, errlog=stderr)
        (out / "B01-baseline.json").write_text(raw_text + "\n", encoding="utf-8")
        assert baseline.get("kind") == "docs_context" and baseline.get("status") in {"ok", "truncated"}
        assert not baseline.get("hard_stop") and not baseline.get("requires_confirmation")
        assert not baseline.get("recommended_next_action")
        baseline_bytes = len(raw_text.encode("utf-8"))
        assert baseline_bytes > 48_000, {"baseline_bytes": baseline_bytes}
        rows = expand_sections(baseline)["sources"]
        assert rows
        assert any("How many characters per line to allow. The default is 88." in row["snippet"]
                   for row in rows), "Original B01 fact missing from the real legacy evidence"
        for row in rows:
            path = row["path_or_url"]
            assert path in documents and row["scope"] == "project"
            assert row["evidence_id"] and row["source_uri"].startswith("docatlas://source/")
            start, end = row["line_start"], row["line_end"]
            lines = documents[path].splitlines(keepends=True)
            assert type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)
            assert row["snippet"] in "".join(lines[start - 1:end])
        before = state(database)
        compact_env = {**env, "DOCATLAS_MCP_COMPACT_TEXT": "1"}
        with (out / "B01-compact-trace.log").open("w") as stderr:
            blocked, blocked_text, _ = await call(
                {**compact_env, "DOCATLAS_TRACE": "1"}, root, prepare=None,
                question=LARGE_QUESTION, expect_delivery_error=True, check_denial=False, errlog=stderr)
        (out / "B01-compact.json").write_text(blocked_text + "\n", encoding="utf-8")
        error = blocked["error"]
        assert blocked["status"] == "failed" and not blocked.get("sources")
        assert error["reason_code"] == "context_delivery_unavailable"
        assert error["where"]["phase"] == "delivery" and error["retryable"] is False
        assert error["details"]["delivery_reason"] in {
            "model_context_output_limit", "standalone_context_output_limit"}
        assert error["details"]["fallback_utf8_bytes"] > 48_000
        assert len(blocked_text.encode("utf-8")) <= 48_000
        assert projection_token_count(blocked_text.encode("utf-8")) <= 12000
        with (out / "B01-compact-trace-off.log").open("w") as stderr:
            quiet, quiet_text, _ = await call(
                compact_env, root, prepare=None, question=LARGE_QUESTION,
                expect_delivery_error=True, check_denial=False, errlog=stderr)
        assert quiet == blocked and quiet_text == blocked_text, "Tracing changed the delivered error"
        events = []
        for line in (out / "B01-compact-trace.log").read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("event") == "docatlas_mcp_text_fallback":
                events.append(event)
        assert len(events) == 1 and events[0]["outcome"] == "delivery_error"
        assert events[0]["delivery_reason"] == error["details"]["delivery_reason"]
        assert "docatlas_mcp_text_fallback" not in (out / "B01-compact-trace-off.log").read_text()
        assert state(database) == before
        assert all((root / "project" / name).read_bytes() == text.encode("utf-8")
                   for name, text in documents.items())
        result = {
            "id": "B01", "question": LARGE_QUESTION, "retrieval_calls": 3,
            "preparation_calls": 1, "compression": "off", "source_rows": len(rows),
            "legacy_utf8_bytes": baseline_bytes,
            "legacy_o200k": projection_token_count(raw_text.encode("utf-8")),
            "delivery_error_utf8_bytes": len(blocked_text.encode("utf-8")),
            "delivery_error_o200k": projection_token_count(blocked_text.encode("utf-8")),
            "delivery_reason": error["details"]["delivery_reason"],
            "source_fidelity": True, "files_and_sqlite_unchanged": True,
            "trace_does_not_change_result": True,
            "note": "Installed MCP transport refusal; no delivered evidence, no OpenCode/model answer claim",
        }
        (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


async def run(out: Path, *, large_packet: bool = False):
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
        # The dense real project case proves the server actually emits an
        # assembled representation by DEFAULT, not just that the code
        # supports an explicit adaptive setting on archived responses.
        if not os.environ.get("DOCATLAS_MINILM_MODEL_DIR"):
            assert len(view["sources"]) >= 6, len(view["sources"])
            assert raw_view["context_format"].startswith("docatlas.assembled-"), raw_view["context_format"]
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
        if large_packet:
            result["large_packet"] = await large_packet_check(out / "large-packet")
        (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--large-packet", action="store_true",
                        help="Also verify a real oversized Black B01 response is a typed delivery failure")
    args = parser.parse_args()
    asyncio.run(run(args.out, large_packet=args.large_packet))
