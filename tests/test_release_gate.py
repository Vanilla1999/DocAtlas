from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import main_ruleset


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def self_host_payload_runner(monkeypatch, tmp_path):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import Mock

    from scripts import run_project_docs_self_host_gate as gate
    from scripts._project_docs_self_host_fixture import SelfHostFixture
    from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload
    from docmancer.docs.interfaces.mcp import context_tools
    from docmancer.docs.application.model_visible_projection import _snapshot_entry, _source_digest

    text = "Docs provide grounded project documentation.\ndoc-atlas mcp packs-serve\n"
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki/Commands.md").write_text(text)
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "_historical_paths", lambda: set())
    original = {"path": "wiki/Commands.md", "content": text}
    source = {
        "path_or_url": "wiki/Commands.md", "evidence_id": "e1",
        "snippet": text.splitlines()[0], "content_sha256": _source_digest(original),
        "retrieval_query_matches": {"query-original": {"qualified": True, "coverage_kind": "direct"}},
    }
    payload = {
        "status": "ok", "kind": "docs_context", "context_status": "ready",
        "answer_supported": False, "answer_available": False, "edit_ready": False,
        "answer_policy": "cite_only", "facets": [], "sources": [{
            key: value for key, value in source.items() if key != "retrieval_query_matches"
        }],
        "covered_query_ids": ["query-original"], "missing_query_ids": [],
        "estimated_tokens": 1,
    }
    app = SimpleNamespace(
        get_docs_context=Mock(return_value=SimpleNamespace(context_pack=[{
            **original, "retrieval_query_matches": source["retrieval_query_matches"],
        }])),
    )
    service = SimpleNamespace(
        _cold=SimpleNamespace(_service=None, member_storage_policy=SimpleNamespace(
            db_path=tmp_path / "uninitialized.db", marker=tmp_path / "uninitialized.owner",
        )),
        unified_context=app,
        get_docs_context=Mock(side_effect=AssertionError("Do not replay the facade query")),
    )

    @contextmanager
    def fixture_context(origin):
        fixture = SelfHostFixture(tmp_path, service, None, {}, {})
        fixture.prepare = Mock()
        yield fixture
        if not fixture.cold_read_verified:
            fixture.prepare.assert_not_called()

    monkeypatch.setattr(gate, "self_host_fixture", fixture_context)
    monkeypatch.setattr(context_tools, "validate_model_visible_projection", lambda *args, **kwargs: [])

    def run(
        mutator=lambda value: None, *, question="How do Docs work?",
        snapshot_mutator=lambda value: None, missing=False, negative=None,
        expected_public_query_ids=(), lookup_queries=(), real_projection=False,
        payload_transform=lambda value: value, expected_kind="docs_context",
        preflight_transform=lambda value: value,
    ):
        app.get_docs_context.reset_mock()
        retrieve = app.get_docs_context
        select = gate.docs_context_projection.context_selection_decision
        validate = context_tools.validate_model_visible_projection
        value = copy.deepcopy(payload)
        snapshot = {"e1": {
            **_snapshot_entry(original, copy.deepcopy(payload["sources"][0])),
            "qualification": copy.deepcopy(source),
        }}
        mutator(value)
        snapshot_mutator(snapshot)
        calls = 0

        def dispatch(tool, arguments, instance):
            nonlocal calls
            calls += 1
            if calls == 1:
                return preflight_transform(build_mcp_error_payload(
                    reason_code="permission_denied", message="permission_denied: request failed",
                    exception=PermissionError("member_store_uninitialized"),
                    tool="get_docs_context", phase="execution",
                ))
            instance.unified_context.get_docs_context(arguments["question"], project_path=arguments["project_path"])
            if arguments["question"] == "negative":
                return negative
            if missing and calls == 2:
                return None
            decision = gate.docs_context_projection.context_selection_decision(
                [snapshot["e1"]["qualification"]], ["query-original"],
            )
            projected = gate.docs_context_projection._payload(
                [snapshot["e1"]["qualification"]], decision=decision, query_plan={},
            ) if real_projection else value
            if real_projection:
                snapshot["e1"]["projected_source"] = copy.deepcopy(projected["sources"][0])
            context_tools.validate_model_visible_projection(projected, snapshot=snapshot, max_tokens=None)
            return payload_transform(copy.deepcopy(projected))

        monkeypatch.setattr(gate, "call_docs_tool_payload", dispatch)
        case = gate.LiveCase(
            question, ("wiki/Commands.md",), required_fragments=("grounded project documentation",),
            expected_kind=expected_kind,
            required_facts_by_path=(("wiki/Commands.md", "grounded project documentation"),),
            expected_public_query_ids=expected_public_query_ids, lookup_queries=lookup_queries,
        )
        report = gate.run(cases=(case,) * 15, negative_cases=("negative",))
        assert app.get_docs_context is retrieve
        assert gate.docs_context_projection.context_selection_decision is select
        assert context_tools.validate_model_visible_projection is validate
        service.get_docs_context.assert_not_called()
        return report, app

    return run


def _assert_self_host_payload_baseline(self_host_payload_runner):
    report, _ = self_host_payload_runner(negative={"status": "insufficient_evidence"})
    assert report["verdict"] == "PASS", report["errors"]


_SELF_HOST_BAD_PAYLOADS = [
    (lambda p: p["sources"][0].update(snippet="Docs provide context.", title="grounded project documentation"), "required_facts"),
    (lambda p: p.update(sources=p["sources"] * 4), "citation_integrity"),
    (lambda p: p.update(answer="x" * 4000), "context_contract"),
    (lambda p: p.update(edit_ready=True), "context_contract"),
    (lambda p: p.update(answer_available=True), "context_contract"),
    (lambda p: p["sources"][0].update(evidence_id="forged"), "citation_integrity"),
    (lambda p: p["sources"][0].update(content_sha256="a" * 64), "citation_integrity"),
    (lambda p: p.update(facets=[{"evidence_ids": ["forged"]}]), "citation_integrity"),
    (lambda p: p.update(covered_query_ids=["query-original", "query-internal-1"]), "public_query_inventory"),
    (lambda p: p.update(missing_query_ids=["query-internal-1"]), "public_query_inventory"),
    (lambda p: p.update(covered_query_ids=["query-original", "query-original"]), "public_query_inventory"),
    (lambda p: p.update(missing_query_ids=["query-original"]), "public_query_inventory"),
    (lambda p: p.update(covered_query_ids=[]), "public_query_inventory"),
    (lambda p: p.update(answer_policy="answer_freely"), "context_contract"),
]


def _assert_self_host_rejects_bad_payloads(self_host_payload_runner, mutation, check):
    report, _ = self_host_payload_runner(mutation, negative={"status": "insufficient_evidence"})
    assert report["verdict"] == "FAIL"
    assert report["results"][0]["checks"][check] is False


def _assert_self_host_metadata_is_not_top1_fact(self_host_payload_runner):
    report, _ = self_host_payload_runner(lambda p: p["sources"][0].update(
        snippet="Docs provide context.", title="grounded project documentation",
    ))
    assert report["metrics"]["top1_fact_bearing_count"] == 0
    assert report["metrics"]["useful_result_count"] == 0
    report, _ = self_host_payload_runner(lambda p: p["sources"].insert(
        0, {"snippet": "Docs provide grounded project documentation."},
    ))
    assert report["metrics"]["top1_fact_bearing_count"] == 0


def _assert_self_host_measures_cost_without_fixed_ceilings(self_host_payload_runner):
    report, _ = self_host_payload_runner(lambda p: p.update(sources=p["sources"] * 4, answer="x" * 4000))
    assert report["metrics"]["max_source_count"] == 4
    assert "source_budget_violation_count" not in report["metrics"]
    # Duplicate evidence IDs and nonempty answer remain independently invalid.
    assert report["verdict"] == "FAIL"
    assert report["results"][0]["checks"]["citation_integrity"] is False
    assert report["results"][0]["checks"]["context_contract"] is False
    assert report["metrics"]["max_estimated_tokens"] > 800
    assert "token_budget_violation_count" not in report["metrics"]
    assert report["metrics"]["max_public_utf8_bytes"] > 3200


def _assert_self_host_packs_content_is_intent_scoped(self_host_payload_runner, question, expected):
    snippet = "Docs provide grounded project documentation.\ndoc-atlas mcp packs-serve"

    def snapshot_mutator(snapshot):
        snapshot["e1"]["projected_source"]["snippet"] = snippet
        snapshot["e1"]["qualification"]["snippet"] = snippet

    report, _ = self_host_payload_runner(
        lambda p: p["sources"][0].update(snippet=snippet), question=question,
        snapshot_mutator=snapshot_mutator, negative={"status": "insufficient_evidence"},
    )
    assert report["metrics"]["packs_contamination_count"] == expected
    assert report["verdict"] == ("FAIL" if expected else "PASS"), report["errors"]
    from scripts.run_project_docs_self_host_gate import _packs_contamination
    assert not _packs_contamination("How do I start Docs MCP?", {"sources": [{
        "path_or_url": "docs/PROJECT_MAP.md", "snippet": "The runtime also has a Packs gateway.",
    }]})
    assert not _packs_contamination("How do I start Docs MCP?", {"sources": [{
        "path_or_url": "wiki/Commands.md", "snippet": "Do not run doc-atlas mcp packs-serve for Docs.",
    }]})
    assert _packs_contamination("How do I start Docs MCP?", {"sources": [{
        "path_or_url": "wiki/Commands.md",
        "snippet": "Use doc-atlas mcp packs-serve instead of doc-atlas mcp docs-serve.",
    }]})
    for substituted in (
        "Do not run doc-atlas mcp docs-serve; use doc-atlas mcp packs-serve for Docs.",
        "For Docs use doc-atlas mcp packs-serve; doc-atlas mcp docs-serve is broken.",
    ):
        assert _packs_contamination("How do I start Docs MCP?", {"sources": [{
            "path_or_url": "wiki/Commands.md", "snippet": substituted,
        }]})


def _assert_self_host_missing_payload_preserves_case_partitions(self_host_payload_runner):
    report, _ = self_host_payload_runner(missing=True)
    assert report["case_count"] == 16
    assert report["positive_case_count"] == 15
    assert report["negative_case_count"] == 1
    assert report["results"][0]["passed"] is False
    assert any("failed negative cases" in error for error in report["errors"])


def _assert_self_host_negative_cannot_authorize(self_host_payload_runner, flag):
    report, _ = self_host_payload_runner(negative={"status": "insufficient_evidence", flag: True})
    assert report["verdict"] == "FAIL"
    assert report["results"][-1]["passed"] is False


def _assert_self_host_attribution_uses_same_call_qualified_snapshot(self_host_payload_runner, kinds):
    def change(snapshot):
        snapshot["e1"]["qualification"]["retrieval_query_matches"]["query-original"] = {
            "qualified": bool(kinds), "coverage_kinds": list(kinds),
            "coverage_kind": kinds[0] if kinds else "direct",
        }

    report, service = self_host_payload_runner(snapshot_mutator=change)
    assert service.get_docs_context.call_count == 16
    assert report["results"][0]["observed"]["coverage_attribution"] == sorted(kinds)
    assert report["metrics"]["direct_only_coverage_count"] == (15 if kinds == ("direct",) else 0)
    assert report["metrics"]["derived_only_coverage_count"] == (15 if kinds == ("derived",) else 0)
    assert report["metrics"]["both_coverage_count"] == (15 if len(kinds) == 2 else 0)


def _assert_self_host_attribution_rejects_same_path_different_identity(self_host_payload_runner):
    report, _ = self_host_payload_runner(lambda p: p["sources"][0].update(evidence_id="other"))
    assert report["results"][0]["observed"]["coverage_attribution"] == []


def _assert_self_host_cost_has_no_fixed_token_ceiling(self_host_payload_runner):
    from docmancer.docs.application.model_visible_projection import estimate_projection_tokens

    def resize(payload, target):
        payload.pop("estimated_tokens")
        payload["padding"] = ""
        payload["padding"] = "x" * (4 * (target - estimate_projection_tokens(payload)))
        assert estimate_projection_tokens(payload) == target

    for target in (800, 801, 1600):
        report, _ = self_host_payload_runner(
            lambda payload: resize(payload, target), negative={"status": "insufficient_evidence"},
        )
        assert report["metrics"]["max_estimated_tokens"] == target
        assert "token_budget_violation_count" not in report["metrics"]
        assert report["verdict"] == "PASS", report["errors"]


def _assert_self_host_expected_public_inventory(self_host_payload_runner):
    for expected in (("query-original", "query-lookup-1"), ()):
        report, _ = self_host_payload_runner(
            lambda payload: payload.update(missing_query_ids=["query-lookup-1"]),
            expected_public_query_ids=expected, lookup_queries=("Docs retrieval",),
            negative={"status": "insufficient_evidence"},
        )
        assert report["verdict"] == "PASS", report["errors"]


def _assert_self_host_attribution_rejects_changed_snapshot(self_host_payload_runner):
    for field, value in (("snippet", "Other text"), ("evidence_id", "other"), ("content_sha256", "a" * 64)):
        report, _ = self_host_payload_runner(snapshot_mutator=lambda snapshot: snapshot["e1"]["qualification"].update({field: value}))
        assert report["results"][0]["observed"]["coverage_attribution"] == []


def _assert_self_host_private_qualification_projection(self_host_payload_runner):
    def qualify(snapshot):
        source = snapshot["e1"]["qualification"]
        source.update({
            "_qualification_candidate": {"content": source["snippet"], "path": source["path_or_url"]},
            "_expected_project_identity": "project-test",
            "_lifecycle_intent": "active",
            "catalog_role": "commands",
            "retrieval_query_ids": ["query-original"],
            "_assigned_requirement_ids": [],
        })
        source["retrieval_query_matches"]["query-original"].update(
            coverage_kinds=["direct", "derived"],
        )

    report, app = self_host_payload_runner(
        snapshot_mutator=qualify, real_projection=True,
        negative={"status": "insufficient_evidence"},
    )
    assert app.get_docs_context.call_count == 16
    assert report["verdict"] == "PASS", report["errors"]
    assert report["metrics"]["both_coverage_count"] == 15
    assert report["metrics"]["original_query_covered_count"] == 15
    assert "_qualification_candidate" not in report["results"][0]["payload"]["sources"][0]


def _assert_self_host_exact_public_source_keys(self_host_payload_runner):
    for mutate in (
        lambda bound: bound["qualification"].update(scope=None),
        lambda bound: bound["projected_source"].update(scope=None),
        lambda bound: bound["qualification"].pop("snippet"),
        lambda bound: bound["projected_source"].pop("snippet"),
    ):
        report, _ = self_host_payload_runner(snapshot_mutator=lambda snapshot: mutate(snapshot["e1"]))
        assert report["results"][0]["observed"]["coverage_attribution"] == []


def _assert_self_host_abstention_safety(self_host_payload_runner):
    for unsafe in ({"kind": "docs_answer"}, {"edit_ready": True}, {"mutation_ready": True}):
        payload = {"status": "insufficient_evidence", **unsafe}
        report, _ = self_host_payload_runner(negative=payload)
        assert report["results"][-1]["passed"] is False, unsafe
        report, _ = self_host_payload_runner(
            lambda value: value.update(payload), expected_kind="insufficient_evidence",
        )
        assert report["results"][0]["passed"] is False, unsafe


def _assert_self_host_nonmapping_payloads(self_host_payload_runner):
    for invalid in (None, [], ["unexpected"], "unexpected", 7):
        report, _ = self_host_payload_runner(payload_transform=lambda value: invalid, negative=invalid)
        assert report["case_count"] == 16
        assert report["positive_case_count"] == 15
        assert report["negative_case_count"] == 1
        assert report["passed_count"] == 0
        assert report["verdict"] == "FAIL"
        report, _ = self_host_payload_runner(preflight_transform=lambda value: invalid)
        assert report["verdict"] == "FAIL"
        assert any("pre-sync" in error for error in report["errors"])


def _assert_self_host_positive_passed_count(self_host_payload_runner):
    report, _ = self_host_payload_runner(missing=True, negative={"status": "insufficient_evidence"})
    assert report["positive_passed_count"] == 14
    assert report["passed_count"] == 15






























def _assert_main_ruleset_contract(monkeypatch, capsys) -> None:
    desired = main_ruleset._load(main_ruleset.DEFAULT_CONFIG)
    main_ruleset.validate_contract(desired)
    checks = main_ruleset._rule(
        main_ruleset.canonical_policy(desired),
        "required_status_checks",
    )["parameters"]["required_status_checks"]
    assert checks == [
        {
            "context": "required-ci",
            "integration_id": main_ruleset.GITHUB_ACTIONS_APP_ID,
        },
        {
            "context": "required-release",
            "integration_id": main_ruleset.GITHUB_ACTIONS_APP_ID,
        },
    ]

    mutations = [
        (
            lambda payload: payload["rules"][2]["parameters"].__setitem__(
                "dismiss_stale_reviews_on_push", True
            ),
            "pull request rule differs",
        ),
        (
            lambda payload: payload["rules"][3]["parameters"].__setitem__(
                "do_not_enforce_on_create", True
            ),
            "required checks must be strict",
        ),
        (
            lambda payload: payload["rules"][3]["parameters"][
                "required_status_checks"
            ][0].__setitem__("integration_id", None),
            "integration_id must be an integer",
        ),
    ]
    for mutator, message in mutations:
        payload = copy.deepcopy(desired)
        mutator(payload)
        with pytest.raises(ValueError, match=message):
            main_ruleset.validate_contract(payload)

    calls: list[tuple[str, str, str | None]] = []

    def fake_request(repo: str, path: str, *, token: str | None, **_: object):
        calls.append((repo, path, token))
        return [{"id": 7, "name": "protect-main"}]

    monkeypatch.setattr(main_ruleset, "_request", fake_request)
    result = main_ruleset._find_ruleset(
        "owner/repo",
        "protect-main",
        token="token",
    )
    assert result == {"id": 7, "name": "protect-main"}
    assert calls == [
        (
            "owner/repo",
            "/rulesets?includes_parents=false&per_page=100",
            "token",
        )
    ]

    remote = copy.deepcopy(desired)
    remote.pop("bypass_actors")
    monkeypatch.setattr(
        main_ruleset,
        "_find_ruleset",
        lambda *_args, **_kwargs: {"id": 7, "name": "protect-main"},
    )
    monkeypatch.setattr(
        main_ruleset,
        "_request",
        lambda *_args, **_kwargs: remote,
    )
    with pytest.raises(RuntimeError, match="omitted bypass_actors"):
        main_ruleset.check("owner/repo", desired, token="token")

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main_ruleset.main(["--check"]) == 1
    assert "Administration: write" in capsys.readouterr().err


def test_release_gate_help(monkeypatch, capsys) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/release_gate.py"), "--help"],
        check=True,
    )
    _assert_main_ruleset_contract(monkeypatch, capsys)
