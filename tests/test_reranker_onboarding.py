"""Public CLI/stdio onboarding on isolated data, without a model or GPU.

Run with the candidate wheel installed in the test interpreter. Children use
``-I`` outside the checkout; no product helper, scorer, hash check or storage is
mocked. The only substituted boundary is an HTTP CONNECT proxy that refuses or
pauses external downloads. This does not qualify successful Hugging Face/CDN
downloads, inference, a fresh uv install, or SIGKILL recovery.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest


@contextmanager
def refusing_proxy():
    """Replace external transport only; never return synthetic model assets."""
    seen = threading.Event()
    release = threading.Event()
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_CONNECT(self):
            requests.append(self.path)
            seen.set()
            if self.server.pause:
                release.wait(20)
                # The interrupt scenario deliberately closes the client socket.
                return
            self.send_error(502, "Offline onboarding transport fixture")

        def do_GET(self):
            requests.append(self.path)
            self.send_error(502, "Offline onboarding transport fixture")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.pause = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, seen, release, requests
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def cli_host(tmp_path, request):
    root = tmp_path.resolve()
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
           if key in os.environ}
    for key, name in {"HOME": "home", "USERPROFILE": "home", "DOCATLAS_HOME": "app",
                      "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data",
                      "XDG_CACHE_HOME": "cache"}.items():
        path = root / name
        path.mkdir(mode=0o700, exist_ok=True)
        env[key] = str(path)
    env.update({"DOCATLAS_AUTO_VECTORS": "0", "DOCATLAS_OFFLINE": "1",
                "DOCATLAS_REGISTRY_API_URL": "http://127.0.0.1:1"})
    if os.environ.get("TIKTOKEN_CACHE_DIR"):
        env["TIKTOKEN_CACHE_DIR"] = os.environ["TIKTOKEN_CACHE_DIR"]
    calls = []
    command = [sys.executable, "-I", "-m", "docmancer.cli"]
    with refusing_proxy() as proxy:
        server, _seen, _release, _requests = proxy
        endpoint = f"http://127.0.0.1:{server.server_port}"
        env.update({"http_proxy": endpoint, "https_proxy": endpoint,
                    "HTTP_PROXY": endpoint, "HTTPS_PROXY": endpoint,
                    "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})

        def run(*args, extra_env=None):
            started = time.monotonic()
            receipt = {"command": list(args)}
            calls.append(receipt)
            try:
                result = subprocess.run(command + list(args), cwd=root,
                                        env={**env, **(extra_env or {})}, capture_output=True,
                                        text=True, timeout=45, stdin=subprocess.DEVNULL)
                receipt["returncode"] = result.returncode
            finally:
                receipt["seconds"] = round(time.monotonic() - started, 3)
            assert "Traceback (most recent call last)" not in result.stderr, result.stderr
            return result

        yield root, env, command, run, proxy, calls
    print(json.dumps({"scenario": request.node.name, "cli_calls": len(calls), "calls": calls}))


def test_public_readiness_and_doctor_explain_optional_profile(cli_host):
    root, env, command, run, proxy, calls = cli_host
    report = run("reranker", "check", "--json")
    assert report.returncode == 1, report.stdout
    missing = json.loads(report.stdout)
    assert missing["assets"]["error"] == "evidence_model_path_not_set"
    assert missing["ready"] is False and missing["assets_ready"] is False
    assert missing["enabled"] is False and missing["profile_valid"] is True
    assert missing["inference_checked"] is False
    assert missing["environment_scope"] == "current_process"

    default_doctor = run("doctor", "--check", "reranker", "--json")
    assert default_doctor.returncode == 0, default_doctor.stderr
    assert json.loads(default_doctor.stdout)["issues"] == []

    configured = {"DOCATLAS_EXPERIMENT_PAIRED_QWEN": "1",
                  "DOCATLAS_EXPERIMENT_QWEN_STUDY": "1",
                  "DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE": "unsupported"}
    invalid = run("reranker", "check", "--json", extra_env=configured)
    invalid_report = json.loads(invalid.stdout)
    assert invalid.returncode == 1 and invalid_report["profile_valid"] is False
    assert "qwen_study_requires_explicit_control_no_stop_no_redundancy_or_relative" in invalid_report["profile"]["error"]
    assert any(issue["component"] == "profile" and issue["action"]
               for issue in invalid_report["issues"]), invalid_report

    doctor = run("doctor", "--check", "reranker", "--json", extra_env=configured)
    issues = json.loads(doctor.stdout)["issues"]
    assert any(issue["severity"] == "BLOCKER" and issue["code"] == "RERANKER_NOT_READY"
               for issue in issues), issues

    configured["DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE"] = "no_redundancy"
    valid = run("reranker", "check", "--json", extra_env=configured)
    valid_report = json.loads(valid.stdout)
    assert valid.returncode == 1 and valid_report["enabled"] is True
    assert valid_report["profile_valid"] is True and valid_report["ready"] is False
    assert valid_report["profile"]["native_budget"] == 12000
    assert valid_report["inference_checked"] is False

    # An existing but unprepared directory is real input, not mocked model assets.
    # Its path alone must not silently activate MiniLM instead of requested Qwen.
    unprepared = root / "unprepared-assets"
    unprepared.mkdir()
    inherited_compression = {
        **configured, "DOCATLAS_MINILM_MODEL_DIR": str(unprepared),
    }
    implicit = run("reranker", "check", "--json", extra_env=inherited_compression)
    implicit_report = json.loads(implicit.stdout)
    assert implicit.returncode == 1 and implicit_report["profile_valid"] is False
    assert implicit_report["profile"]["error"] == "paired_qwen_requires_compression_off"

    explicit_off = run("reranker", "check", "--json", extra_env={
        **inherited_compression, "DOCATLAS_CONTEXT_COMPRESSION": "off",
    })
    off_report = json.loads(explicit_off.stdout)
    assert explicit_off.returncode == 1 and off_report["profile_valid"] is True
    assert off_report["enabled"] is True and off_report["ready"] is False

    conflict = run("reranker", "check", "--json", extra_env={
        **configured, "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "1",
    })
    conflict_report = json.loads(conflict.stdout)
    assert conflict.returncode == 1 and conflict_report["profile_valid"] is False
    assert conflict_report["assets_ready"] is False and conflict_report["ready"] is False
    assert "paired_qwen_requires_default_native_acquisition_not_minimal_complete_scope" in conflict_report["profile"]["error"]

    configured["DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS"] = "0"
    budget = run("reranker", "check", "--json", extra_env=configured)
    budget_report = json.loads(budget.stdout)
    assert budget.returncode == 1 and budget_report["profile_valid"] is False
    assert "DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS" in budget_report["profile"]["error"]
    assert proxy[3] == [], "Readiness must not initiate model downloads"


def test_public_prepare_refuses_unsafe_destinations_without_writes(cli_host):
    root, env, command, run, proxy, calls = cli_host
    relative = run("reranker", "prepare", "relative-model")
    assert relative.returncode == 1
    assert "reranker_prepare_requires_absolute_out" in relative.stderr
    assert not (root / "relative-model").exists()

    occupied = root / "user-models"
    occupied.mkdir()
    marker = occupied / "keep.txt"
    marker.write_bytes(b"User data must survive rejected preparation.\n")
    before = marker.read_bytes()
    rejected = run("reranker", "prepare", str(occupied))
    assert rejected.returncode == 1
    assert "reranker_prepare_requires_empty_directory" in rejected.stderr
    assert marker.read_bytes() == before and list(occupied.iterdir()) == [marker]

    linked = root / "model-link"
    target = root / "empty-user-directory"
    target.mkdir()
    linked.symlink_to(target, target_is_directory=True)
    symlink = run("reranker", "prepare", str(linked))
    assert symlink.returncode == 1
    assert "reranker_prepare_symlink_destination" in symlink.stderr
    assert linked.is_symlink() and target.is_dir() and list(target.iterdir()) == []
    assert proxy[3] == [], "Destination guards must run before external transport"


def test_public_prepare_transport_failure_keeps_original_empty_directory(cli_host):
    root, env, command, run, proxy, calls = cli_host
    destination = root / "prepared-model"
    destination.mkdir()
    inode = destination.stat().st_ino
    siblings = set(root.iterdir())
    failed = run("reranker", "prepare", str(destination))
    assert failed.returncode == 1 and "502" in failed.stderr, failed
    assert proxy[3] and set(proxy[3]) == {"huggingface.co:443"}
    assert destination.is_dir() and destination.stat().st_ino == inode
    assert list(destination.iterdir()) == []
    assert set(root.iterdir()) == siblings, "Failed prepare left staging data behind"


def test_public_prepare_interrupt_cleans_only_its_own_staging(cli_host):
    root, env, command, run, proxy, calls = cli_host
    server, seen, release, requests = proxy
    server.pause = True
    destination = root / "new-model"
    siblings = set(root.iterdir())
    process = subprocess.Popen(command + ["reranker", "prepare", str(destination)],
                               cwd=root, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    receipt = {"command": ["reranker", "prepare", str(destination)], "interrupted": True}
    calls.append(receipt)
    try:
        assert seen.wait(15), "Prepare never reached the external transport boundary"
        # A different actor creates user-owned data while the request is in flight.
        destination.mkdir(exist_ok=True)
        marker = destination / "keep.txt"
        marker.write_bytes(b"Created independently during model preparation.\n")
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=15)
        receipt["returncode"] = process.returncode
        assert process.returncode != 0, (stdout, stderr)
        assert marker.read_bytes() == b"Created independently during model preparation.\n"
        assert list(destination.iterdir()) == [marker]
        assert set(root.iterdir()) == siblings | {destination}
        assert requests == ["huggingface.co:443"]
    finally:
        release.set()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_default_installed_mcp_preserves_source_and_confirmation(cli_host):
    root, env, command, run, proxy, calls = cli_host
    project = root / "project"
    project.mkdir()
    document = ("# AtlasCache operations\n\n"
                "The AtlasCache TTL is 45 seconds. Refresh only after an explicit "
                "operator confirmation.\n")
    source = project / "README.md"
    source.write_text(document, encoding="utf-8")
    entry = {"path": "README.md", "role": "runbook", "scope": "project",
             "description": "AtlasCache TTL and refresh requirements", "module_path": None,
             "authority": "source_of_truth", "status": "active", "impact": "track"}
    catalog = project / "docatlas.project-docs.yaml"
    catalog.write_text(json.dumps({"schema_version": 1, "code_files": [],
                                   "documents": [entry]}), encoding="utf-8")
    for args in (("init", "-q"), ("add", "."),
                 ("-c", "user.email=fixture@example.test", "-c", "user.name=Onboarding fixture",
                  "commit", "-qm", "Accepted fixture documentation")):
        subprocess.run(["git", "-C", str(project), *args], check=True,
                       capture_output=True, timeout=15)
    tool_calls = []
    question = {"question": "How long is AtlasCache cached and when may it be refreshed?",
                "project_path": str(project)}

    async def scenario():
        params = StdioServerParameters(command=command[0], args=command[1:] + ["mcp", "docs-serve"],
                                       env=env, cwd=str(root))
        with (root / "mcp-stderr.log").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()

                    async def invoke(name, arguments):
                        tool_calls.append(name)
                        result = await session.call_tool(name, arguments)
                        if result.structuredContent is not None:
                            return result.structuredContent
                        return json.loads("".join(row.text for row in result.content if row.type == "text"))

                    cold = await invoke("get_docs_context", question)
                    assert cold["status"] == "not_prepared", cold
                    assert cold["recommended_next_action"]["requires_confirmation"] is True
                    database = Path(cold["storage_path"])
                    assert not database.exists()
                    refused = await invoke("prepare_docs", {"action": "sync_project_docs",
                                                            "project_path": str(project)})
                    assert refused.get("status") != "success" and not database.exists(), refused
                    # The fixture author approves exactly its own catalogued document.
                    # Hashes bind authored input, not expected retrieval output.
                    mutation = {"operation": "sync_project_docs", "confirm": True,
                                "storage_path": str(database), "expected_generation_id": None,
                                "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
                                "documents": [{"path": "README.md",
                                  "content_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                  "catalog_entry_hash": "sha256:" + hashlib.sha256(json.dumps(
                                      entry, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()}]}
                    prepared = await invoke("prepare_docs", {"action": "sync_project_docs",
                                           "project_path": str(project), "mutation": mutation})
                    assert prepared["status"] == "success" and database.is_file(), prepared
                    answer = await invoke("get_docs_context", question)
                    assert answer["kind"] == "docs_context" and answer["status"] in {"ok", "truncated"}, answer
                    rows = answer["sources"]
                    assert rows and any("The AtlasCache TTL is 45 seconds." in row["snippet"]
                                        and "Refresh only after an explicit operator confirmation." in row["snippet"]
                                        for row in rows), answer
                    for row in rows:
                        assert row["path_or_url"] == "README.md", row
                        assert row["scope"] == "project" and row["authority"] == "source_of_truth"
                        assert row["version_binding"] == "unversioned"
                        assert row["evidence_id"].startswith("ev-")
                        start, end = row["line_start"], row["line_end"]
                        assert 1 <= start <= end <= len(document.splitlines())
                        assert row["snippet"] in "".join(document.splitlines(keepends=True)[start - 1:end])
                    assert not answer.get("edit_ready")

        # Reuse the genuinely prepared store but restart the actual MCP server
        # with an inherited MiniLM trigger. It must not silently route Qwen to
        # MiniLM; an empty directory is sufficient to exercise the config guard.
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        unprepared = root / "unprepared-minilm"
        unprepared.mkdir()
        conflict_env = {**env, "DOCATLAS_EXPERIMENT_PAIRED_QWEN": "1",
                        "DOCATLAS_EXPERIMENT_QWEN_STUDY": "1",
                        "DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE": "no_redundancy",
                        "DOCATLAS_MINILM_MODEL_DIR": str(unprepared)}
        params = StdioServerParameters(command=command[0], args=command[1:] + ["mcp", "docs-serve"],
                                       env=conflict_env, cwd=str(root))
        with (root / "mcp-conflict-stderr.log").open("w") as stderr:
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    tool_calls.append("get_docs_context")
                    result = await session.call_tool("get_docs_context", question)
                    conflict = result.structuredContent
                    if conflict is None:
                        conflict = json.loads("".join(row.text for row in result.content if row.type == "text"))
                    assert conflict["status"] == "failed", conflict
                    assert conflict["error"]["reason_code"] == "paired_qwen_requires_compression_off", conflict
                    assert any("DOCATLAS_CONTEXT_COMPRESSION=off" in hint
                               for hint in conflict["error"]["hints"]), conflict
                    assert not conflict.get("sources"), conflict
                    print(json.dumps({"conflict_reason": conflict["error"]["reason_code"],
                                      "conflict_hints": conflict["error"]["hints"]}))
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before

    try:
        asyncio.run(scenario())
    finally:
        print(json.dumps({"mcp_tool_calls": len(tool_calls), "tools": tool_calls}))
    assert source.read_text(encoding="utf-8") == document
    assert proxy[3] == [], "Default documentation retrieval must not download a model"
    assert tool_calls == ["get_docs_context", "prepare_docs", "prepare_docs", "get_docs_context",
                          "get_docs_context"]
    print(json.dumps({"required_facts": 2, "delivered_facts": 2}))
