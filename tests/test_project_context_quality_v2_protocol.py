import json

import pytest

from eval import project_context_quality_v2_protocol as protocol








































def test_query_trace_off_on_off_preserves_real_sources_and_retrieval_calls(tmp_path, monkeypatch, capsys):
    from dataclasses import asdict, is_dataclass
    from copy import deepcopy
    from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
    from scripts import run_project_docs_self_host_gate as runner
    from docmancer.retrieval.dispatch import RetrievalDispatcher
    from docmancer.docs.application.query_trace import query_trace
    from docmancer.mcp.docs_server import call_docs_tool_payload
    import json
    import os
    import subprocess
    import sys

    root = tmp_path / "project"
    fact = "DocAtlas stores fixture records for local inspection."
    text = "# Fixture store\n\n" + fact + "\n"
    write_project(root, {"docs/store.md": text})
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        request = {"question": fact, "project_path": str(root), "scope": "project"}
        app = service.unified_context
        retrieve = app.get_docs_context
        raw_calls = []
        calls = {"coverage": 0, "acquisition": 0}
        coverage = runner.docs_context_projection.component_coverage_decision
        dispatch = RetrievalDispatcher.run

        def observe_coverage(*args, **kwargs):
            calls["coverage"] += 1
            return coverage(*args, **kwargs)

        def observe_acquisition(self, *args, **kwargs):
            calls["acquisition"] += 1
            return dispatch(self, *args, **kwargs)

        def observe_real_retrieval(*args, **kwargs):
            result = retrieve(*args, **kwargs)
            raw_calls.append(deepcopy(asdict(result) if is_dataclass(result) else result))
            return result

        monkeypatch.setattr(app, "get_docs_context", observe_real_retrieval)
        monkeypatch.setattr(runner, "REPO_ROOT", root)
        monkeypatch.setattr(runner.docs_context_projection, "component_coverage_decision", observe_coverage)
        monkeypatch.setattr(RetrievalDispatcher, "run", observe_acquisition)
        capsys.readouterr()
        off_first, snapshot_first = runner._call_with_snapshot(request, service, trace_enabled=False)
        assert len(raw_calls) == 1
        first_calls = dict(calls)
        assert first_calls["coverage"] > 0 and first_calls["acquisition"] > 0
        on, snapshot_on = runner._call_with_snapshot(request, service, trace_enabled=True)
        assert len(raw_calls) == 2
        assert calls == {key: count * 2 for key, count in first_calls.items()}
        off_last, snapshot_last = runner._call_with_snapshot(request, service, trace_enabled=False)
        assert len(raw_calls) == 3
        assert calls == {key: count * 3 for key, count in first_calls.items()}
        assert off_first == off_last == {key: value for key, value in on.items() if key != "diagnostics"}
        assert snapshot_first == snapshot_on == snapshot_last
        assert "diagnostics" not in off_first and "diagnostics" not in off_last
        assert fact in "\n".join(source["snippet"] for source in on["sources"])
        assert runner._citation_integrity(on, snapshot_on)
        assert on["diagnostics"]["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
        trace = on["diagnostics"]["projection_observation"]["returned_core_diagnostics"]["decision_trace"]
        assert trace["events"]["recorded_count"] > 0
        for raw in (raw_calls[0], raw_calls[2]):
            assert "same_call_pipeline" not in raw.get("ingestion_diagnostics", {}).get("project", {})
        assert capsys.readouterr().out == ""
        assert (root / "docs/store.md").read_text() == text
        assert not hasattr(service, "_same_call_diagnostics_observer")

        # Three new processes read the same committed fixture: startup OFF/ON/OFF,
        # even after their environment changes. Each executes one public call.
        code = """
import json, os, sys
from docmancer.docs.application.query_trace import query_trace_enabled
from docmancer.mcp._docs_server_part01 import create_local_mcp_service, call_docs_tool_payload
os.environ['DOCATLAS_TRACE'] = '0' if os.environ.get('DOCATLAS_TRACE') == '1' else '1'
result = call_docs_tool_payload('get_docs_context', json.loads(sys.argv[1]), create_local_mcp_service())
print(json.dumps(result, ensure_ascii=False))
"""
        for startup in (None, "1", "0"):
            env = dict(os.environ)
            env.pop("DOCATLAS_TRACE", None)
            if startup is not None:
                env["DOCATLAS_TRACE"] = startup
            child = subprocess.run([sys.executable, "-c", code, json.dumps(request)], env=env,
                                   text=True, capture_output=True, timeout=60, check=True)
            assert json.loads(child.stdout) == off_first
            events = [json.loads(line) for line in child.stderr.splitlines()
                      if line.startswith('{"event": "docatlas_query_trace"')]
            assert bool(events) is (startup == "1")
            if events:
                assert events[0]["request_id"] and fact not in json.dumps(events)

        # Diagnostic-only failures must not change the genuine public operation.
        def broken_observer(value):
            raise RuntimeError("diagnostic-only observer failure")

        class BrokenWriter:
            def write(self, value):
                raise OSError("diagnostic-only sink failure")

        with query_trace(True):
            with monkeypatch.context() as scope:
                scope.setattr(service, "_same_call_diagnostics_observer", broken_observer, raising=False)
                assert call_docs_tool_payload("get_docs_context", request, service) == off_first
            with monkeypatch.context() as scope:
                scope.setattr(runner.context_tools.sys, "stderr", BrokenWriter())
                assert call_docs_tool_payload("get_docs_context", request, service) == off_first
        assert len(raw_calls) == 5
        assert calls == {key: count * 5 for key, count in first_calls.items()}
        assert (root / "docs/store.md").read_text() == text


@pytest.mark.parametrize("question,has_candidates", [
    ("Как DocAtlas отправляет сообщения через квантовый канал?", True),
    ("zzxqv_missing_fixture_topic_73291", False),
])
def test_delivery_veto_observer_distinguishes_rejected_candidates_from_empty_acquisition(
    tmp_path, question, has_candidates,
):
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
    from scripts import run_project_docs_self_host_gate as runner

    root = tmp_path / "project"
    text = "# Fixture store\n\nDocAtlas stores fixture records for local inspection.\n"
    write_project(root, {"docs/store.md": text})
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        request = {"question": question, "project_path": str(root), "scope": "project"}
        plain = call_docs_tool_payload("get_docs_context", request, service)
        observed, snapshot = runner._call_with_snapshot(request, service)
        assert {key: value for key, value in observed.items() if key != "diagnostics"} == plain
        assert plain["status"] == "insufficient_evidence" and not plain.get("sources")
        assert not plain.get("context_available") and not plain.get("answer_supported")
        assert not plain.get("answer_available") and not plain.get("edit_ready")
        assert snapshot == {} and "diagnostics" not in plain
        diagnostics = observed["diagnostics"]
        assert diagnostics["observer_counts"] == {"retrieval_calls": 1, "validation_calls": 1}
        assert diagnostics["stage_status"]["retrieval"] == "observed"
        assert diagnostics["stage_status"]["qualification"] == "observed"
        assert diagnostics["stage_status"]["delivery"] == "blocked_before_projection"
        assert all(diagnostics["stage_status"][stage] == "not_reached"
                   for stage in ("ranking", "projection", "coverage"))
        assert bool(diagnostics["retrieved_candidate_ids"]) is has_candidates
        assert diagnostics["delivery_decision"]["deliverable"] is False
        assert not diagnostics.get("pre_projection_qualified_ids")
        assert not hasattr(service, "_same_call_diagnostics_observer")
        assert (root / "docs/store.md").read_text() == text
        # Observers are optional diagnostics; a broken callback cannot change
        # the already validated result or convert the veto into a successful read.
        def broken_observer(value):
            raise RuntimeError("observer-only failure")
        service._same_call_diagnostics_observer = broken_observer
        try:
            assert call_docs_tool_payload("get_docs_context", request, service) == plain
        finally:
            del service._same_call_diagnostics_observer



