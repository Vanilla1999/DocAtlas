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
        # even after their environment changes. Each executes one genuine read
        # and one public schema rejection (no retrieval for the latter).
        code = """
import json, os, sys
from docmancer.mcp._docs_server_part01 import create_local_mcp_service, call_docs_tool_payload
os.environ['DOCATLAS_TRACE'] = '0' if os.environ.get('DOCATLAS_TRACE') == '1' else '1'
service = create_local_mcp_service()
request = json.loads(sys.argv[1])
result = call_docs_tool_payload('get_docs_context', request, service)
invalid = call_docs_tool_payload('get_docs_context', {**request, 'question': 17}, service)
print(json.dumps({'result': result, 'invalid': invalid}, ensure_ascii=False))
"""
        child_outputs = []
        for startup in (None, "1", "0"):
            env = dict(os.environ)
            env.pop("DOCATLAS_TRACE", None)
            if startup is not None:
                env["DOCATLAS_TRACE"] = startup
            child = subprocess.run([sys.executable, "-c", code, json.dumps(request)], env=env,
                                   text=True, capture_output=True, timeout=60, check=True)
            payload = json.loads(child.stdout)
            assert payload["result"] == off_first
            assert fact in "\n".join(source["snippet"] for source in payload["result"]["sources"])
            assert {source["path_or_url"] for source in payload["result"]["sources"]} == {"docs/store.md"}
            assert all(source["snippet"].strip() in text for source in payload["result"]["sources"])
            assert runner._citation_integrity(payload["result"], snapshot_first)
            assert payload["invalid"]["status"] == "failed"
            assert payload["invalid"]["error"]["reason_code"] == "validation_error"
            assert payload["invalid"]["error"]["where"] == {
                "tool": "get_docs_context", "handler": None, "phase": "validation",
            }
            assert payload["invalid"]["error"]["retryable"] is False
            child_outputs.append(child.stdout)
            events = [json.loads(line) for line in child.stderr.splitlines()
                      if line.startswith('{"event": "docatlas_query_trace"')]
            assert bool(events) is (startup == "1")
            if events:
                assert events[0]["request_id"] and fact not in json.dumps(events)
            records = [json.loads(line) for line in child.stderr.splitlines() if line.startswith("{")]
            records = [record for record in records if record.get("event", "").startswith("docatlas_")]
            if startup != "1":
                assert records == []
            else:
                lifecycle = [record for record in records if record["event"] != "docatlas_query_trace"]
                assert [record["event"] for record in lifecycle] == [
                    "docatlas_request_start", "docatlas_request_end",
                    "docatlas_request_start", "docatlas_request_end",
                ]
                assert all(record["interface"] == "mcp" and
                           record["operation"] == "call_docs_tool_payload" for record in lifecycle)
                read_start, read_end, invalid_start, invalid_end = lifecycle
                assert read_start["request_id"] == read_end["request_id"] == events[0]["request_id"]
                assert invalid_start["request_id"] == invalid_end["request_id"]
                assert read_start["request_id"] != invalid_start["request_id"]
                assert read_start["status"] == invalid_start["status"] == "started"
                assert read_end["status"] == "success" and invalid_end["status"] == "error"
                assert all(record["duration_ms"] >= 0 and record["trace_incomplete"] is False
                           for record in (read_end, invalid_end))
                assert fact not in json.dumps(lifecycle) and str(root) not in json.dumps(lifecycle)
        assert child_outputs[0] == child_outputs[1] == child_outputs[2]

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


def test_frozen_main_flow_questions_deliver_source_bound_facts(tmp_path, record_property):
    """One real preparation and ten public reads, without lookup hints or retries.

    This is the public dispatcher/SQLite boundary, not installed-wheel or client
    acceptance. The existing observer calls the real retrieval and validator;
    expected facts and byte ranges come only from the frozen source documents.
    """
    from contextlib import closing
    import hashlib
    from pathlib import Path

    from eval.evidence_quality_v2.runtime import index_project, isolated_service
    from scripts import run_project_docs_self_host_gate as runner

    artifacts = Path(__file__).resolve().parents[1] / "eval/main_flow_comparison"
    corpus_bytes = (artifacts / "corpus.md").read_bytes()
    question_bytes = (artifacts / "questions.json").read_bytes()
    corpus_hash = "31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00"
    question_hash = "2b88e653b4726747d4ee55682d159744bc1b7dcfc8ac525ee830a688ec401f67"
    assert hashlib.sha256(corpus_bytes).hexdigest() == corpus_hash
    assert hashlib.sha256(question_bytes).hexdigest() == question_hash
    corpus = corpus_bytes.decode("utf-8")
    lines = corpus.splitlines(keepends=True)
    questions = json.loads(question_bytes)
    assert [row["id"] for row in questions] == list(range(1, 11))

    # Authored before execution, independently of retrieval and qualification.
    # Each fact includes its subject/negation where needed; a mention alone is
    # not an answer. Q10's unasked project-policy addendum remains in the frozen
    # expected file but is not required to answer the literal article question.
    facts = {
        1: [(5, 5, "Подробная диагностика по умолчанию выключена."),
            (14, 14, "Глобальные `--trace` / `--no-trace` указываются **перед подкомандой**.")],
        2: [(14, 15, "Глобальные `--trace` / `--no-trace` указываются **перед подкомандой**.\n"
             "Они переопределяют `DOCATLAS_TRACE` на время вызова.")],
        3: [(16, 17, "только `DOCATLAS_TRACE=1` включает трассу; значение\n"
             "окружения читается при загрузке модуля, поэтому задайте его до запуска процесса.")],
        4: [(24, 24, "Диагностика идёт в **stderr**, отдельно от JSON/текстового ответа CLI и MCP stdout.")],
        5: [(29, 31, "`docatlas_request_start` и `docatlas_request_end` связываются через `request_id`.\n"
             "  Поля: `interface`, `operation`, `status`; завершение содержит `duration_ms`\n"
             "  и `trace_incomplete`.")],
        6: [(32, 34, "Покрыты CLI `query`, `context` и публичный диспетчер Docs MCP\n"
             "  (`operation=call_docs_tool_payload`). Ошибки разбора CLI до входа в callback\n"
             "  не имеют lifecycle-событий.")],
        7: [(38, 39, "`success` означает завершение границы вызова, а не достаточность найденных\n"
             "  доказательств."),
            (40, 40, "результат запроса остаётся источником продуктового статуса.")],
        8: [(41, 41, "Ошибка записи диагностики не должна менять ответ."),
            (41, 42, "Пропущенное начало\n  отмечается `trace_incomplete`"),
            (42, 43, "при сбое завершения предпринимается запись\n  `docatlas_trace_gap`."),
            (43, 44, "Полностью недоступный stderr не позволяет доставить\n  даже сообщение о пропуске.")],
        9: [(74, 74, "**Решение проекта:** новые проверки только интеграционного уровня и выше"),
            (80, 80, "Получить эталон из исходных документов и требований, не из выдачи проверяемого кода."),
            (80, 80, "обязательные факты, дословные опорные фрагменты, допустимые источники/hash/span, scope"),
            (83, 83, "Наличие события, внутреннего флага или exit 0 не заменяет проверку результата и состояния.")],
        10: [(69, 69, "**Граница Countdown-Code.** Это исследование обхода награды при доступном "
              "для записи верификаторе, а не сравнение unit- и integration-тестов.")],
    }
    fact_spans = {}
    for question_id, required in facts.items():
        fact_spans[question_id] = []
        for first, last, quote in required:
            window = "".join(lines[first - 1:last])
            assert window.count(quote) == 1, (question_id, quote)
            start = sum(map(len, lines[:first - 1])) + window.index(quote)
            fact_spans[question_id].append((start, start + len(quote), quote))

    root = (tmp_path / "project").resolve()
    root.mkdir(mode=0o700)
    (root / "README.md").write_bytes(corpus_bytes)
    catalog = root / "docatlas.project-docs.yaml"
    catalog.write_text(json.dumps({"schema_version": 1, "code_files": [], "documents": [{
        "path": "README.md", "role": "overview", "scope": "project",
        "description": "DocAtlas main-flow logging and evaluation documentation",
        "authority": "source_of_truth",
    }]}), encoding="utf-8")
    catalog_bytes = catalog.read_bytes()
    project_identity = "local:" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    reports = []
    raw_results = []
    report_path = tmp_path / "main-flow-proof.json"

    def save_report():
        report_path.write_text(json.dumps({
            "boundary": "public MCP dispatcher with real SQLite and same-call validation snapshots",
            "corpus_sha256": corpus_hash, "questions_sha256": question_hash,
            "product_calls": {"prepare_docs": 1, "get_docs_context": len(raw_results)},
            "summary": reports, "results": raw_results,
        }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    with isolated_service(tmp_path / "state") as (service, config):
        prepared = index_project(service, config, root)
        generation = prepared["generation_id"]
        policy = service._cold.member_storage_policy
        with closing(policy.connect()) as connection:
            stored = connection.execute(
                "SELECT source, content, content_hash, source_identity FROM generation_sources WHERE generation_id = ?",
                (generation,),
            ).fetchall()
        assert [tuple(row)[:3] for row in stored] == [(str(root / "README.md"), corpus, corpus_hash)]

        for question in questions:
            request = {"question": question["question"], "project_path": str(root), "scope": "project"}
            try:
                payload, snapshot = runner._call_with_snapshot(request, service)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                raw_results.append({"id": question["id"], "request": request, "execution_error": error})
                reports.append({"id": question["id"], "errors": [error], "missing_facts": [
                    quote for _start, _end, quote in fact_spans[question["id"]]
                ]})
                save_report()
                continue
            raw_results.append({"id": question["id"], "request": request,
                                "payload": payload, "validation_snapshot": snapshot})
            save_report()
            if not isinstance(payload, dict):
                reports.append({"id": question["id"], "errors": ["no structured payload"],
                                "missing_facts": [quote for _start, _end, quote in fact_spans[question["id"]]]})
                save_report()
                continue
            sources = payload.get("sources") or []
            errors = []
            visible_spans = []
            if not (payload.get("kind") == "docs_context" and payload.get("context_available")
                    and payload.get("support_status") == "retrieval_only"
                    and payload.get("answer_supported") is False
                    and payload.get("answer_available") is False and payload.get("edit_ready") is False):
                errors.append("read-context delivery contract")
            for source in sources:
                bound = snapshot.get(source.get("evidence_id")) or {}
                if (bound.get("projected_source") != source
                        or source.get("path_or_url") != "README.md"
                        or source.get("project_identity") != project_identity
                        or source.get("scope") != "project"
                        or source.get("authority") != "source_of_truth"
                        or source.get("version_binding") != "unversioned"):
                    errors.append("source identity/snapshot/scope/version")
                    continue
                raw = bound.get("source") or {}
                reference = raw.get("_reference_evidence") or {}
                identity = reference.get("source") or {}
                scope = identity.get("scope") or {}
                if (reference.get("raw_document") != corpus
                        or identity.get("canonical_path") != "README.md"
                        or identity.get("content_sha256") != corpus_hash
                        or identity.get("document_id") != stored[0]["source_identity"]
                        or scope.get("project_id") != project_identity
                        or scope.get("snapshot_id") != generation or scope.get("version") != ""):
                    errors.append("raw document/source lineage")
                    continue
                ref_start, ref_end = reference.get("char_start"), reference.get("char_end")
                reference_text = reference.get("text")
                if not (type(ref_start) is int and type(ref_end) is int
                        and 0 <= ref_start < ref_end <= len(corpus)
                        and reference_text == corpus[ref_start:ref_end]):
                    errors.append("raw reference character span")
                    continue
                first, last = source.get("line_start"), source.get("line_end")
                snippet = source.get("snippet", "").strip()
                if not (type(first) is int and type(last) is int and 1 <= first <= last <= len(lines)):
                    errors.append("invalid line span")
                    continue
                if not snippet or reference_text.count(snippet) != 1:
                    errors.append("nonverbatim or ambiguous referenced snippet")
                    continue
                start = ref_start + reference_text.index(snippet)
                end = start + len(snippet)
                if not (sum(map(len, lines[:first - 1])) <= start
                        and end <= sum(map(len, lines[:last]))):
                    errors.append("declared lines exclude referenced occurrence")
                    continue
                # Public source hashes bind this canonical envelope, not just
                # the display snippet. Do not call the production digest helper.
                material = {
                    "path": raw.get("path") or raw.get("source") or raw.get("url") or raw.get("source_url"),
                    "section": raw.get("heading_path") or raw.get("title"),
                    "content": raw.get("content") or raw.get("display_text"),
                    "snippet": raw.get("snippet") or raw.get("code"),
                    "version": raw.get("version_binding") or raw.get("version") or raw.get("requested_version"),
                }
                digest = hashlib.sha256(json.dumps(
                    material, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")).hexdigest()
                if source.get("content_sha256") != digest:
                    errors.append("source digest")
                    continue
                visible_spans.append((start, end))

            # Adjacent genuine excerpts may jointly cover a fact. Credit only
            # emitted characters; no missing paragraph/negation gets parent credit.
            merged = []
            for start, end in sorted(visible_spans):
                if merged and (start <= merged[-1][1] or not corpus[merged[-1][1]:start].strip()):
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            missing = [quote for start, end, quote in fact_spans[question["id"]]
                       if not any(left <= start and right >= end for left, right in merged)]
            reports.append({"id": question["id"], "status": payload.get("status"),
                            "source_count": len(sources), "errors": errors, "missing_facts": missing})
            save_report()

        assert policy.generation() == generation
        with closing(policy.connect()) as connection:
            unchanged = connection.execute(
                "SELECT source, content, content_hash, source_identity FROM generation_sources WHERE generation_id = ?",
                (generation,),
            ).fetchall()
        assert [tuple(row) for row in unchanged] == [tuple(row) for row in stored]
    assert (root / "README.md").read_bytes() == corpus_bytes
    assert catalog.read_bytes() == catalog_bytes
    assert (artifacts / "corpus.md").read_bytes() == corpus_bytes
    assert (artifacts / "questions.json").read_bytes() == question_bytes
    record_property("main_flow_calls", "1 prepare_docs + 10 get_docs_context; no retries or lookups")
    record_property("main_flow_results", json.dumps(reports, ensure_ascii=False))
    failures = [row for row in reports if row["errors"] or row["missing_facts"]]
    print(f"Main-flow factual delivery: {10 - len(failures)}/10; failed IDs: {[row['id'] for row in failures]}")
    assert len(raw_results) == len(reports) == 10
    assert not failures, {"failures": failures, "raw_evidence": str(report_path)}
