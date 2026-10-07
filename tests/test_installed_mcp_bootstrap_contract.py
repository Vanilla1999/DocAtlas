"""Fixture-host infrastructure; no answer oracle or live provider changes."""
from contextlib import contextmanager
import asyncio
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from eval.agent_developer_v1 import installed_mcp_benchmark as benchmark
from eval.agent_developer_v1.installed_mcp_contract import ArtifactIdentity, EventLog, ScriptedPlanner, sha256_json
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_tool_data import PUBLIC_ADVERTISED_INPUT_SCHEMAS
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload, create_local_mcp_service


@pytest.fixture
def fixture_host(monkeypatch):
    with benchmark._fixture_workspace("contract-test") as root:
        project = root / "project"
        project.mkdir(mode=0o700)
        home = root / "docatlas-home"
        home.mkdir(mode=0o700)
        (project / "README.md").write_bytes(b"# Fixture\r\n\r\nAuthored documentation.\r\n")
        (project / "docatlas.project-docs.yaml").write_text(json.dumps({
            "schema_version": 1, "documents": [{"path": "README.md", "role": "overview",
            "scope": "project", "description": "Fixture"}], "code_files": []}))
        monkeypatch.setenv("DOCATLAS_HOME", str(home))
        monkeypatch.delenv("DOCATLAS_INDEX_DB_PATH", raising=False)
        monkeypatch.setenv("DOCATLAS_OFFLINE", "1")
        yield project, home


def test_bootstrap_exact_schema_and_authored_byte_hashes(fixture_host):
    project, home = fixture_host
    request = benchmark._fixture_bootstrap(project, home, fixture_author_confirm=True)
    jsonschema.validate(request, PUBLIC_ADVERTISED_INPUT_SCHEMAS["prepare_docs"])
    mutation = request["mutation"]
    assert set(request) == {"action", "project_path", "mutation"}
    assert mutation["confirm"] is True
    assert mutation["expected_generation_id"] is None
    assert mutation["storage_path"] == str(home / "mcp-members" / "members.db")
    assert mutation["catalog_sha256"] == hashlib.sha256((project / "docatlas.project-docs.yaml").read_bytes()).hexdigest()
    entry = read_project_docs_catalog(project).entries[0]
    assert mutation["documents"] == [{"path": "README.md",
        "content_sha256": hashlib.sha256((project / "README.md").read_bytes()).hexdigest(),
        "catalog_entry_hash": catalog_entry_hash(entry)}]
    assert not (home / "mcp-members").exists()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**request, "with_vectors": False}, PUBLIC_ADVERTISED_INPUT_SCHEMAS["prepare_docs"])


@pytest.mark.parametrize("confirm", [False, None, 1, "true"])
def test_producer_denies_without_fixture_author_confirmation(fixture_host, confirm):
    project, home = fixture_host
    with pytest.raises(PermissionError):
        benchmark._fixture_bootstrap(project, home, fixture_author_confirm=confirm)
    assert not (home / "mcp-members").exists()


def test_missing_or_invalid_finite_catalog_denied(fixture_host):
    project, home = fixture_host
    (project / "docatlas.project-docs.yaml").write_text('{"schema_version":1,"roots":[{"path":"."}]}')
    with pytest.raises(ValueError):
        benchmark._fixture_bootstrap(project, home, fixture_author_confirm=True)
    assert not (home / "mcp-members").exists()


def test_cold_service_no_index_before_confirmation_and_real_cas(fixture_host):
    project, home = fixture_host
    service = create_local_mcp_service()
    database = home / "mcp-members" / "members.db"
    assert not database.exists()
    denied = call_docs_tool_payload("prepare_docs", {"action": "sync_project_docs", "project_path": str(project)}, service)
    assert denied.get("status") != "success"
    assert not database.exists()
    request = benchmark._fixture_bootstrap(project, home, fixture_author_confirm=True)
    prepared = call_docs_tool_payload("prepare_docs", request, service)
    assert prepared["status"] == "success", prepared
    generation = prepared["metrics"]["generation_id"]
    assert generation == service.member_storage_policy.generation()
    assert call_docs_tool_payload("prepare_docs", request, service).get("status") != "success"
    request["mutation"]["expected_generation_id"] = generation
    repeat = call_docs_tool_payload("prepare_docs", request, service)
    assert repeat["status"] == "success", repeat
    assert repeat["metrics"]["generation_id"] == generation


def test_private_workspace_ignores_temp_alias_and_rejects_foreign_ancestor(monkeypatch, tmp_path):
    monkeypatch.setenv("TMPDIR", str(tmp_path / "untrusted-alias"))
    with benchmark._fixture_workspace("private-test") as root:
        assert root.parent == Path.home()
        assert root.stat().st_mode & 0o777 == 0o700
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: unsafe))
    with pytest.raises(PermissionError):
        with benchmark._fixture_workspace("denied"):
            pytest.fail("unsafe ancestor accepted")


def test_nested_diagnostic_is_bounded_and_never_persists_secrets_or_paths():
    secret = "Bearer private-provider-token /home/private/project"
    error = ExceptionGroup(secret, [RuntimeError(secret) for _ in range(30)])
    diagnostic = benchmark._exception_diagnostic(error)
    serialized = json.dumps(diagnostic)
    assert secret not in serialized
    assert "private-provider-token" not in serialized
    assert "/home/private" not in serialized
    assert len(diagnostic["exceptions"]) == 16
    assert diagnostic["truncated"] is True
    assert diagnostic["exceptions"][1]["parent"] == 0


def test_infrastructure_failure_preserves_partial_schema_hash_chain_and_no_pass(monkeypatch):
    async def fail(**kwargs):
        events = EventLog()
        events.add("server_start", {"command": "doc-atlas"})
        events.add("mcp_tools_list", {"schema_sha256": "a" * 64})
        kwargs["diagnostics"].update(events=events, mcp_schema_sha256="a" * 64)
        raise ExceptionGroup("outer", [RuntimeError("bootstrap failed")])
    monkeypatch.setattr(benchmark, "_run_task", fail)
    artifact = ArtifactIdentity(origin="reviewed-wheel", distribution="doc-atlas", version="1.3.2",
        artifact_filename="fixture.whl", artifact_sha256="b" * 64, source_commit="c" * 40,
        python_version="3.12", cli_sha256="d" * 64, public_release_verified=False)
    report = asyncio.run(benchmark.run_benchmark_async(planner=ScriptedPlanner({}),
        server_command="unused", artifact=artifact, task_ids={"module_definition_supported"}))
    assert report["passed_tasks"] == 0
    assert report["executed_task_count"] == 0
    assert report["pass_rate"] == 0
    assert report["infrastructure_errors"] == ["module_definition_supported: ExceptionGroup"]
    diagnostic = report["infrastructure_diagnostics"][0]
    assert diagnostic["mcp_schema_sha256"] == "a" * 64
    previous = None
    for event in diagnostic["events"]:
        assert event["previous_event_sha256"] == previous
        assert event["event_sha256"] == sha256_json({k: v for k, v in event.items() if k != "event_sha256"})
        previous = event["event_sha256"]


def test_script_main_infrastructure_exit_two_even_with_zero_threshold(monkeypatch, tmp_path):
    from scripts import run_installed_mcp_agent_benchmark as runner
    @contextmanager
    def installed(**kwargs):
        yield None, "unused"
    monkeypatch.setattr(runner, "installed_artifact", installed)
    monkeypatch.setattr(runner, "run_benchmark", lambda **kwargs: {
        "artifact": {"origin": "reviewed-wheel"}, "provider": {"model": "deterministic-script"},
        "passed_tasks": 0, "task_count": 1, "false_supported": 0,
        "forbidden_source_contamination": 0, "mcp": {"schema_sha256": None},
        "infrastructure_errors": ["module_definition_supported: ExceptionGroup"], "pass_rate": 0})
    assert runner.main(["--wheel", "unused.whl", "--planner", "scripted", "--source-commit", "c" * 40,
        "--min-pass-rate", "0", "--output", str(tmp_path / "fresh.json")]) == 2
