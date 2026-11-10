"""Installed real-stdio MCP acceptance for OpenCode's self-contained text mode.

Uses actual project preparation, SQLite, source reader and fresh or persistent
MCP sessions. No mocked retrieval, source validator or tool transport. This tests
the OpenCode-facing MCP content shape, not paid-provider billing.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml
import jsonschema
import docmancer
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from docmancer.docs.application.context_assembly import decode_context
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.application.section_compression import expand_sections
from docmancer.docs.project_docs_catalog import CATALOG_FILENAME, read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from docmancer.mcp._docs_server_schema import PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA
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


def setup(root: Path, documents: dict[str, str] | None = None, *,
          descriptions: dict[str, str] | None = None,
          languages: dict[str, list[str]] | None = None) -> None:
    docs = root / "project"
    docs.mkdir()
    catalog = []
    for name, text in (DOCS if documents is None else documents).items():
        target = docs / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
        catalog.append({"path": name, "role": "other", "scope": "project",
                        "description": (descriptions or {}).get(name, "Pinned integration source"),
                        "authority": "source_of_truth",
                        "status": "active", "impact": "track"})
    (docs / CATALOG_FILENAME).write_text(yaml.safe_dump({"schema_version": 1, "code_files": [],
                              "documentation_languages": languages or {},
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


def source_rows(payload: dict) -> list[dict]:
    """Read public evidence from either supported MCP text representation."""
    if not payload.get("context_format"):
        return expand_sections(payload).get("sources", [])
    view = decode_context(payload)
    return [{**(view.get("source_context") or {}), **row,
             "path_or_url": row["path"], "snippet": row["text"], "evidence_id": row["ref"]}
            for row in view.get("sources", [])]


def source_fidelity(payload: dict, documents: dict[str, str], *, binding_hashes: bool = False) -> list[dict]:
    rows = source_rows(payload)
    for row in rows:
        path = row["path_or_url"]
        assert path in documents, row
        assert row["scope"] == "project" and row["authority"] == "source_of_truth", row
        assert row["version_binding"] == "unversioned" and row["project_identity"].startswith("local:"), row
        assert row["evidence_id"].startswith("ev-") and row["source_uri"].startswith("docatlas://source/"), row
        start, end = row["line_start"], row["line_end"]
        lines = documents[path].splitlines(keepends=True)
        assert type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), row
        assert row["snippet"] and row["snippet"] in "".join(lines[start - 1:end]), row
        if binding_hashes:
            # Canonical content_sha256 is an opaque source-binding digest, not
            # the file checksum. The resource reader exposes the latter.
            assert re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]), row
    return rows


def required_facts(rows: list[dict], facts: dict[str, str]) -> None:
    for path, quote in facts.items():
        assert any(row["path_or_url"] == path and quote in row["snippet"] for row in rows), {
            "missing_source_fact": {"path": path, "quote": quote},
            "delivered_paths": sorted({row["path_or_url"] for row in rows}),
        }


def delivered_budget(text: str) -> dict[str, int]:
    body = text.encode("utf-8")
    measured = {"utf8_bytes": len(body), "o200k_tokens": projection_token_count(body)}
    assert measured["utf8_bytes"] <= 48_000 and measured["o200k_tokens"] <= 12_000, measured
    return measured


async def call(env: dict, root: Path, *, prepare: dict | None,
               question: str = QUESTION, expect_delivery_error: bool = False,
               search_question: str | None = None, read_sources: dict[str, str] | None = None,
               response_path: Path | None = None,
               check_denial: bool = True, errlog=None):
    params = StdioServerParameters(command=sys.executable, args=["-I", "-m", "docmancer.cli", "mcp", "docs-serve"],
                                   env=env, cwd=str(root))
    options = {"errlog": errlog} if errlog is not None else {}
    async with stdio_client(params, **options) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            return await call_in_session(
                session, env, root, prepare=prepare, question=question,
                expect_delivery_error=expect_delivery_error, search_question=search_question,
                read_sources=read_sources, response_path=response_path, check_denial=check_denial)


async def call_in_session(session: ClientSession, env: dict, root: Path, *, prepare: dict | None,
                          question: str = QUESTION, expect_delivery_error: bool = False,
                          search_question: str | None = None,
                          read_sources: dict[str, str] | None = None,
                          response_path: Path | None = None,
                          check_denial: bool = True):
    """Exercise the same public request in an existing initialized MCP session."""
    spec = next(x for x in (await session.list_tools()).tools if x.name == "get_docs_context")
    assert getattr(spec, "outputSchema", None) is None
    if prepare is not None:
        # Fresh installed MCP must explain preparation without creating
        # storage or falsely reporting an OS permission failure.
        database = Path(prepare["storage_path"])
        if not database.exists():
            target = {} if env.get("DOCATLAS_PROJECT_BINDING") else {"project_path": str(root / "project")}
            for tool, arguments in (
                ("docs_status", {"action": "project", **target}),
                ("get_docs_context", {"question": question, **target}),
            ):
                cold, _ = text_payload(await session.call_tool(tool, arguments))
                assert cold["status"] == "not_prepared", cold
                assert cold["reason_code"] == "member_store_uninitialized", cold
                assert cold["storage_path"] == str(database), cold
                assert cold["recommended_next_action"]["action"] == "sync_project_docs", cold
                assert cold["recommended_next_action"]["requires_confirmation"] is True, cold
                assert cold["project_path"] == str(root / "project"), cold
                if tool == "docs_status" and not target:
                    assert cold["project_binding"]["project_path"] == str(root / "project"), cold
                assert not database.exists()
        result, _ = text_payload(await session.call_tool("prepare_docs", {
            "action": "sync_project_docs", "project_path": str(root / "project"), "mutation": prepare}))
        assert result["status"] == "success", result
    target = {} if env.get("DOCATLAS_PROJECT_BINDING") else {"project_path": str(root / "project")}
    arguments = {**target, "question": question}
    if search_question is not None:
        arguments["search_question"] = search_question
    reply = await session.call_tool("get_docs_context", arguments)
    result, text = text_payload(reply)
    if response_path is not None:
        response_path.write_text(text + "\n", encoding="utf-8")
    assert bool(reply.isError) is expect_delivery_error, {
        "isError": reply.isError, "status": result.get("status"),
        "utf8_bytes": len(text.encode("utf-8")), "error": result.get("error"),
    }
    source_reads = {}
    for path, document in (read_sources or {}).items():
        row = min((row for row in source_rows(result) if row["path_or_url"] == path),
                  key=lambda row: row["line_end"])
        resource = await session.read_resource(row["source_uri"])
        assert len(resource.contents) == 1
        continuation = json.loads(resource.contents[0].text)
        source_reads[path] = continuation
        if response_path is not None:
            response_path.with_name(response_path.stem + "-sources.json").write_text(
                json.dumps(source_reads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert continuation["status"] in {"complete", "truncated"}, continuation
        assert continuation.get("reason_code") != "end_of_source", {
            "missing_independent_file_checksum": path, "continuation": continuation}
        assert continuation["path"] == path, continuation
        assert continuation["content_sha256"] == "sha256:" + digest(document.encode("utf-8"))
        assert continuation["project_identity"] == row["project_identity"]
        start, end = continuation["line_start"], continuation["line_end"]
        assert 1 <= start <= end <= len(document.splitlines()), continuation
        assert continuation["snippet"] == "\n".join(document.splitlines()[start - 1:end])
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
    retrieval calls require the independently pinned fact in bounded canonical
    and compact delivery, then verify tracing does not change that delivery.
    Only the isolated fixture is prepared or written.
    """
    repo = Path(__file__).resolve().parents[2]
    source = repo / "eval/prepared_model_comparison40/sources/black"
    expected = json.loads((repo / "eval/context_assembly/questions20.json").read_text())["source_sha256"]
    documents = {path.relative_to(source).as_posix(): path.read_text(encoding="utf-8")
                 for path in source.rglob("*.md")}
    assert len(documents) == 3
    for name, text in documents.items():
        assert digest(text.encode("utf-8")) == expected["black/" + name]
    quote = "How many characters per line to allow. The default is 88."
    fact = {name: quote for name, text in documents.items() if quote in text}
    assert len(fact) == 1, "Independent B01 reference must remain unique"
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="docatlas-opencode-large-") as temp:
        root = Path(temp).resolve()
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
        legacy_budget = delivered_budget(raw_text)
        rows = source_fidelity(baseline, documents, binding_hashes=True)
        assert rows
        required_facts(rows, fact)
        before = state(database)
        database_before = (digest(database.read_bytes()), database.stat().st_mtime_ns)
        compact_env = {**env, "DOCATLAS_MCP_COMPACT_TEXT": "1"}
        with (out / "B01-compact-trace.log").open("w") as stderr:
            compact, compact_text, _ = await call(
                {**compact_env, "DOCATLAS_TRACE": "1"}, root, prepare=None,
                question=LARGE_QUESTION, check_denial=False, errlog=stderr)
        (out / "B01-compact.json").write_text(compact_text + "\n", encoding="utf-8")
        compact_budget = delivered_budget(compact_text)
        compact_rows = source_fidelity(compact, documents)
        required_facts(compact_rows, fact)
        assert compact["status"] in {"ok", "truncated"}, compact
        assert not compact.get("hard_stop") and not compact.get("requires_confirmation")
        with (out / "B01-compact-trace-off.log").open("w") as stderr:
            quiet, quiet_text, _ = await call(
                compact_env, root, prepare=None, question=LARGE_QUESTION,
                check_denial=False, errlog=stderr)
        assert quiet == compact and quiet_text == compact_text, "Tracing changed the delivered evidence"
        events = []
        for line in (out / "B01-compact-trace.log").read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        assert any(event.get("event") == "docatlas_request_end" for event in events)
        assert not any(event.get("outcome") == "delivery_error" for event in events)
        assert "docatlas_request_end" not in (out / "B01-compact-trace-off.log").read_text()
        assert state(database) == before
        assert (digest(database.read_bytes()), database.stat().st_mtime_ns) == database_before
        assert all((root / "project" / name).read_bytes() == text.encode("utf-8")
                   for name, text in documents.items())
        result = {
            "id": "B01", "question": LARGE_QUESTION, "retrieval_calls": 3,
            "preparation_calls": 1, "compression": "off", "source_rows": len(rows),
            "legacy_utf8_bytes": baseline_bytes,
            "legacy_o200k": legacy_budget["o200k_tokens"],
            "compact_source_rows": len(compact_rows), "compact": compact_budget,
            "required_fact_delivered": True,
            "source_fidelity": True, "files_and_sqlite_unchanged": True,
            "trace_does_not_change_result": True,
            "note": "Real installed MCP evidence delivery; no OpenCode/model answer or corpus-completeness claim",
        }
        (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        return result


async def retained_reference_check(out: Path) -> dict:
    """Three context calls in one session, at the ordinary 128-cursor capacity.

    A first response issues the retained reference. A second response fills the
    other 127 slots. A third selects that oldest reference before a new one;
    reading the old reference then detects eviction during batch registration.
    Source facts, the pressure sequence and its bounds are frozen before MCP.
    """
    old_path, new_path = "refs/old.md", "refs/incoming.md"
    old_fact, new_fact = "cacheanchor cachemix permit amber.", "cachemix permit emerald requires an additional review before publication."
    documents = {
        old_path: "# Alpha\n\n" + old_fact + "\n\n## Receipt\n\nArchive receipt for amber permit.\n",
        **{f"refs/fill-{number:03d}.md": f"# Ledger {number:03d}\n\ncachefill record {number:03d}.\n"
           for number in range(127)},
        new_path: "# Zeta\n\n" + new_fact + "\n\n## Receipt\n\nArchive receipt for emerald permit.\n",
    }
    fill_facts = {path: f"cachefill record {number:03d}."
                  for number, path in enumerate(path for path in documents if path.startswith("refs/fill-"))}
    requests = (("retained", "cacheanchor"), ("fill", "cachefill"), ("mixed", "cachemix"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "FROZEN.json").write_text(json.dumps({
        "documents": documents, "requests": requests,
        "required_facts": {old_path: old_fact, new_path: new_fact},
        "fill_facts": fill_facts, "existing_cursor_count_before_mix": 128,
        "premise": "The already issued retained row precedes the newly issued row in the mixed response.",
        "source_sha256": {path: digest(text.encode()) for path, text in documents.items()},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with TemporaryDirectory(prefix="docatlas-retained-reference-") as temp:
        root = Path(temp).resolve()
        setup(root, documents)
        project = root / "project"
        env = {**environment(root), "DOCATLAS_CONTEXT_COMPRESSION": "off",
               "DOCATLAS_MCP_MODEL_VIEW": "off", "DOCATLAS_MCP_COMPACT_TEXT": "1", "DOCATLAS_TRACE": "0"}
        mutation, database = prepared_mutation(env, project)
        params = StdioServerParameters(command=sys.executable,
            args=["-I", "-m", "docmancer.cli", "mcp", "docs-serve"], env=env, cwd=str(root))
        responses, issued = {}, set()
        with (out / "stderr.log").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    prepared, _ = text_payload(await session.call_tool("prepare_docs", {
                        "action": "sync_project_docs", "project_path": str(project), "mutation": mutation}))
                    assert prepared["status"] == "success", prepared
                    before = state(database)
                    database_before = (digest(database.read_bytes()), database.stat().st_mtime_ns)
                    files_before = {path: (project / path).read_bytes() for path in [*documents, CATALOG_FILENAME]}
                    for label, question in requests:
                        payload, text, _ = await call_in_session(
                            session, env, root, prepare=None, question=question,
                            response_path=out / (label + ".json"), check_denial=False)
                        jsonschema.validate(payload, PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA)
                        rows = source_fidelity(payload, documents)
                        measured = delivered_budget(text)
                        uris = {row["source_uri"] for row in rows}
                        responses[label] = {**measured, "source_rows": len(rows), "source_uris": sorted(uris)}
                        if label == "retained":
                            required_facts(rows, {old_path: old_fact})
                            assert len(uris) == 1, "The pressure fixture must issue exactly one old reference"
                            old_uri = next(iter(uris))
                            issued.update(uris)
                        elif label == "fill":
                            required_facts(rows, fill_facts)
                            assert len(uris) == 127 and not (uris & issued), "The fill must occupy 127 other slots"
                            issued.update(uris)
                            assert len(issued) == 128
                        else:
                            required_facts(rows, {old_path: old_fact, new_path: new_fact})
                            old_index = next(index for index, row in enumerate(rows) if row["source_uri"] == old_uri)
                            fresh_indices = [index for index, row in enumerate(rows) if row["source_uri"] not in issued]
                            assert fresh_indices and old_index < min(fresh_indices), {
                                "unexercised_old_before_new_pressure": [row["path_or_url"] for row in rows]}
                            assert len(issued | uris) > 128 and len(uris) <= 128
                            (out / "pressure.json").write_text(json.dumps({
                                "previously_issued": len(issued), "mixed_selected": len(uris),
                                "new_selected": len(uris - issued), "old_uri": old_uri,
                                "old_row_index": old_index, "fresh_row_indices": fresh_indices,
                            }, indent=2) + "\n", encoding="utf-8")
                            resource = await session.read_resource(old_uri)
                            assert len(resource.contents) == 1
                            continuation = json.loads(resource.contents[0].text)
                            (out / "retained-source.json").write_text(
                                json.dumps(continuation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                            assert continuation["status"] in {"complete", "truncated"}, continuation
                            assert continuation.get("reason_code") != "end_of_source", continuation
                            assert continuation["path"] == old_path
                            assert continuation["content_sha256"] == "sha256:" + digest(documents[old_path].encode())
                            assert continuation["project_identity"] == rows[old_index]["project_identity"]
                            start, end = continuation["line_start"], continuation["line_end"]
                            assert 1 <= start <= end <= len(documents[old_path].splitlines())
                            assert continuation["snippet"] == "\n".join(documents[old_path].splitlines()[start - 1:end])
                    assert state(database) == before
                    assert (digest(database.read_bytes()), database.stat().st_mtime_ns) == database_before
                    assert all((project / path).read_bytes() == data for path, data in files_before.items())
        result = {"status": "PASS", "preparation_calls": 1, "retrieval_calls": 3,
                  "source_resource_reads": 1, "previously_issued_references": 128,
                  "retained_reference_readable": True, "source_fidelity": True,
                  "files_and_sqlite_unchanged": True, "responses": responses}
        (out / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result


async def bilingual_selection(out: Path, *, large_packet: bool = False) -> None:
    """One authored source oracle and eight existing-index reads, plus cursor pressure.

    The first-language source material exceeds the delivery budget before the
    useful last English document is merged. Metadata cannot count as evidence.
    This is a synthetic regression scenario, not a blind relevance benchmark.
    """
    repo = Path(__file__).resolve().parents[2]
    installed = Path(docmancer.__file__).resolve()
    assert not installed.is_relative_to(repo), "Run with the installed wheel, outside the checkout"
    question_ru = (
        "Какой порядок восстановления обязателен перед повторным проигрыванием событий "
        "в проекте и где должны храниться производственные ключи?"
    )
    question_en = (
        "What recovery order is required before replaying queued events in the project, "
        "and where must production API keys be stored?"
    )
    negative_ru = (
        "Какой договорный SLA гарантирует задержку поиска p99 в этом проекте "
        "и какой денежный штраф предусмотрен за нарушение?"
    )
    negative_en = (
        "What contractual SLA guarantees p99 retrieval latency for this project, "
        "and what monetary penalty applies if that SLA is missed?"
    )
    identifier_question = "restore_checkpoint"
    identifier_fact = "`restore_checkpoint` requires a signed manifest."
    locator_question = "docs/deploy-policy.md"
    locator_fact = "Every rollout requires two reviewers."
    unknown_locator = "docs/missing-policy.md"
    ambiguous_locator = "review-note.md"
    russian_path, english_path = "docs/a-recovery.md", "docs/z-custody.md"
    facts = {
        russian_path: "Запускайте повторное проигрывание только после успешного восстановления.",
        english_path: "Production API keys must be stored in the secret store, never in the repository.",
    }
    documents = {russian_path: (
        "# Порядок восстановления\n\n"
        "Перед повторным проигрыванием событий сначала остановите приём, затем проверьте отметку журнала.\n"
        + facts[russian_path] + "\n\n## Приложение\n\nДата редакции: март.\n"
    )}
    # These are real weak body matches, not metadata decoys. They make the RU
    # lane large enough that retaining a prefix can lose the later EN fact.
    filler = (
        "Повторным проигрыванием здесь названа выставочная экспозиция. "
        "В ботаническом журнале отмечены влажность почвы, форма листа, цвет лепестков, "
        "количество семян и длина стебля. Садовник заносит наблюдения в тетрадь, "
        "сушит образцы на бумаге и размещает гербарий на деревянной полке. "
    )
    weak_paths = []
    for number in range(6):
        path = f"docs/m-herbarium-{number}.md"
        weak_paths.append(path)
        documents[path] = f"# Гербарий {number}\n\n" + "\n".join(
            f"## Повторным проигрыванием — карточка {number}-{section}\n\n"
            + " ".join(f"Образец {number}-{section}-{part}. {filler}" for part in range(3)) + "\n"
            for section in range(16)
        )
    decoys = set()
    for number in range(8):
        path = f"docs/project-recovery-order-production-api-keys-sla-p99-{number}.md"
        decoys.add(path)
        documents[path] = (
            f"# Botanical register {number}\n\n" + "\n".join(
                f"## Specimen {number}-{section}\n\n"
                "Fern specimens bear green fronds; brown spores.\n"
                "Checkpoint labels fade. Restore labels fade.\n"
                for section in range(40)
            )
        )
    # Insertion and pathname both put this useful second-language source last.
    documents[english_path] = (
        "# Vault custody\n\n" + facts[english_path] + "\n\n## Appendix\n\nRevision date: March.\n"
        "\n## Signed recovery\n\n" + identifier_fact + "\n"
    )
    documents[locator_question] = "# Release controls\n\n" + locator_fact + "\n"
    documents["docs/one/review-note.md"] = "# Copper archive\n\nKeep amber specimens sealed.\n"
    documents["docs/two/review-note.md"] = "# Silver archive\n\nKeep indigo specimens dry.\n"
    # More than 256 independently indexed metadata-only windows must precede
    # the real identifier fact under unfiltered FTS ranking. The source-field
    # check must happen before acquisition's cap, not after its old top-N.
    descriptions = {path: " ".join((question_ru, question_en, negative_en, *([identifier_question] * 6)))
                    for path in decoys}
    descriptions[locator_question] = "Approval requirements."
    assert all(len(value) <= 512 for value in descriptions.values())
    languages = {path: ["ru" if path == russian_path or path in weak_paths else "en"] for path in documents}
    weak_bytes = sum(len(documents[path].encode("utf-8")) for path in weak_paths)
    assert weak_bytes > 48_000
    question_words = set(re.findall(r"\w+", " ".join((
        question_ru, question_en, negative_ru, negative_en, identifier_question)).casefold()))
    for path in decoys:
        body_words = set(re.findall(r"\w+", documents[path].casefold()))
        overlap = question_words.intersection(body_words)
        assert not overlap, {"metadata_only_fixture_has_body_match": path, "terms": sorted(overlap)}
        # A whole technical identifier appears in routing metadata only; its
        # separated words in prose must not become evidence for that identifier.
        assert {"restore", "checkpoint"}.issubset(body_words)
        assert identifier_question in descriptions[path]
    for path, quote in facts.items():
        assert quote in documents[path]
    assert identifier_fact in documents[english_path]
    assert not set(re.findall(r"\w+", locator_question)).intersection(
        re.findall(r"\w+", documents[locator_question] + descriptions[locator_question]))
    out.mkdir(parents=True, exist_ok=True)
    # Persist the independently authored corpus and criteria before any MCP
    # preparation/retrieval. No returned text is used to construct this oracle.
    (out / "FROZEN.json").write_text(json.dumps({
        "question": question_ru, "search_question": question_en,
        "negative_question": negative_ru, "negative_search_question": negative_en,
        "identifier_question": identifier_question,
        "identifier_required_facts": {english_path: identifier_fact},
        "locator_question": locator_question, "locator_required_facts": {locator_question: locator_fact},
        "unknown_locator": unknown_locator, "ambiguous_locator": ambiguous_locator,
        "metadata_only_window_floor": 257,
        "required_facts": facts, "metadata_only_paths": sorted(decoys),
        "catalog_descriptions": descriptions, "documentation_languages": languages,
        "source_sha256": {path: digest(text.encode("utf-8")) for path, text in documents.items()},
        "documents": documents, "weak_body_utf8_bytes": weak_bytes,
        "boundary": "Self-authored integration oracle, not a blind or semantic-completeness benchmark",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with TemporaryDirectory(prefix="docatlas-project-recovery-order-production-api-keys-sla-p99-") as temp:
        root = Path(temp).resolve()
        setup(root, documents, descriptions=descriptions, languages=languages)
        project = root / "project"
        env = {**environment(root), "DOCATLAS_CONTEXT_COMPRESSION": "off",
               "DOCATLAS_MCP_MODEL_VIEW": "off", "DOCATLAS_MCP_COMPACT_TEXT": "off", "DOCATLAS_TRACE": "0"}
        mutation, database = prepared_mutation(env, project)
        params = StdioServerParameters(command=sys.executable,
            args=["-I", "-m", "docmancer.cli", "mcp", "docs-serve"], env=env, cwd=str(root))
        with (out / "prepare-stderr.log").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    prepared, _ = text_payload(await session.call_tool("prepare_docs", {
                        "action": "sync_project_docs", "project_path": str(project), "mutation": mutation}))
                    assert prepared["status"] == "success", prepared
        before = state(database)
        database_before = (digest(database.read_bytes()), database.stat().st_mtime_ns)
        files_before = {path: file.read_bytes() for path in [*documents, CATALOG_FILENAME]
                        if (file := project / path).is_file()}
        # This read-only observation establishes the adversarial fixture's
        # premise independently of the new source-scoring UDF and selector.
        # Passing still requires the exact source fact in the public MCP reply.
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
            unfiltered = db.execute("""
                SELECT child.source, child.display_text, bm25(retrieval_children_fts) AS score
                FROM retrieval_children_fts
                JOIN retrieval_children AS child ON child.id = retrieval_children_fts.rowid
                WHERE retrieval_children_fts MATCH '"restore_checkpoint"'
                ORDER BY score, child.source, child.chunk_index, child.stable_chunk_id
            """).fetchall()
        decoy_sources = {str(project / path) for path in decoys}
        metadata_windows = sum(source in decoy_sources for source, _, _ in unfiltered)
        assert metadata_windows > 256, {"insufficient_metadata_pressure": metadata_windows}
        assert any(identifier_fact in body for _, body, _ in unfiltered)
        assert all(source in decoy_sources for source, _, _ in unfiltered[:256]), {
            "fixture_did_not_exercise_filter_before_limit": [source for source, _, _ in unfiltered[:256]
                                                            if source not in decoy_sources]}
        (out / "acquisition-pressure.json").write_text(json.dumps({
            "metadata_only_matching_windows": metadata_windows,
            "unfiltered_fts_first_256_metadata_only": True,
            "required_identifier_fact_present_in_index": True,
        }, indent=2) + "\n", encoding="utf-8")
        responses = {}
        for label, question, search_question, compact, required in (
            ("ru", question_ru, None, False, {russian_path: facts[russian_path]}),
            ("en", question_en, None, False, {english_path: facts[english_path]}),
            ("merged", question_ru, question_en, True, facts),
            ("unsupported", negative_ru, negative_en, True, {}),
            ("identifier", identifier_question, None, True, {english_path: identifier_fact}),
            ("locator", locator_question, None, False, {locator_question: locator_fact}),
            ("unknown-locator", unknown_locator, None, False, {}),
            ("ambiguous-locator", ambiguous_locator, None, False, {}),
        ):
            with (out / f"{label}-stderr.log").open("w") as stderr:
                payload, text, _ = await call(
                    {**env, "DOCATLAS_MCP_COMPACT_TEXT": "1" if compact else "off"},
                    root, prepare=None, question=question, search_question=search_question,
                    read_sources={path: documents[path] for path in facts} if label == "merged" else None,
                    response_path=out / f"{label}.json",
                    check_denial=False, errlog=stderr)
            measured = delivered_budget(text)
            jsonschema.validate(payload, PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA)
            rows = source_fidelity(payload, documents, binding_hashes=not compact)
            paths = {row["path_or_url"] for row in rows}
            assert not paths.intersection(decoys), {"metadata_only_evidence": sorted(paths.intersection(decoys))}
            required_facts(rows, required)
            assert payload.get("answer_supported") is not True
            assert payload.get("context_quality", {}).get("status") in {"unverified", "unavailable"}, payload
            if required:
                assert payload["status"] in {"ok", "truncated"}, payload
                assert not payload.get("hard_stop") and not payload.get("requires_confirmation")
            if label == "merged":
                selection = payload.get("source_selection") or {}
                assert selection.get("candidate_rows", 0) > selection.get("selected_rows", 0), selection
            if label == "locator":
                assert paths == {locator_question}, paths
                assert not payload.get("covered_query_ids"), "A file locator must not acquire body-match credit"
            if label in {"unknown-locator", "ambiguous-locator"}:
                assert not rows and payload["status"] in {"failed", "insufficient_evidence"}, payload
            if label == "unsupported":
                # No claim that a lexical search proves absence in a corpus.
                # A metadata match must not deliver the entire authored corpus.
                assert len(paths) < len(documents)
                assert sum(len(row["snippet"].encode("utf-8")) for row in rows) < weak_bytes // 8
            assert state(database) == before, f"{label} changed existing stored state"
            assert (digest(database.read_bytes()), database.stat().st_mtime_ns) == database_before
            assert all((project / path).read_bytes() == content for path, content in files_before.items())
            responses[label] = {**measured, "source_rows": len(rows), "source_paths": sorted(paths),
                                "required_facts": len(required), "status": payload["status"],
                                "source_selection": payload.get("source_selection"),
                                "context_quality": payload.get("context_quality")}
        retained = await retained_reference_check(out / "retained-reference")
        result = {"status": "PASS", "installed_stdio": True, "installed_package": str(installed),
                  "preparation_calls": 2, "retrieval_calls": 11, "source_resource_reads": 3,
                  "file_snapshot_hashes_verified": 3, "strict_public_schema": True,
                  "metadata_only_matching_windows": metadata_windows,
                  "retained_reference": retained,
                  "responses": responses, "source_fidelity": True, "metadata_only_evidence": False,
                  "existing_store_unchanged": True, "files_and_sqlite_unchanged": True,
                  "boundary": "Real offline installed MCP; no model answers, semantic absence or real-client claim"}
        if large_packet:
            result["large_packet"] = await large_packet_check(out / "large-packet")
        (out / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))


async def run(out: Path, *, large_packet: bool = False):
    with TemporaryDirectory(prefix="docatlas-opencode-stdio-") as temp:
        root = Path(temp).resolve()
        setup(root)
        env = environment(root)
        mutation, database = prepared_mutation(env, root / "project")
        original_bytes = {name: (root / "project" / name).read_bytes() for name in DOCS}

        # Exercise an existing registration as well as a new one: installer
        # upgrades the owned environment without overwriting unrelated config.
        # An empty local model directory deliberately cannot run MiniLM. Its
        # presence must not opt the registered OpenCode profile into inference.
        model_directory = root / "unused-model-assets"
        model_directory.mkdir()
        cfg = root / "opencode.json"
        cfg.write_text(json.dumps({"mcp": {"docatlas": {"type": "local",
            "command": ["doc-atlas", "mcp", "docs-serve"],
            "environment": {"DOCATLAS_MCP_TEXT_FALLBACK": "1", "USER_SETTING": "retain",
                            "DOCATLAS_MINILM_MODEL_DIR": str(model_directory)},
            "disabled": True}}}), encoding="utf-8")
        target = AgentTarget("opencode", cfg, "json_opencode_mcp")
        with patch.dict(os.environ, {**env, "DOCATLAS_MINILM_MODEL_DIR": str(model_directory)}, clear=True):
            assert register_server(target)[0]
            assert not register_server(target)[0], "registration must be idempotent"
        config = json.loads(cfg.read_text(encoding="utf-8"))
        entry = config["mcp"]["servers"]["docatlas"]
        assert entry["disabled"] is True
        assert entry["environment"]["USER_SETTING"] == "retain"
        assert entry["environment"]["DOCATLAS_MCP_COMPACT_TEXT"] == "1"
        assert entry["environment"]["DOCATLAS_CONTEXT_COMPRESSION"] == "off"
        assert entry["environment"]["DOCATLAS_MINILM_MODEL_DIR"] == str(model_directory)
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

        baseline_env = {**env, "DOCATLAS_MCP_COMPACT_TEXT": "off",
                        "DOCATLAS_CONTEXT_COMPRESSION": "off"}
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
        # Selection may legitimately reduce density and choose literal layout.
        # The outcome is source evidence, not a minimum row count or layout.
        for fact in ("tern restore --checkpoint current", "secret store", "watermark"):
            assert any(fact in row["text"] for row in view["sources"]), fact
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
        assert not list(model_directory.iterdir()), "registration/read must not download model assets"
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
                  "default_registry_compression": "off", "model_path_does_not_enable_selection": True,
                  "base_scenario_calls": {"prepare_docs": 1, "get_docs_context": 9,
                                          "docs_status": 1, "source_resource_reads": 0,
                                          "initialize": 4, "tools_list": 4},
                  "note": "real installed stdio, not a paid OpenCode conversation"}
        if large_packet:
            result["large_packet"] = await large_packet_check(out / "large-packet")
        (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


async def first_use(out: Path):
    """Installed project CLI -> question-only cold reads -> approved preparation -> evidence."""
    from docmancer.docs.application.context_assembly import decode_context
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="docatlas-first-use-") as temp:
        root = Path(temp).resolve()
        setup(root)
        project_config = root / "project" / "docatlas.yaml"
        project_config_text = "index:\n  provider: sqlite\n  db_path: .docatlas/docatlas.db\n  extracted_dir: .docatlas/extracted\n"
        project_config.write_text(project_config_text)
        env = environment(root)
        install = subprocess.run(
            [sys.executable, "-I", "-m", "docmancer.cli", "install", "opencode", "--project"],
            cwd=root / "project", env=env, capture_output=True, text=True,
        )
        (out / "install.log").write_text(install.stdout + install.stderr)
        assert install.returncode == 0, install.stderr
        config = json.loads((root / "project" / "opencode.json").read_text())
        env.update(config["mcp"]["servers"]["docatlas"]["environment"])
        mutation, database = prepared_mutation(env, root / "project")
        assert not database.exists()
        result, text, _ = await call(env, root, prepare=mutation, check_denial=False)
        view = decode_context(result)
        rows = view["sources"]
        assert rows, result
        combined = "\n".join(row["text"] for row in rows)
        for fact in ("tern restore --checkpoint current", "secret store", "watermark"):
            assert fact in combined, (fact, result)
        for row in rows:
            assert row["path"] in DOCS, row
            assert row["text"] in DOCS[row["path"]], row
        assert database.is_file()
        assert not (root / "project" / ".docatlas" / "docatlas.db").exists()
        assert not (root / "project" / ".docatlas" / "extracted").exists()
        assert project_config.read_text() == project_config_text
        assert all((root / "project" / name).read_text() == text for name, text in DOCS.items())
        (out / "response.json").write_text(text)
        (out / "RESULT.json").write_text(json.dumps({
            "status": "PASS", "cold_reads": 2, "preparation_calls": 1,
            "prepared_question_calls": 1, "source_fidelity": True,
            "boundary": "installed stdio MCP, not autonomous model",
        }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--large-packet", action="store_true",
                        help="Also require the frozen Black B01 fact in bounded delivery with tracing on/off")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--first-use", action="store_true")
    mode.add_argument("--bilingual-selection", action="store_true",
                      help="Run the installed metadata/body and bilingual final-evidence regression scenario")
    args = parser.parse_args()
    if args.first_use:
        asyncio.run(first_use(args.out))
    elif args.bilingual_selection:
        asyncio.run(bilingual_selection(args.out, large_packet=args.large_packet))
    else:
        asyncio.run(run(args.out, large_packet=args.large_packet))
