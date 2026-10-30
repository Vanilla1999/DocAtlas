"""Installed CLI/config/stdio proof of explicit current-project host binding.

The original five Black questions, sources and V40 gold remain unchanged.
Separate tiny lifecycle/scope fixtures exercise host binding, not search tuning.
No paid model, autonomous OpenCode, mocked retrieval or local production run.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


checks = load("project_binding_checks", Path(__file__).with_name("checks.py"))
save = checks.save


def environment(root: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LD_LIBRARY_PATH", "TIKTOKEN_CACHE_DIR"}}
    for key, name in {"HOME": "home", "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                      "XDG_CACHE_HOME": "cache", "DOCATLAS_HOME": "docatlas-home"}.items():
        path = root / name
        path.mkdir(parents=True, mode=0o700)
        env[key] = str(path)
    env.update(DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0", HF_HUB_OFFLINE="1",
               DOCATLAS_MINILM_MODEL_DIR="/model", DOCATLAS_MCP_TEXT_FALLBACK="1",
               DOCATLAS_MCP_COMPACT_TEXT="1", DOCATLAS_MCP_MODEL_VIEW="off",
               PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", NO_PROXY="*",
               TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="2")
    return env


class Recorder:
    def __init__(self, out: Path):
        self.out, self.counts = out, Counter()

    def note(self, operation, status, **fields):
        with (self.out / "OPERATIONS.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"operation": operation, "status": status,
                                     "monotonic": time.monotonic(), **fields}, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def cli(self, label, command, env, cwd, *, success=True):
        self.counts["installer_cli"] += 1
        self.note("installer_cli", "started", label=label, command=command, cwd=str(cwd))
        result = subprocess.run(command, env=env, cwd=cwd, text=True,
                                capture_output=True, timeout=60)
        save(self.out / f"{label}.json", {"command": command, "cwd": str(cwd),
                                        "returncode": result.returncode,
                                        "stdout": result.stdout, "stderr": result.stderr})
        self.note("installer_cli", "returned", label=label, returncode=result.returncode)
        assert (result.returncode == 0) is success, result.stdout + result.stderr
        return result

    async def call(self, session, label, name, arguments):
        from docmancer.docs.application.projection_tokenizer import projection_token_count

        self.counts[name] += 1
        self.note(name, "started", label=label, arguments=arguments)
        started = time.monotonic()
        reply = await asyncio.wait_for(session.call_tool(name, arguments), 240)
        packet, raw = checks.contents(reply)
        item = {"tool": name, "arguments": arguments, "seconds": time.monotonic() - started,
                "isError": bool(reply.isError), "utf8_bytes": len(raw.encode()),
                "text_o200k": projection_token_count(raw.encode()), "payload": packet}
        save(self.out / f"{label}.json", item)
        self.note(name, "returned", label=label, status_value=packet.get("status"), isError=bool(reply.isError))
        return packet, item

    async def resource(self, session, label, row, documents, root):
        self.counts["resources/read"] += 1
        self.note("resources/read", "started", label=label, uri=row["source_uri"])
        result = await asyncio.wait_for(session.read_resource(row["source_uri"]), 60)
        assert len(result.contents) == 1
        content = json.loads(result.contents[0].text)
        save(self.out / f"{label}.json", content)
        checks.check_resource(content, row, documents, root)
        self.note("resources/read", "returned", label=label, status_value=content.get("status"))


@asynccontextmanager
async def server(recorder, label, command, env, cwd):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    recorder.counts["server_processes"] += 1
    recorder.note("server", "started", label=label, command=command, cwd=str(cwd))
    params = StdioServerParameters(command=command[0], args=command[1:], env=env, cwd=str(cwd))
    with (recorder.out / f"{label}-stderr.log").open("w") as stderr:
        async with stdio_client(params, errlog=stderr) as streams:
            async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=240)) as session:
                await asyncio.wait_for(session.initialize(), 60)
                recorder.counts["initialize"] += 1
                listed = await asyncio.wait_for(session.list_tools(), 60)
                recorder.counts["tools/list"] += 1
                save(recorder.out / f"{label}-catalog.json", listed.model_dump(mode="json"))
                assert {tool.name for tool in listed.tools} == {"get_docs_context", "prepare_docs", "docs_status"}
                spec = next(tool for tool in listed.tools if tool.name == "get_docs_context")
                assert spec.inputSchema.get("required") == ["question"]
                assert getattr(spec, "outputSchema", None) is None
                yield session
    recorder.note("server", "exited", label=label)


def installed_command() -> list[str]:
    command = Path(sys.executable).parent / "doc-atlas"
    assert command.is_file(), command
    return [str(command)]


def installed_registration(recorder, work, env, files) -> list[str]:
    """Exercise the real installed public installer, including refusal/no-op."""
    executable = installed_command()
    project = work / "black"
    recorder.cli("INSTALL-global", executable + ["install", "opencode"], env, project)
    global_path = Path(env["HOME"]) / ".config/opencode/opencode.json"
    global_bytes = global_path.read_bytes()
    global_entry = json.loads(global_bytes)["mcp"]["servers"]["docatlas"]
    assert global_entry["command"] == ["doc-atlas", "mcp", "docs-serve"]
    assert "DOCATLAS_PROJECT_ROOT" not in global_entry.get("environment", {})
    recorder.cli("INSTALL-project", executable + ["install", "opencode", "--project"], env, project)
    config_path = project / "opencode.json"
    entry = json.loads(config_path.read_text())["mcp"]["servers"]["docatlas"]
    expected = ["doc-atlas", "mcp", "docs-serve", "--project-root", str(project)]
    assert entry["command"] == expected
    assert entry["environment"] == {"DOCATLAS_MCP_TEXT_FALLBACK": "1", "DOCATLAS_MCP_COMPACT_TEXT": "1"}
    before = files(project)
    recorder.cli("INSTALL-project-again", executable + ["install", "opencode", "--project"], env, project)
    assert files(project) == before and global_path.read_bytes() == global_bytes

    upgraded = work / "legacy-install"
    upgraded.mkdir()
    save(upgraded / "opencode.json", {"model": "keep", "mcp": {"my-docs": {
        "type": "local", "command": ["doc-atlas", "mcp", "docs-serve"], "enabled": False,
        "environment": {"CUSTOM": "keep"}, "timeout": {"startup": 42000}}}})
    recorder.cli("INSTALL-upgrade", executable + ["install", "opencode", "--project"], env, upgraded)
    config = json.loads((upgraded / "opencode.json").read_text())
    assert config["model"] == "keep" and set(config["mcp"]["servers"]) == {"my-docs"}
    migrated = config["mcp"]["servers"]["my-docs"]
    assert migrated["disabled"] is True and "enabled" not in migrated
    assert migrated["environment"]["CUSTOM"] == "keep" and migrated["timeout"] == {"startup": 42000}
    assert migrated["command"] == ["doc-atlas", "mcp", "docs-serve", "--project-root", str(upgraded)]

    conflict = work / "conflicting-install"
    conflict.mkdir()
    save(conflict / "opencode.json", {"mcp": {"servers": {"custom-docs": entry}}})
    before = files(conflict)
    refused = recorder.cli("INSTALL-conflict", executable + ["install", "opencode", "--project"],
                           env, conflict, success=False)
    assert "refusing to overwrite" in refused.stderr
    assert files(conflict) == before
    save(recorder.out / "INSTALLER.json", {"project_root": str(project), "command": entry["command"],
         "global_remains_unbound": True, "project_registration_idempotent": True,
         "legacy_upgrade_preserves_name_state_options": True, "conflicting_binding_unchanged": True,
         "launch_boundary": "installed console command from generated project-local OpenCode config"})
    return executable + entry["command"][1:]


def prepared_mutation(env, project):
    # Reuse the existing installed public-MCP preparation helper. It computes
    # hashes from fixture documents, not expected answers or retrieval output.
    helper = load("binding_prepare", REPO / "eval/opencode_compat/installed_stdio.py")
    return helper.prepared_mutation(env, project)


async def original_black(recorder, work, env, bound_command, runtime, state):
    project, other_cwd = work / "black", work / "unrelated-cwd"
    other_cwd.mkdir()
    (other_cwd / "README.md").write_text("# Unrelated workspace\n\nThe default length is 13.\n")
    docs = checks.source_docs(REPO)
    plain_command = installed_command() + ["mcp", "docs-serve"]
    before_cold = state.files(work / "host")
    async with server(recorder, "unbound", plain_command, env, project) as session:
        for case_id, question in checks.CASES:
            packet, item = await recorder.call(session, case_id + "-unbound", "get_docs_context", {"question": question})
            assert item["isError"] and packet["error"]["reason_code"] == "docs_context_target_missing"
            assert not checks.decoded_rows(packet)[0]
    assert state.files(work / "host") == before_cold

    mutation, storage = prepared_mutation(env, project)
    assert not storage.exists()
    before_cold = state.files(work / "host"), state.files(project), state.files(other_cwd)
    outcomes = []
    async with server(recorder, "host-bound", bound_command, env, other_cwd) as session:
        cold, item = await recorder.call(session, "cold-bound", "get_docs_context", {"question": checks.CASES[0][1]})
        assert cold.get("reason_code", (cold.get("error") or {}).get("reason_code")) == "needs_prepare", cold
        assert not checks.decoded_rows(cold)[0] and not storage.exists()
        assert (state.files(work / "host"), state.files(project), state.files(other_cwd)) == before_cold
        prepared, _ = await recorder.call(session, "PREPARE", "prepare_docs", {
            "action": "sync_project_docs", "project_path": str(project), "mutation": mutation})
        assert prepared.get("status") == "success", prepared
        inventory = {"storage_path": str(storage), "generation_id": prepared["metrics"]["generation_id"]}
        save(recorder.out / "SNAPSHOTS.json", state.snapshots(inventory, project, docs))
        before = state.database(storage), state.files(project), state.files(other_cwd)
        first_rows = None
        for case_id, question in checks.CASES:
            packet, item = await recorder.call(session, case_id + "-bound", "get_docs_context", {"question": question})
            assert not item["isError"] and packet.get("kind") == "docs_context", packet
            rows, intervals, fmt = checks.checked_rows(packet, docs, project)
            if rows:
                assert fmt in {"docatlas.standalone-text.v1", "docatlas.assembled-grouped.v1",
                               "docatlas.assembled-table.v1", "docatlas.assembled-grouped-table.v1"}
            assert item["utf8_bytes"] <= 48_000 and item["text_o200k"] <= 12000
            gold = checks.frozen_gold(REPO, case_id, docs, intervals, rows)
            if case_id == "B08":
                gold["negative_context_available_false"] = packet.get("context_available") is False
                gold["frozen_negative_contract_pass"] = not rows and packet.get("context_available") is False
            if case_id in {"B01", "B02", "B05"}:
                assert gold["all_documented_claims_covered"], (case_id, gold)
            if case_id == "B06":
                # Preserve the previous scenario's nonempty partial result;
                # report the full unchanged documented-part witness score.
                assert rows, (case_id, "no source evidence for the documented partial question")
            outcomes.append({"id": case_id, "source_rows": len(rows), "context_format": fmt,
                             "utf8_bytes": item["utf8_bytes"], "text_o200k": item["text_o200k"],
                             "frozen_gold": gold})
            if case_id == "B01":
                first_rows = rows
                await recorder.resource(session, "B01-source-read", rows[0], docs, project)
        same, _ = await recorder.call(session, "explicit-same-root", "get_docs_context", {
            "question": checks.CASES[0][1], "project_path": str(project)})
        same_rows, _, _ = checks.checked_rows(same, docs, project)
        assert checks.source_signature(same_rows) == checks.source_signature(first_rows)
        conflict, item = await recorder.call(session, "explicit-conflicting-root", "get_docs_context", {
            "question": checks.CASES[0][1], "project_path": str(other_cwd)})
        assert item["isError"] and conflict["error"]["reason_code"] == "docs_context_target_conflict"
        assert not checks.decoded_rows(conflict)[0]
        library, _ = await recorder.call(session, "library-only", "get_docs_context", {
            "question": checks.CASES[0][1], "library": "black"})
        assert (library.get("error") or {}).get("reason_code") not in {
            "docs_context_target_missing", "docs_context_target_conflict"}
        assert not checks.decoded_rows(library)[0], "Unregistered library must not inherit the host project"
        assert (state.database(storage), state.files(project), state.files(other_cwd)) == before
    assert (state.database(storage), state.files(project), state.files(other_cwd)) == before
    # Exercise the legacy unbound explicit-path refusal on a PREPARED store.
    # Otherwise a mistaken CWD fallback could fail merely because it is cold.
    async with server(recorder, "unavailable-target", plain_command, env, project) as session:
        missing, _ = await recorder.call(session, "unavailable-root", "get_docs_context", {
            "question": checks.CASES[0][1], "project_path": str(work / "nonexistent")})
        assert missing.get("status") not in {"ok", "truncated"} and not checks.decoded_rows(missing)[0]
    assert (state.database(storage), state.files(project), state.files(other_cwd)) == before
    save(recorder.out / "BLACK.json", {"questions": outcomes, "source_and_state_integrity": "PASS",
         "question_only_equals_explicit_binding": True, "unrelated_server_cwd_ignored": True,
         "B06_partial_B08_negative": "Unchanged frozen scores, not a claim of complete answers or negative retrieval success"})
    return outcomes


async def module_scope(recorder, work, runtime, state):
    import yaml

    project = work / "scope-project"
    docs = {"README.md": "# Review gate\n\nThe project review gate needs paired approval.\n",
            "packages/relay/guide.md": "# Review gate\n\nThe relay review gate retries every 17 seconds.\n"}
    runtime.write_project(project, docs)
    catalog_path = project / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    module_path = "packages/relay/guide.md"
    for entry in catalog["documents"]:
        if entry["path"] == module_path:
            entry.update(scope="module", module_path="packages/relay")
    catalog_path.write_text(yaml.safe_dump(catalog, sort_keys=False))
    env = environment(work / "scope-host")
    # Separate supported startup transport: an explicit host environment,
    # not server CWD or a model-provided project_path.
    env["DOCATLAS_PROJECT_ROOT"] = str(project)
    _, storage = prepared_mutation(env, project)
    question = "What does the project review gate need, and how often does the relay review gate retry?"
    async with server(recorder, "module-scope", installed_command() + ["mcp", "docs-serve"],
                      env, work / "unrelated-cwd") as session:
        prepared, _ = await recorder.call(session, "scope-PREPARE", "prepare_docs", {
            "action": "discover_project_docs", "confirm": True})
        assert prepared.get("status") == "success", prepared
        assert prepared["manifest_origin"] == "repository" and prepared["candidate_count"] == 2
        inventory = {"storage_path": str(storage), "generation_id": prepared["metrics"]["generation_id"]}
        save(recorder.out / "scope-SNAPSHOTS.json", state.snapshots(inventory, project, docs))
        before = state.database(storage), state.files(project)
        for label, extra, expected in (
            ("all-default", {}, {"README.md", module_path}),
            ("project-explicit", {"scope": "project"}, {"README.md"}),
            ("module-implied", {"module_path": "packages/relay"}, {module_path}),
            ("module-explicit", {"scope": "module", "module_path": "packages/relay"}, {module_path}),
        ):
            packet, item = await recorder.call(session, "scope-" + label, "get_docs_context", {"question": question, **extra})
            assert not item["isError"], packet
            rows, _, _ = checks.checked_rows(packet, docs, project, module_paths=(module_path,))
            assert {row["path"] for row in rows} == expected, (label, rows)
            for path in expected:
                fact = "paired approval" if path == "README.md" else "every 17 seconds"
                assert any(fact in row["text"] for row in rows if row["path"] == path)
        denied, _ = await recorder.call(session, "scope-missing-module", "get_docs_context", {
            "question": question, "scope": "module", "module_path": "packages/missing"})
        assert not checks.decoded_rows(denied)[0]
        assert (state.database(storage), state.files(project)) == before
    assert (state.database(storage), state.files(project)) == before


async def run(a):
    global REPO
    REPO = a.repo
    import docmancer

    origin = Path(docmancer.__file__).resolve().parent
    assert not origin.is_relative_to(a.repo)
    checked = 0
    for source in sorted((a.repo / "docmancer").rglob("*.py")):
        relative = source.relative_to(a.repo / "docmancer")
        assert (origin / relative).read_bytes() == source.read_bytes(), relative
        checked += 1
    runtime = load("binding_runtime", a.repo / "eval/evidence_quality_v2/runtime.py")
    state = load("binding_state", a.repo / "eval/heuristic_removal/receipts.py")
    runtime.write_project(a.work / "black", checks.source_docs(a.repo))
    env = environment(a.work / "host")
    recorder = Recorder(a.out)
    try:
        command = installed_registration(recorder, a.work, env, state.files)
        black = await original_black(recorder, a.work, env, command, runtime, state)
        await module_scope(recorder, a.work, runtime, state)
        discovery = load("binding_discovery", Path(__file__).with_name("discovery_flow.py"))
        await discovery.run(recorder, a.work, environment, installed_command, server, checks, state)
        expected_counts = {"installer_cli": 5, "server_processes": 5, "initialize": 5,
                           "tools/list": 5, "get_docs_context": 26, "prepare_docs": 7,
                           "resources/read": 4, "docs_status": 1}
        assert dict(recorder.counts) == expected_counts, dict(recorder.counts)
        summary = {"pass": True, "installed_origin": str(origin), "checked_python_files": checked,
                   "counts": dict(recorder.counts), "black_positive_fact_gates": ["B01", "B02", "B05"],
                   "black_frozen_gold": black, "current_project_without_model_path": True,
                   "default_all_explicit_project_and_module_scope_verified": True,
                   "explicit_discovery_and_moved_source_verified": True,
                   "read_only_before_and_after_server_exit": True,
                   "model_path": "unchanged production CPU MiniLM; forward counts not instrumented",
                   "autonomous_opencode_argument_selection": "NOT_TESTED", "paid_model_usage": None}
        save(a.out / "RESULT.json", summary)
        print(json.dumps({key: value for key, value in summary.items() if key != "black_frozen_gold"},
                         ensure_ascii=False), flush=True)
    finally:
        save(a.out / "COUNTS.json", dict(recorder.counts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("repo", "work", "out"):
        parser.add_argument("--" + field, required=True, type=Path)
    a = parser.parse_args()
    for field in ("repo", "work", "out"):
        setattr(a, field, getattr(a, field).resolve())
    assert not a.work.exists() and not a.out.exists(), "Use a fresh fixture and output directory"
    a.work.mkdir(parents=True)
    a.out.mkdir(parents=True)
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
