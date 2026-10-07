#!/usr/bin/env python3
"""Real installed-artifact stdio delivery smoke; no mocked retrieval or providers.

--read-only checks the runnable unindexed delivery surface. It never claims
the indexed/large-packet matrix passed. Full smoke verifies the current blocked
preparation boundary and exits nonzero until separately approved safe storage
work makes positive indexed delivery available.

--ready-index additionally bootstraps accepted temporary project/module and
local versioned library fixtures outside MCP, for real public retrieval only.
It never certifies preparation or legacy compatibility, and retains open gates.
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
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import url2pathname

from docmancer.mcp.agent_config import AgentTarget, register_server

TOOLS = {"get_docs_context", "prepare_docs", "docs_status"}
QUESTION = "Which command starts the Docs MCP server?"
NEEDLE = "doc-atlas mcp docs-serve"


def payload(result: object, *, allow_error: bool = False) -> dict:
    assert allow_error or not getattr(result, "isError", False), result
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", [])
    assert len(content) == 1 and isinstance(getattr(content[0], "text", None), str), result
    value = json.loads(content[0].text)
    assert isinstance(value, dict), value
    return value


def text_payload(result: object, *, allow_error: bool = False) -> dict:
    if getattr(result, "structuredContent", None) is not None:
        raise AssertionError("text-only compatibility response included structuredContent")
    return payload(result, allow_error=allow_error)


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
    negative_bindings = {}
    for name, extra in (("module_mismatch", {"scope": "module", "module_path": "missing-module"}),
                        ("version_mismatch", {"version": "99.0.0"})):
        response = decode(await session.call_tool("get_docs_context", {
            **canonical_query, **extra, "context_format": "patch_context"}))
        validate_patch_payload(response, completeness="unavailable")
        assert response["result"] == "failure" and not response.get("sources"), response
        negative_bindings[name] = {"result": response["result"], "completeness": response["completeness"],
                                   "sources": [], "source_bytes": 0}
    for extra in ({"mutation_intent": {"operation": "delete", "confirm": True}},
                  {"edit_ready": True}, {"allow_network": True, "consent": True}):
        rejected = await session.call_tool("get_docs_context", {**canonical_query, **extra})
        if not rejected.isError:
            response = decode(rejected)
            assert response.get("status") in {"error", "failed"}, response
    assert (project / "README.md").read_text().endswith(f"`{NEEDLE}`.\n")
    print(f"Installed {'text' if text_only else 'structured'} unindexed read-only observations: " + json.dumps({
        "docs_default": {"status": docs.get("status"), "kind": docs.get("kind"),
                         "sources": docs.get("sources", []),
                         "source_bytes": sum(len(row.get("snippet", "").encode()) for row in docs.get("sources", []))},
        "empty_patch": {"result": patch["result"], "completeness": patch["completeness"],
                        "sources": [], "source_bytes": 0},
        "negative_bindings": negative_bindings, "unauthorized_fields": "rejected; target unchanged"}, sort_keys=True))


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
    blocked = decode(first, allow_error=True)
    validate_blocked_preparation(blocked)
    assert fixture_database_state(store.db_path) == before, "blocked preparation modified fixture member rows"
    assert fixture_database_fingerprint(store.db_path) == before_files, "blocked preparation changed fixture database bytes"
    mode = "text" if text_only else "structured"
    print(f"Installed {mode} preparation boundary: " + json.dumps({
        "response": blocked, "database_bytes_unchanged": True, "member_rows_unchanged": True,
        "fixture_initialization": "explicit outside-MCP empty SQLite fixture only",
        "ready_index_bootstrap": "NOT RUN", "sources": [], "source_bytes": 0,
        "positive_matrix": "NOT RUN: docs ready / partial / complete / >32KB / positive scope/version / generation repeat"}, sort_keys=True))
    blockers.append(f"{mode}: unsafe_sqlite_path_mutation; mutation_performed=false; retryable=false. "
                    "Positive preparation acceptance remains blocked. Descriptor-bound safe storage is not integrated in this artifact; no retries or bypass. "
                    "Outside-MCP ready-index diagnostics, when explicitly selected, are not preparation acceptance.")
    return blockers


def validate_blocked_preparation(response: dict) -> None:
    assert response.get("status") == "blocked", response
    assert response.get("reason_code") == "unsafe_sqlite_path_mutation", response
    assert response.get("retryable") is False and response.get("mutation_performed") is False, response


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


def bootstrap_ready_fixture(project: Path) -> dict:
    """Fixture author setup, never preparation acceptance or legacy migration."""
    from docmancer.core.models import Document
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.application.project_docs_member_transaction import local_project_identity
    from docmancer.docs.project import ProjectMetadataReader

    catalog_path = project / "docatlas.project-docs.yaml"
    catalog = json.loads(catalog_path.read_text())
    for entry in catalog["documents"]:
        entry["authority"] = "source_of_truth"
    for name in ("alpha", "beta"):
        module = project / "packages" / name
        module.mkdir(parents=True)
        (module / "pyproject.toml").write_text(f'[project]\nname = "fixture-{name}"\nversion = "1.0.0"\n')
        (module / "README.md").write_text(
            f"# {name.title()} transport\n\nThe {name} transport command is `{name}-start`.\n", encoding="utf-8")
        catalog["documents"].append({"path": f"packages/{name}/README.md", "role": "module_architecture",
            "scope": "module", "module_path": f"packages/{name}", "description": f"Fixture {name} transport",
            "authority": "source_of_truth"})
    catalog_path.write_text(json.dumps(catalog, sort_keys=True), encoding="utf-8")
    (project / ".gitignore").write_text(".docatlas/\n", encoding="utf-8")
    _accept_fixture(project)
    metadata = ProjectMetadataReader().read(project)
    assert metadata.docs_catalog_valid, metadata.warnings
    identity = local_project_identity(project)
    documents = []
    provenance = {}
    for candidate in metadata.docs_candidates:
        path = project / candidate.path
        content = path.read_bytes().decode("utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert candidate.content_hash == "sha256:" + digest
        document_metadata = {
            "project_path": str(project), "project_identity": identity, "repository_identity": identity,
            "source_class": "project_file", "project_docs": True, "source_path": candidate.path,
            "project_doc_path": candidate.path, "project_doc_content_hash": candidate.content_hash,
            "project_doc_catalog_entry_hash": candidate.catalog_entry_hash,
            "project_doc_mtime_ns": candidate.mtime_ns, "project_doc_reason": candidate.reason,
            "doc_scope": candidate.doc_scope, "module_path": candidate.module_path,
            "module_id": candidate.module_id, "module_name": candidate.module_name,
            "module_type": candidate.module_type, "project_doc_description": candidate.description,
            "project_doc_authority": candidate.authority, "project_doc_lifecycle_status": candidate.lifecycle_status,
            "lifecycle_status": candidate.lifecycle_status, "project_doc_impact_policy": candidate.impact_policy,
            "index_freshness": "synchronized",
        }
        documents.append(Document(source=str(path), content=content, metadata=document_metadata))
        provenance[candidate.path] = {"content_sha256": digest, "bytes": len(path.read_bytes()),
                                     "scope": candidate.doc_scope, "module_path": candidate.module_path}
    store = SQLiteStore(project / ".docatlas" / "docatlas.db")
    result = store.add_documents(documents)
    return {"generation_id": result.generation_id, "project_identity": identity,
            "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(), "files": provenance}


def evidence_sizes(response: dict, project: Path) -> dict:
    """Count returned bytes and union actual source spans; never wire wrappers."""
    sources = response.get("sources", [])
    total = 0
    intervals = {}
    details = []
    for row in sources:
        text = row.get("text", row.get("snippet", ""))
        path = row.get("path", row.get("path_or_url", ""))
        total += len(text.encode("utf-8"))
        detail = {"path": path, "evidence_id": row.get("evidence_id"),
                  "bytes": len(text.encode("utf-8")), "content_sha256": row.get("content_sha256")}
        start, end = row.get("char_start"), row.get("char_end")
        parsed = urlparse(path)
        source = (Path(url2pathname(parsed.path)) if parsed.scheme == "file" else project / path).resolve()
        assert source.is_relative_to(project.resolve()) and source.is_file(), row
        raw = source.read_bytes().decode("utf-8")
        if "text" in row:
            assert type(start) is int and type(end) is int and raw[start:end] == text, row
            assert hashlib.sha256(text.encode()).hexdigest() == row["content_sha256"], row
            detail["span_basis"] = "returned patch span"
        else:
            assert text and raw.count(text) == 1, "docs snippet cannot be uniquely bound for byte measurement"
            start = raw.index(text)
            end = start + len(text)
            detail["span_basis"] = "unique exact docs snippet occurrence; reporting only, not an added witness"
        intervals.setdefault(str(source), []).append((start, end))
        detail.update(char_start=start, char_end=end)
        details.append(detail)
    unique = 0
    for path, spans in intervals.items():
        merged = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        raw = Path(path).read_bytes().decode("utf-8")
        unique += sum(len(raw[start:end].encode("utf-8")) for start, end in merged)
    return {"source_text_utf8_bytes": total, "unique_nonoverlap_utf8_bytes": unique,
            "unique_span_measurement": "returned patch spans / uniquely located exact docs snippets", "sources": details}


def bootstrap_library_fixture(project: Path, index_root: Path) -> dict:
    """Real local authored versions, no remote URL, fetch, or external claim."""
    from docmancer.core.config import DocmancerConfig
    from docmancer.core.models import Document
    from docmancer.core.product_identity import ensure_owned_home
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.infrastructure.agent_index_gateway import AgentIndexGateway
    from docmancer.docs.registry import LibraryRegistry

    database = project / ".docatlas" / "docatlas.db"
    ensure_owned_home(index_root.parent)  # Explicit fresh fixture home before populating it.
    registry = LibraryRegistry(database)
    config = DocmancerConfig(index={"db_path": str(database)})
    gateway = AgentIndexGateway(config, library_index_root=index_root)
    now = datetime.now(timezone.utc).isoformat()
    fixtures = {}
    for version, command in (("1.0.0", "fixture-open"), ("2.0.0", "fixture-connect")):
        directory = project / "library-fixtures" / version
        directory.mkdir(parents=True)
        path = directory / "reference.md"
        content = f"# Local transport fixture {version}\n\nFor authored version {version}, the transport command is `{command}`.\n"
        path.write_text(content, encoding="utf-8")
        record = registry.upsert(library="local-transport-fixture", ecosystem=None, version=version,
            source_type="api", docs_url=directory.as_uri(), now=now, status="available",
            last_refreshed_at=now, requested_version=version, resolved_version=version,
            version_source="explicit", version_inferred=False,
            docs_snapshot_exact=True)  # Author selected the exact local version directory/bytes.
        indexed = gateway.index_config_for(record)
        metadata = {"library_id": record.library_id, "canonical_id": record.canonical_id,
                    "resolved_version": version, "version": version, "docs_snapshot_exact": True,
                    "source_class": "library_doc", "doc_scope": "library", "authority": "official",
                    "docset_root": directory.as_uri(), "canonical_url": path.as_uri(),
                    "source_origin_url": path.as_uri()}
        store = SQLiteStore(indexed.index.db_path, extracted_dir=indexed.index.extracted_dir)
        result = store.add_documents([Document(source=path.as_uri(), content=content, metadata=metadata)])
        fixtures[version] = {"source": path.as_uri(), "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "generation_id": result.generation_id, "database": str(store.db_path)}
    _accept_fixture(project)
    return fixtures


async def ready_index_diagnostic(session, project: Path, *, text_only: bool, environment: dict) -> list[str]:
    decode = text_payload if text_only else payload
    bootstrap = bootstrap_ready_fixture(project)
    library_home = project.parent / f"{project.name}-library-home"
    library_home.mkdir()
    library_environment = {**environment, "DOCATLAS_HOME": str(library_home)}
    libraries = bootstrap_library_fixture(project, library_home / "docs-indexes")
    library_before = {version: fixture_database_state(Path(row["database"])) for version, row in libraries.items()}
    database = project / ".docatlas" / "docatlas.db"
    before = fixture_database_state(database)
    before_bytes = fixture_database_fingerprint(database)
    queries = {
        "docs_default": {"question": QUESTION},
        "complete": {"question": "What command is documented as `doc-atlas mcp docs-serve`?"},
        "partial": {"question": "What command is documented as `doc-atlas mcp docs-serve` and `AbsentFixtureConstraint`?",
                    "lookup_queries": [NEEDLE]},
        "project_scope": {"question": QUESTION, "scope": "project"},
        "module_alpha": {"question": "What is the `alpha-start` transport command?", "module_path": "packages/alpha"},
        "module_beta": {"question": "What is the `beta-start` transport command?", "scope": "module", "module_path": "packages/beta"},
        "all_scope": {"question": "Which transport commands are `alpha-start` and `beta-start`?", "scope": "all",
                      "lookup_queries": ["alpha-start", "beta-start"]},
        "version_mismatch": {"question": QUESTION, "version": "99.0.0"},
        "module_mismatch": {"question": QUESTION, "module_path": "missing-module"},
        "large": {"question": "Inspect " + " ".join(f"`validate_protocol_{i}`" for i in range(12)),
                  "lookup_queries": [f"validate_protocol_{i}" for i in range(5)]},
        "library_v1": {"question": "What is the `fixture-open` transport command?", "library": "local-transport-fixture", "version": "1.0.0"},
        "library_v2": {"question": "What is the `fixture-connect` transport command?", "library": "local-transport-fixture", "version": "2.0.0"},
        "library_missing_version": {"question": "What is the transport command?", "library": "local-transport-fixture", "version": "99.0.0"},
    }
    outcomes = {}
    blockers = []
    for name, query in queries.items():
        arguments = query.copy() if name.startswith("library_") else {"project_path": str(project), **query}
        if name != "docs_default":
            arguments["context_format"] = "patch_context"
        if name.startswith("library_"):
            # A library-only public call in a separately configured fixture
            # process avoids widening it into a mixed project/library request.
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            params = StdioServerParameters(command=shutil.which("doc-atlas"),
                args=["mcp", "docs-serve", "--config", str(project / "docatlas.yaml")],
                env=library_environment, cwd=str(project.parent))
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as library_session:
                    await library_session.initialize()
                    await library_session.list_tools()
                    wire = await library_session.call_tool("get_docs_context", arguments)
        else:
            wire = await session.call_tool("get_docs_context", arguments)
        response = decode(wire, allow_error=True)
        outcome = {"status": response.get("status"), "result": response.get("result"),
                   "completeness": response.get("completeness"), "missing": response.get("missing", []),
                   "tool_wire_utf8_bytes": len(wire.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")),
                   "tool_wire_measurement": "serialized CallToolResult, excluding JSON-RPC envelope/framing"}
        try:
            assert not wire.isError, response
            if name == "docs_default":
                validate_context_payload(response, required_fragment=NEEDLE)
            else:
                validate_patch_payload(response)
            outcome.update(evidence_sizes(response, project))
            if name in {"complete", "partial"}:
                assert response["result"] == "data" and response["completeness"] == name, response
            if name in {"project_scope", "module_alpha", "module_beta", "all_scope"}:
                assert response["result"] == "data", response
                paths = {row["path"] for row in response["sources"]}
                if name == "project_scope":
                    assert paths <= {"README.md", "protocols.md"}, paths
                elif name in {"module_alpha", "module_beta"}:
                    module = "alpha" if name == "module_alpha" else "beta"
                    assert paths == {f"packages/{module}/README.md"}, paths
                else:
                    assert {"packages/alpha/README.md", "packages/beta/README.md"} <= paths, paths
            if name in {"library_v1", "library_v2"}:
                version = "1.0.0" if name == "library_v1" else "2.0.0"
                assert response["result"] == "data" and response["completeness"] == "complete", response
                assert {row["path"] for row in response["sources"]} == {libraries[version]["source"]}, response
                assert all(row.get("version_binding") == version for row in response["sources"]), response
            if name in {"version_mismatch", "module_mismatch", "library_missing_version"}:
                assert response["completeness"] != "complete", response
            outcome["check"] = "observed"
        except (AssertionError, KeyError, ValueError) as exc:
            outcome["check"] = "BLOCKED"
            outcome["error"] = str(exc)
            blockers.append(f"{name}: {exc}")
        if name == "large":
            outcome["gate"] = "BLOCKED_upstream"
            blockers.append(">32KB necessary admitted source remains BLOCKED_upstream: unchanged public 4000-token merged project budget; no budget override or fabricated windows")
        outcomes[name] = outcome
    after = fixture_database_state(database)
    assert after == before, "public fixture reads changed indexed evidence generation/member state"
    assert {version: fixture_database_state(Path(row["database"])) for version, row in libraries.items()} == library_before, "library public reads changed evidence generation"
    print(f"Installed {'text' if text_only else 'structured'} READY-INDEX DIAGNOSTIC: " + json.dumps({
        "bootstrap": "actual SQLiteStore.add_documents outside MCP; NOT prepare acceptance; NOT legacy identity compatibility",
        "provenance": bootstrap, "local_library_provenance": libraries, "matrix": outcomes, "source_generation_rows_unchanged": True,
        "library_generation_rows_unchanged": True,
        "whole_database_bytes_unchanged": fixture_database_fingerprint(database) == before_bytes,
        "whole_database_note": "registry/job initialization can change other tables; distinct from indexed evidence",
        "library_lineage_note": "_unified_context_service_part02._library_context_pack omits original char/line spans, parent id and snapshot lineage; validation/size binding remains strict; local authored provenance only"}, sort_keys=True))
    return blockers


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
                                                             "project_path": str(project)}), allow_error=True)
    assert terminal["status"] == "failed" and terminal["retryable"] is False, terminal
    assert terminal["counts"]["pages"]["total"] == 0, terminal


async def smoke(*, read_only: bool = False, ready_index: bool = False) -> None:
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
                        try:
                            blockers.extend(await indexed_delivery(session, project, text_only=text_only))
                            if ready_index:
                                blockers.extend(await ready_index_diagnostic(session, project, text_only=text_only, environment=params.env))
                        except Exception as exc:
                            blockers.append(f"{'text' if text_only else 'structured'} indexed matrix aborted: {type(exc).__name__}: {exc}")
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--read-only", action="store_true")
    mode.add_argument("--ready-index", action="store_true", help="Outside-MCP accepted fixture bootstrap and real public retrieval diagnostic; never preparation acceptance")
    args = parser.parse_args()
    asyncio.run(smoke(read_only=args.read_only, ready_index=args.ready_index))
