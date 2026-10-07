"""Real local MCP lifecycle, with disposable host state and no fixture indexing."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier

import pytest
import yaml

from docmancer.core.member_storage_policy import MemberStoragePolicy
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, create_local_mcp_service


@pytest.fixture
def cold(tmp_path, monkeypatch):
    # Source-runtime subprocesses must use this checkout after the fixture changes
    # cwd, not another editable install in the interpreter environment. Installed
    # wheel acceptance deliberately runs separately without this source path.
    source_root = str(Path(__file__).resolve().parents[1])
    inherited_pythonpath = os.environ.get("PYTHONPATH")
    monkeypatch.setenv("PYTHONPATH", source_root + (
        os.pathsep + inherited_pythonpath if inherited_pythonpath else ""))
    home = tmp_path / "app-home"
    monkeypatch.setenv("DOCATLAS_HOME", str(home))
    monkeypatch.delenv("DOCATLAS_INDEX_DB_PATH", raising=False)
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text(
        "# Docs MCP server\n\nThe command that starts the Docs MCP server is `doc-atlas mcp docs-serve`.\n"
    )
    (root / "other.md").write_text("# Other\n\nUnrelated immutable member evidence.\n")
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "code_files": [], "documents": [
            {"path": name, "role": "overview", "scope": "project", "description": name}
            for name in ("README.md", "other.md")
        ],
    }))
    monkeypatch.chdir(tmp_path)
    service = create_local_mcp_service()
    assert not home.exists()
    return root, service


def request(cold, *, generation=None, paths=("README.md",)):
    root, service = cold
    entries = {row.path: row for row in read_project_docs_catalog(root).entries}
    return {"action": "sync_project_docs", "project_path": str(root), "mutation": {
        "operation": "sync_project_docs", "confirm": True,
        "storage_path": str(service.member_storage_policy.db_path),
        "catalog_sha256": hashlib.sha256((root / "docatlas.project-docs.yaml").read_bytes()).hexdigest(),
        "expected_generation_id": generation,
        "documents": [{"path": path, "content_sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
                       "catalog_entry_hash": catalog_entry_hash(entries[path])} for path in paths],
    }}


def prepare(cold, **kwargs):
    result = call_docs_tool_payload("prepare_docs", request(cold, **kwargs), cold[1])
    assert result.get("status") == "success", result
    generation = result["metrics"]["generation_id"]
    assert generation == cold[1].member_storage_policy.generation()
    return generation


def member_state(policy):
    with closing(policy.connect()) as conn:
        return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in ("sources", "sections", "index_state", "index_generations",
                              "generation_sources", "retrieval_children", "retrieval_children_fts")}


def retrieve(cold):
    return call_docs_tool_payload("get_docs_context", {
        "question": "Which command starts the Docs MCP server?", "project_path": str(cold[0]),
        "scope": "project",
    }, cold[1])


def test_cold_prepare_public_retrieve_and_restart(cold):
    root, service = cold
    generation = prepare(cold)
    policy = service.member_storage_policy
    assert generation.startswith("gen-")
    assert policy.db_path.stat().st_mode & 0o777 == 0o600
    assert policy.db_path.parent.stat().st_mode & 0o777 == 0o700
    assert not (policy.db_path.parent / "extracted").exists()
    before = member_state(policy)
    for current in (service, create_local_mcp_service()):
        answer = retrieve((root, current))
        assert answer.get("status") == "ok", answer
        assert answer["sources"], answer
        assert any("doc-atlas mcp docs-serve" in source["snippet"] for source in answer["sources"])
        for source in answer["sources"]:
            assert source["snippet"] in (root / "README.md").read_text()
            assert len(source["content_sha256"]) == 64
        assert current.materialize().config.index.db_path == str(policy.db_path)
        assert policy.generation() == generation
    assert member_state(policy) == before
    assert not (root / ".docatlas" / "docatlas.db").exists()


@pytest.mark.parametrize("invalid", ["read", "missing", "null", "false", "generation_missing", "wrong_hash", "wrong_target", "stale"])
def test_cold_invalid_or_read_request_never_provisions(cold, invalid):
    root, service = cold
    args = request(cold)
    if invalid == "read":
        result = retrieve(cold)
    else:
        if invalid == "missing":
            del args["mutation"]
        elif invalid == "null":
            args["mutation"] = None
        elif invalid == "false":
            args["mutation"]["confirm"] = False
        elif invalid == "generation_missing":
            del args["mutation"]["expected_generation_id"]
        elif invalid == "wrong_hash":
            args["mutation"]["documents"][0]["content_sha256"] = "0" * 64
        elif invalid == "wrong_target":
            args["mutation"]["storage_path"] = str(root / ".docatlas" / "docatlas.db")
        else:
            args["mutation"]["expected_generation_id"] = "gen-" + "0" * 32
        result = call_docs_tool_payload("prepare_docs", args, service)
    assert result.get("status") != "success", result
    assert not service.member_storage_policy.app_home.exists()
    assert service._service is None


@pytest.mark.parametrize("kind", ["foreign", "symlink", "hardlink", "directory_symlink", "public_parent", "journal", "wal"])
def test_foreign_targets_denied_before_sqlite_connect(cold, kind, monkeypatch):
    root, service = cold
    policy = service.member_storage_policy
    policy.db_path.parent.mkdir(parents=True, mode=0o700)
    foreign = root.parent / "foreign.db"
    foreign.write_bytes(b"foreign unchanged bytes")
    foreign.chmod(0o600)
    if kind == "foreign":
        policy.db_path.write_bytes(foreign.read_bytes())
        policy.db_path.chmod(0o600)
    elif kind == "symlink":
        policy.db_path.symlink_to(foreign)
    elif kind == "hardlink":
        os.link(foreign, policy.db_path)
    elif kind == "directory_symlink":
        policy.db_path.parent.rmdir()
        policy.db_path.parent.symlink_to(root.parent, target_is_directory=True)
    elif kind == "public_parent":
        root.parent.chmod(0o777)
    else:
        Path(str(policy.db_path) + ("-journal" if kind == "journal" else "-wal")).symlink_to(foreign)
    args = request(cold)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: pytest.fail("foreign target reached SQLite"))
    result = call_docs_tool_payload("prepare_docs", args, service)
    assert result.get("status") != "success", result
    assert foreign.read_bytes() == b"foreign unchanged bytes"


def test_project_config_cannot_redirect_prepare_or_retrieval(cold):
    root, service = cold
    generation = prepare(cold)
    before = member_state(service.member_storage_policy)
    foreign = root.parent / "foreign.db"
    (root / "docatlas.yaml").write_text(f"index:\n  db_path: {foreign}\n")
    result = call_docs_tool_payload("prepare_docs", request(cold, generation=generation), service)
    assert result.get("status") != "success"
    assert retrieve(cold).get("sources")
    assert retrieve((root, service.materialize())).get("sources")
    assert member_state(service.member_storage_policy) == before
    assert not foreign.exists()


def test_unchanged_repeat_stale_cas_and_unrelated_member_preservation(cold):
    root, service = cold
    first = prepare(cold, paths=("README.md", "other.md"))
    before = member_state(service.member_storage_policy)
    assert prepare(cold, generation=first, paths=("README.md", "other.md")) == first
    assert member_state(service.member_storage_policy) == before
    (root / "README.md").write_text("# Changed\n\nChanged command evidence.\n")
    second = prepare(cold, generation=first)
    assert second != first
    after = member_state(service.member_storage_policy)
    result = call_docs_tool_payload("prepare_docs", request(cold, generation=first), service)
    assert result.get("status") != "success"
    assert member_state(service.member_storage_policy) == after
    assert next(row for row in before["sources"] if row[1].endswith("other.md")) == next(
        row for row in after["sources"] if row[1].endswith("other.md"))


def test_two_different_updates_one_generation_one_commit(cold, monkeypatch):
    root, service = cold
    generation = prepare(cold, paths=("README.md", "other.md"))
    (root / "README.md").write_text("# README changed\n\nChanged first member.\n")
    (root / "other.md").write_text("# Other changed\n\nChanged second member.\n")
    requests = [request(cold, generation=generation, paths=(path,)) for path in ("README.md", "other.md")]
    barrier = Barrier(2)
    original = MemberStoragePolicy.generation
    def observed(self):
        result = original(self)
        barrier.wait(timeout=5)
        return result
    monkeypatch.setattr(MemberStoragePolicy, "generation", observed)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda args: call_docs_tool_payload("prepare_docs", args, service), requests))
    assert sum(row.get("status") == "success" for row in outcomes) == 1, outcomes


@pytest.mark.parametrize("lane", ["sources", "generation_sources"])
def test_member_owner_conflict_rolls_back(cold, lane):
    generation = prepare(cold)
    policy = cold[1].member_storage_policy
    with closing(policy.connect()) as conn, conn:
        owner = json.loads(conn.execute(f"SELECT metadata_json FROM {lane}").fetchone()[0])
        owner["project_path"] = "/different/project"
        conn.execute(f"UPDATE {lane} SET metadata_json=?", (json.dumps(owner),))
    before = member_state(policy)
    result = call_docs_tool_payload("prepare_docs", request(cold, generation=generation), cold[1])
    assert result.get("status") != "success"
    assert member_state(policy) == before


def test_member_failure_rolls_back_disk_transaction(cold, monkeypatch):
    generation = prepare(cold)
    policy = cold[1].member_storage_policy
    before = member_state(policy)
    (cold[0] / "README.md").write_text("# Changed\n\nPending member update.\n")
    def fail(*args, **kwargs):
        raise RuntimeError("activation fault")
    monkeypatch.setattr(SQLiteStore, "_activate_generation", fail)
    result = call_docs_tool_payload("prepare_docs", request(cold, generation=generation), cold[1])
    assert result.get("status") != "success"
    assert member_state(policy) == before


def test_process_restart_uses_same_host_target(cold):
    generation = prepare(cold)
    query = {"question": "Which command starts the Docs MCP server?", "project_path": str(cold[0])}
    code = """
import json, sys
from docmancer.mcp._docs_server_part01 import create_local_mcp_service, call_docs_tool_payload
service = create_local_mcp_service()
answer = call_docs_tool_payload('get_docs_context', json.load(sys.stdin), service)
print(json.dumps({'answer': answer, 'generation': service.member_storage_policy.generation(),
                  'database': str(service.member_storage_policy.db_path)}))
"""
    result = subprocess.run([sys.executable, "-c", code], input=json.dumps(query), text=True,
                            capture_output=True, check=True, timeout=30)
    observed = json.loads(result.stdout)
    assert observed["generation"] == generation
    assert observed["database"] == str(cold[1].member_storage_policy.db_path)
    assert observed["answer"].get("status") == "ok", observed
    assert any("doc-atlas mcp docs-serve" in source["snippet"] for source in observed["answer"]["sources"])


def test_intact_journal_recovers_after_production_writer_process_crash(cold):
    generation = prepare(cold)
    policy = cold[1].member_storage_policy
    before = member_state(policy)
    (cold[0] / "README.md").write_text("# Changed\n\nCrash recovery pending publication.\n")
    code = """
import json, os, sys
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.mcp._docs_server_part01 import create_local_mcp_service, call_docs_tool_payload
original = SQLiteStore._apply_project_members
def crash(self, conn, *args):
    conn.execute('PRAGMA cache_size=1')
    original(self, conn, *args)
    # Force dirty pages out while the real member transaction is uncommitted.
    conn.execute('CREATE TABLE crash_spill(value BLOB)')
    conn.execute('INSERT INTO crash_spill VALUES (zeroblob(65536))')
    os._exit(86)
SQLiteStore._apply_project_members = crash
call_docs_tool_payload('prepare_docs', json.load(sys.stdin), create_local_mcp_service())
"""
    result = subprocess.run([sys.executable, "-c", code], input=json.dumps(request(cold, generation=generation)),
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 86, result.stderr
    assert Path(str(policy.db_path) + "-journal").exists()
    restarted = create_local_mcp_service()
    assert member_state(restarted.member_storage_policy) == before
    with closing(policy.connect()) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='crash_spill'").fetchone()


def test_commit_return_failure_reports_unknown_not_no_mutation(cold, monkeypatch):
    generation = prepare(cold)
    policy = cold[1].member_storage_policy
    (cold[0] / "README.md").write_text("# Changed\n\nChanged member before ambiguous result.\n")
    original = MemberStoragePolicy.connect
    class Connection:
        def __init__(self, conn):
            self.conn = conn
        def __getattr__(self, name):
            return getattr(self.conn, name)
        def commit(self):
            self.conn.commit()
            raise sqlite3.OperationalError("lost commit acknowledgement")
    monkeypatch.setattr(MemberStoragePolicy, "connect", lambda self: Connection(original(self)))
    result = call_docs_tool_payload("prepare_docs", request(cold, generation=generation), cold[1])
    assert result["reason_code"] == "member_commit_outcome_unknown", result
    assert result["mutation_performed"] is None and result["retryable"] is False
    assert policy.generation() != generation


def test_prepared_module_and_project_scope_isolation(cold):
    root, service = cold
    catalog = yaml.safe_load((root / "docatlas.project-docs.yaml").read_text())
    for name in ("alpha", "beta"):
        module = root / "packages" / name
        module.mkdir(parents=True)
        (module / "pyproject.toml").write_text(f'[project]\nname = "fixture-{name}"\nversion = "1.0.0"\n')
        (module / "README.md").write_text(f"# {name} transport\n\nThe {name} transport command is `{name}-start`.\n")
        catalog["documents"].append({"path": f"packages/{name}/README.md", "role": "module_architecture",
                                     "scope": "module", "module_path": f"packages/{name}", "description": name})
    (root / "docatlas.project-docs.yaml").write_text(yaml.safe_dump(catalog))
    prepare(cold, paths=("README.md", "packages/alpha/README.md", "packages/beta/README.md"))
    for name in ("alpha", "beta"):
        answer = call_docs_tool_payload("get_docs_context", {
            "question": f"What is the {name} transport command?", "project_path": str(root),
            "module_path": f"packages/{name}",
        }, service)
        assert answer.get("sources"), answer
        assert any(f"{name}-start" in row["snippet"] for row in answer["sources"])
        assert all(f"packages/{name}/README.md" in row["path_or_url"] for row in answer["sources"])
    answer = retrieve(cold)
    assert answer.get("sources"), answer
    assert all("packages/" not in row["path_or_url"] for row in answer["sources"])
    other = root.parent / "other-project"
    other.mkdir()
    answer = call_docs_tool_payload("get_docs_context", {
        "question": "Which command starts the Docs MCP server?", "project_path": str(other),
    }, service)
    assert not answer.get("sources"), answer


def test_cwd_config_and_legacy_database_are_not_selected(cold, monkeypatch):
    root, service = cold
    foreign = root / "legacy.db"
    foreign.write_bytes(b"unused old database")
    (root / "docatlas.yaml").write_text(f"index:\n  db_path: {foreign}\n")
    monkeypatch.chdir(root)
    another = create_local_mcp_service()
    assert another.member_storage_policy == service.member_storage_policy
    assert foreign.read_bytes() == b"unused old database"
    assert not service.member_storage_policy.app_home.exists()


def test_host_config_inside_project_denied_before_initialization(cold):
    root, service = cold
    path = root / "host.yaml"
    path.write_text(f"index:\n  db_path: {service.member_storage_policy.db_path}\n")
    untrusted = create_local_mcp_service(path)
    result = call_docs_tool_payload("prepare_docs", request((root, untrusted)), untrusted)
    assert result.get("status") != "success"
    assert not untrusted.member_storage_policy.app_home.exists()


@pytest.mark.parametrize("text_only", [False, True])
def test_real_source_stdio_cold_prepare_retrieve_restart(cold, text_only):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from scripts.docs_mcp_stdio_smoke import payload, text_payload
    root, service = cold
    decode = text_payload if text_only else payload
    env = {key: os.environ[key] for key in ("PATH", "PYTHONPATH") if key in os.environ}
    env.update(DOCATLAS_HOME=str(service.member_storage_policy.app_home),
               HOME=str(root.parent / "isolated-os-home"), DOCATLAS_OFFLINE="1",
               DOCATLAS_AUTO_VECTORS="0", PYTHONDONTWRITEBYTECODE="1")
    if text_only:
        env["DOCATLAS_MCP_TEXT_FALLBACK"] = "1"
    params = StdioServerParameters(command=sys.executable,
                                  args=["-m", "docmancer.cli", "mcp", "docs-serve"],
                                  env=env, cwd=str(root.parent))
    async def lifecycle():
        generation = None
        for restart in (False, True):
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    prepared = decode(await session.call_tool("prepare_docs", request(cold, generation=generation)))
                    assert prepared["status"] == "success", prepared
                    if restart:
                        assert prepared["metrics"]["generation_id"] == generation
                        assert prepared["metrics"]["derived_writes"] == 0
                    generation = prepared["metrics"]["generation_id"]
                    answer = decode(await session.call_tool("get_docs_context", {
                        "question": "Which command starts the Docs MCP server?", "project_path": str(root),
                    }))
                    assert answer["status"] == "ok", answer
                    assert any("doc-atlas mcp docs-serve" in row["snippet"] for row in answer["sources"])
    asyncio.run(lifecycle())
    assert not (root / ".docatlas" / "docatlas.db").exists()
