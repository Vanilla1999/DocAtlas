from eval.project_context_quality_protocol import run_contract

import hashlib
import json
from unittest.mock import patch

import pytest

from eval import project_context_quality_protocol as protocol


def test_legacy_bytes_and_thresholds_are_frozen():
    assert protocol.CASES_PATH.read_bytes() == protocol.CASES_PATH.with_name("cases.legacy.json").read_bytes()
    assert hashlib.sha256(protocol.CASES_PATH.read_bytes()).hexdigest() == "b77ae44e8fb41bc53a6aa6cf584d886ee884ba337302285e4de9af2e4a5d829a"
    assert json.loads(protocol.LOCK_PATH.read_text())["thresholds"] == {
        "contract_pass_rate_min": 1.0, "false_public_tools_max": 0,
        "live_useful_result_min": 13, "live_top1_fact_bearing_min": 12,
        "live_top3_relevant_min": 15, "original_query_coverage_min": 12,
    }


@pytest.mark.parametrize("lane,positives,negatives", [("natural", 15, 2), ("paraphrases", 5, 1)])
def test_frozen_inventory_and_independent_components(lane, positives, negatives):
    rows = protocol.load_cases(lane)
    assert len(rows) == positives + negatives
    assert sum(row["expected_kind"] == "docs_context" for row in rows) == positives
    assert len({row["id"] for row in rows}) == len(rows)
    for row in rows[:positives]:
        assert len(row["required_fact_groups"]) >= 2
        assert len(row["required_fact_groups"]) == len(row["fact_groups"])
        assert 0 < row["minimum_lookup_coverage"] <= len(row["lookup_queries"]) <= 5
        assert "query-original" in row["expected_public_query_ids"]
        assert all(f"query-lookup-{i}" in row["expected_public_query_ids"] for i in range(1, len(row["lookup_queries"]) + 1))
    assert protocol.run_contract(lane)["verdict"] == "PASS"


def test_scope_inventory():
    rows = protocol.load_cases("natural")
    assert {row["id"] for row in rows if row["scope"] == "all"} == {
        "natural-architecture", "natural-request-flow", "natural-evidence-selection",
    }
    assert all(row["scope"] in {"project", "all"} for row in rows)


def test_exact_original_five_questions_and_fact_components():
    originals = {
        "natural-purpose-start": ("Что это за проект и какую проблему он решает?", "project", {"product", "purpose"}),
        "natural-architecture": ("Как устроена архитектура проекта и где проходят основные границы модулей?", "all", {"application", "domain", "mcp_boundary", "infrastructure_boundary"}),
        "natural-request-flow": ("Как проходит запрос get_docs_context от MCP-входа до выбора источников?", "all", {"flow_mcp", "flow_application", "flow_gateway", "flow_selection"}),
        "natural-docs-server": ("Какие публичные инструменты предоставляет Docs MCP?", "project", {"tool_context", "tool_prepare", "tool_status"}),
        "natural-evidence-selection": ("Как система выбирает доказательства?", "all", {"selection_domain", "selection_application", "selection_proof", "project_context"}),
    }
    rows = {row["id"]: row for row in protocol.load_cases("natural")}
    assert {row["id"] for row in rows.values() if row.get("provenance") == "original_user_verbatim"} == set(originals)
    for case_id, (question, scope, groups) in originals.items():
        case = rows[case_id]
        assert case["question"] == question
        assert case["scope"] == scope
        assert case["provenance"] == "original_user_verbatim"
        assert set(case["fact_groups"]) == groups
    for name, identifier in (("tool_context", "get_docs_context"), ("tool_prepare", "prepare_docs"), ("tool_status", "docs_status")):
        case = rows["natural-docs-server"]
        alternatives = case["required_fact_groups"][case["fact_groups"].index(name)]
        assert all(identifier in text and len(text.split()) > 8 for _, text in alternatives)
    assert sum(row["expected_kind"] == "docs_context" and row["id"] not in originals for row in rows.values()) == 10


@pytest.mark.parametrize("lane", ["legacy", "natural", "paraphrases"])
def test_contract_labels_and_executes_planning_not_retrieval(lane):
    with patch.object(protocol, "build_documentation_query_plan", wraps=protocol.build_documentation_query_plan) as planner:
        report = protocol.run_contract(lane)
    assert planner.call_count == report["case_count"] * (2 if lane == "legacy" else 1)
    assert report["evaluation_kind"] == ("alias_and_query_plan_contract" if lane == "legacy" else "query_plan_public_inventory_contract")
    assert report["retrieval_executed"] is False


def test_fact_alternatives_are_active_document_text():
    import yaml

    catalog = yaml.safe_load((protocol.ROOT / "docatlas.project-docs.yaml").read_text())
    inactive = {row["path"] for row in catalog["documents"] if row.get("status") != "active"}
    alternatives = []
    for lane in ("natural", "paraphrases"):
        for case in protocol.load_cases(lane):
            assert not inactive.intersection(case.get("allowed_paths") or case["sources"])
            for group in case["required_fact_groups"]:
                alternatives.append(len(group))
                for path, text in group:
                    assert path not in inactive
                    assert text.casefold() in (protocol.ROOT / path).read_text().casefold(), (path, text)
    assert max(alternatives) > 1
    legacy = next(case for case in protocol.load_cases() if case["id"] == "ru-troubleshoot")
    assert "docs/adr/0002-context-retrieval-vs-answer-proof.md" in legacy["allowed_paths"]


@pytest.mark.parametrize("lane,question_only,report_only", [
    ("natural", False, False), ("natural", True, True), ("paraphrases", False, True),
])
def test_live_scope_stable_ids_and_report_only_isolation(lane, question_only, report_only):
    from scripts import run_project_docs_self_host_gate as gate

    with patch.object(gate, "run", return_value={"verdict": "FAIL", "errors": ["sentinel"], "results": []}) as run:
        report = protocol.run_live(lane, question_only=question_only)
    cases = run.call_args.kwargs["cases"]
    negatives = run.call_args.kwargs["negative_cases"]
    rows = protocol.load_cases(lane)
    assert [case.case_id for case in (*cases, *negatives)] == [row["id"] for row in rows]
    assert [case.scope for case in (*cases, *negatives)] == [row["scope"] for row in rows]
    assert all(case.required_fact_groups for case in cases)
    assert report["report_only"] is report_only
    assert report["verdict"] == "FAIL"
    assert report["errors"] == ["sentinel"]
    if question_only:
        assert all(not case.lookup_queries and case.minimum_lookup_coverage == 0 for case in cases)
        assert all(not any(q.startswith("query-lookup-") for q in case.expected_public_query_ids) for case in cases)
    else:
        assert all(case.lookup_queries and case.minimum_lookup_coverage > 0 for case in cases)


def test_paraphrases_do_not_enter_natural_gate():
    natural = protocol.load_cases("natural")
    paraphrases = protocol.load_cases("paraphrases")
    assert not {row["id"] for row in natural} & {row["id"] for row in paraphrases}
    assert not {row["question"] for row in natural} & {row["question"] for row in paraphrases}


def test_report_only_cli_retains_failed_verdict(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["protocol", "--live", "--lane", "natural", "--question-only"])
    monkeypatch.setattr(protocol, "run_live", lambda *a, **kw: {"verdict": "FAIL", "report_only": True})
    assert protocol.main() == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"


def test_gate_cli_failure_still_fails(monkeypatch):
    monkeypatch.setattr("sys.argv", ["protocol", "--live", "--lane", "natural"])
    monkeypatch.setattr(protocol, "run_live", lambda *a, **kw: {"verdict": "FAIL", "report_only": False})
    assert protocol.main() == 1


@pytest.mark.parametrize("snippet,expected", [
    ("Setup creates the database. Health checks the installation.", True),
    ("Setup creates the database.", False),
    ("Health checks the installation.", False),
])
def test_runner_forwards_scope_and_requires_each_fact_group(monkeypatch, snippet, expected):
    from types import SimpleNamespace
    from scripts import run_project_docs_self_host_gate as gate

    arguments = []
    payload = {
        "status": "ok", "kind": "docs_context", "sources": [{
            "path_or_url": "alternative.md", "snippet": snippet,
        }], "covered_query_ids": ["query-lookup-1"], "missing_query_ids": ["query-original"],
    }

    def capture(args, service):
        arguments.append(args)
        return payload, {}

    def preflight(tool, args, service):
        arguments.append(args)
        return {"recommended_next_action": {"arguments_patch": {"action": "sync_project_docs"}}}

    monkeypatch.setattr(gate, "_call_with_snapshot", capture)
    monkeypatch.setattr(gate, "call_docs_tool_payload", preflight)
    monkeypatch.setattr(gate, "LibraryDocsService", lambda **kw: SimpleNamespace(
        sync_project_docs=lambda *a, **kw: SimpleNamespace(status="success"),
    ))
    monkeypatch.setattr(gate, "LibraryRegistry", lambda *a: None)
    monkeypatch.setattr(gate, "DocmancerAgent", lambda **kw: None)
    case = gate.LiveCase(
        question="How can I set up and verify the tool?", scope="all", case_id="stable-compound-id",
        relevant_paths=("preferred.md", "alternative.md"), expected_kind="docs_context",
        lookup_queries=("How is installation verified?",), minimum_lookup_coverage=1,
        expected_public_query_ids=("query-original", "query-lookup-1"),
        required_fact_groups=(
            (("preferred.md", "Create the database"), ("alternative.md", "Setup creates the database")),
            (("alternative.md", "Health checks the installation"),),
        ),
    )
    report = gate.run(cases=(case,), negative_cases=())
    result = report["results"][0]
    assert all(args["scope"] == "all" for args in arguments)
    assert arguments[1]["lookup_queries"] == list(case.lookup_queries)
    assert result["case_id"] == "stable-compound-id"
    assert result["checks"]["required_facts"] is expected
    assert result["checks"]["public_query_inventory"] is True
    assert result["checks"]["original_coverage_attribution"] is True
    assert result["observed"]["original_query_covered"] is False
    assert result["top1_fact_bearing"] is True


def test_lock_rejects_corpus_drift(monkeypatch, tmp_path):
    original = protocol.CASES_PATH
    monkeypatch.setattr(protocol, "CASES_PATH", tmp_path / "cases.json")
    (tmp_path / "natural.json").write_bytes(original.with_name("natural.json").read_bytes() + b" ")
    with pytest.raises(ValueError, match="hash does not match"):
        protocol.load_cases("natural")


def test_project_context_quality_contract_passes():
    report = run_contract()

    assert report["verdict"] == "PASS"
    assert report["passed_count"] == report["case_count"] == 16
