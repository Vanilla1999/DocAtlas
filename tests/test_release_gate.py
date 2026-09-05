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
    from types import SimpleNamespace
    from unittest.mock import Mock

    from scripts import run_project_docs_self_host_gate as gate
    from docmancer.docs.interfaces.mcp import context_tools
    from docmancer.docs.application.model_visible_projection import _snapshot_entry, _source_digest

    text = "Docs provide grounded project documentation.\nPacks build code context bundles.\n"
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
        sync_project_docs=Mock(return_value=SimpleNamespace(status="success")),
        unified_context=app,
        get_docs_context=Mock(side_effect=AssertionError("Do not replay the facade query")),
    )
    monkeypatch.setattr(gate, "LibraryDocsService", lambda **kwargs: service)
    monkeypatch.setattr(gate, "LibraryRegistry", lambda *args: None)
    monkeypatch.setattr(gate, "DocmancerAgent", lambda **kwargs: None)
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
                return preflight_transform({"recommended_next_action": {"arguments_patch": {"action": "sync_project_docs"}}})
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
            context_tools.validate_model_visible_projection(projected, snapshot=snapshot, max_tokens=800)
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
    (lambda p: p.update(sources=p["sources"] * 4), "context_contract"),
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


def _assert_self_host_measures_full_budgets(self_host_payload_runner):
    report, _ = self_host_payload_runner(lambda p: p.update(sources=p["sources"] * 4, answer="x" * 4000))
    assert report["metrics"]["max_source_count"] == 4
    assert report["metrics"]["source_budget_violation_count"] == 15
    assert report["metrics"]["max_estimated_tokens"] > 800
    assert report["metrics"]["token_budget_violation_count"] == 15


def _assert_self_host_packs_content_is_intent_scoped(self_host_payload_runner, question, expected):
    snippet = "Docs provide grounded project documentation.\nPacks build code context bundles."

    def snapshot_mutator(snapshot):
        snapshot["e1"]["projected_source"]["snippet"] = snippet
        snapshot["e1"]["qualification"]["snippet"] = snippet

    report, _ = self_host_payload_runner(
        lambda p: p["sources"][0].update(snippet=snippet), question=question,
        snapshot_mutator=snapshot_mutator, negative={"status": "insufficient_evidence"},
    )
    assert report["metrics"]["packs_contamination_count"] == expected
    assert report["verdict"] == ("FAIL" if expected else "PASS"), report["errors"]


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


def _assert_self_host_token_boundary(self_host_payload_runner):
    from docmancer.docs.application.model_visible_projection import estimate_projection_tokens

    def resize(payload, target):
        payload.pop("estimated_tokens")
        payload["padding"] = ""
        payload["padding"] = "x" * (4 * (target - estimate_projection_tokens(payload)))
        assert estimate_projection_tokens(payload) == target

    for target in (800, 801):
        report, _ = self_host_payload_runner(
            lambda payload: resize(payload, target), negative={"status": "insufficient_evidence"},
        )
        assert report["metrics"]["max_estimated_tokens"] == target
        assert report["metrics"]["token_budget_violation_count"] == (15 if target > 800 else 0)
        assert report["verdict"] == ("FAIL" if target > 800 else "PASS")


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


def test_publish_workflow_is_manual_build_once_and_oidc() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    trigger_block = text.split("\non:\n", 1)[1].split("\npermissions:\n", 1)[0]
    trigger_events = {
        line.strip()[:-1]
        for line in trigger_block.splitlines()
        if line.startswith("  ")
        and not line.startswith("    ")
        and line.strip().endswith(":")
    }
    assert trigger_events == {"workflow_dispatch", "pull_request"}
    assert "    tags:" not in trigger_block
    assert text.count("python -m build") == 1
    assert 'python: ["3.11", "3.12", "3.13"]' in text
    assert "id-token: write" in text
    assert "PYPI_API_TOKEN" not in text
    assert "environment: release" in text
    assert "if: github.event_name == 'workflow_dispatch'" in text
    assert "refs/tags/${{ inputs.tag }}" in text
    for line in text.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref)


def test_dispatched_release_source_must_be_on_protected_main() -> None:
    # Historical node id retained for the diagnostic inventory. The release
    # policy now requires main ancestry while branch protection is an explicit
    # accepted risk rather than a hidden or falsely-green control.
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    build = text[text.index("  build:"):text.index("  wheel:")]
    assert "fetch-depth: 0" in build
    assert "if: github.event_name == 'workflow_dispatch'" in build
    assert "git fetch --no-tags origin main:refs/remotes/origin/main" in build
    assert "git merge-base --is-ancestor HEAD refs/remotes/origin/main" in build
    assert 'branch.get("protected")' not in build
    assert "remote main is not protected" not in build
    assert "Release source ancestry: PASS" in build

    roadmap = (ROOT / "roadmap" / "README.md").read_text(encoding="utf-8")
    scorecard = (ROOT / "docs" / "public-truth-scorecard.md").read_text(encoding="utf-8")
    assert "P0.1 — Remote `main` ruleset: accepted risk" in roadmap
    assert "| Branch protection | `accepted_risk` |" in scorecard
    assert "Status: **INCOMPLETE**" in scorecard


def test_installer_smoke_passes_an_existing_wheel_path() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert 'DOCATLAS_INSTALL_SOURCE="$(find "$PWD/dist" -name \'*.whl\' -print -quit)"' in text


def test_publish_excludes_release_manifest_from_pypi_upload() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    remove_manifest = text.index("rm dist/release-manifest.json")
    publish_action = text.index("pypa/gh-action-pypi-publish@")
    assert remove_manifest < publish_action


def test_sdist_gate_builds_and_smokes_its_own_wheel() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    assert "python -m pip wheel --no-deps --wheel-dir sdist-wheel dist/*.tar.gz" in text
    assert "python -m pip install --force-reinstall sdist-wheel/*.whl" in text
    assert "python scripts/release_gate.py --dist sdist-wheel" in text


def test_publish_runs_exact_public_version_smoke() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    publish = text[text.index("  publish:"):text.index("  public-platform-smoke:")]
    assert "RELEASE_TAG: ${{ inputs.tag }}" in publish
    assert 'RELEASE_VERSION="${RELEASE_TAG#v}"' in publish
    assert 'RELEASE_VERSION="${{ inputs.tag }}"' not in publish
    assert "DOCATLAS_INSTALL_VERSION=\"$RELEASE_VERSION\"" in publish
    assert "for attempt in 1 2 3 4 5" in publish
    assert "PIP_NO_CACHE_DIR=1" in publish
    assert "scripts/docs_mcp_stdio_smoke.py" in publish


def test_publish_verifies_exact_public_release_on_all_primary_platforms() -> None:
    text = (ROOT / ".github/workflows/publish.yml").read_text()
    public = text[text.index("  public-platform-smoke:"):]
    assert "if: github.event_name == 'workflow_dispatch'" in public
    assert "needs: [publish]" in public
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" in public
    assert "ref: refs/tags/${{ inputs.tag }}" in public
    assert 'run: python scripts/public_release_smoke.py --tag "${{ inputs.tag }}"' in public


def test_public_release_smoke_is_exact_public_and_no_cache() -> None:
    text = (ROOT / "scripts/public_release_smoke.py").read_text()
    assert 'PYPI_INDEX = "https://pypi.org/simple"' in text
    assert '"--isolated"' in text
    assert '"--no-cache-dir"' in text
    assert 'f"doc-atlas=={version}"' in text
    assert "source_version() != version" in text
    assert 'expected = f"doc-atlas {version}"' in text
    assert 'ROOT / "scripts" / "docs_mcp_stdio_smoke.py"' in text


def test_stdio_smoke_requires_cited_content() -> None:
    text = (ROOT / "scripts/docs_mcp_stdio_smoke.py").read_text()
    assert "assert NEEDLE in rendered" in text
    assert 'assert set(canonical_query) == {"question", "project_path"}' in text
    canonical_block = text[text.index("canonical_query = {"):text.index("answer = payload", text.index("canonical_query = {"))]
    assert "output_mode" not in canonical_block
    assert "compatibility_query" not in text
    assert "validate_context_payload(answer, required_fragment=NEEDLE)" in text


def test_stdio_smoke_uses_primary_docatlas_home_without_legacy_writes() -> None:
    text = (ROOT / "scripts/docs_mcp_stdio_smoke.py").read_text()
    assert '"HOME": str(user_home)' in text
    assert '"USERPROFILE": str(user_home)' in text
    assert '"DOCATLAS_HOME": str(docatlas_home)' in text
    assert 'env.pop("DOCATLAS_HOME", None)' not in text
    assert 'not (user_home / ".docmancer").exists()' in text


@pytest.mark.parametrize("self_host_check,args", [
    *[(check, ()) for check in (
        _assert_self_host_payload_baseline,
        _assert_self_host_metadata_is_not_top1_fact,
        _assert_self_host_measures_full_budgets,
        _assert_self_host_missing_payload_preserves_case_partitions,
        _assert_self_host_attribution_rejects_same_path_different_identity,
        _assert_self_host_token_boundary,
        _assert_self_host_expected_public_inventory,
        _assert_self_host_attribution_rejects_changed_snapshot,
        _assert_self_host_private_qualification_projection,
        _assert_self_host_exact_public_source_keys,
        _assert_self_host_abstention_safety,
        _assert_self_host_nonmapping_payloads,
        _assert_self_host_positive_passed_count,
    )],
    *[(_assert_self_host_rejects_bad_payloads, values) for values in _SELF_HOST_BAD_PAYLOADS],
    *[(_assert_self_host_packs_content_is_intent_scoped, values) for values in (
        ("How do Docs work?", 15), ("Compare Docs and Packs", 0),
        ("How do Docs work, not Packs?", 15), ("How do I get started?", 0),
    )],
    *[(_assert_self_host_negative_cannot_authorize, (flag,)) for flag in (
        "answer_supported", "answer_available", "edit_ready",
    )],
    *[(_assert_self_host_attribution_uses_same_call_qualified_snapshot, (kinds,)) for kinds in (
        ("direct",), ("derived",), ("direct", "derived"), (),
    )],
])
def test_stdio_smoke_accepts_structured_content_and_legacy_json_text(self_host_payload_runner, self_host_check, args) -> None:
    self_host_check(self_host_payload_runner, *args)
    from scripts.docs_mcp_stdio_smoke import payload, text_payload, validate_context_payload
    from scripts.run_project_docs_self_host_gate import (
        GOLD_CASES,
        _threshold_failures,
        _validate_context_result,
    )

    class Text:
        def __init__(self, text: str) -> None:
            self.text = text

    class Result:
        def __init__(self, *, structured=None, text: str = "") -> None:
            if structured is not None:
                self.structuredContent = structured
            self.content = [Text(text)]

    expected = {"status": "ok", "kind": "docs_answer"}
    assert payload(Result(structured=expected, text="not JSON")) is expected
    assert payload(Result(text='{"status": "ok", "kind": "docs_answer"}')) == expected
    assert text_payload(Result(text='{"status": "ok", "kind": "docs_answer"}')) == expected
    with pytest.raises(AssertionError, match="included structuredContent"):
        text_payload(Result(structured=expected, text='{"status": "ok"}'))
    validate_context_payload({
        "status": "ok",
        "kind": "docs_context",
        "support_status": "retrieval_only",
        "context_status": "ready",
        "answer_supported": False,
        "answer_available": False,
        "sources": [{
            "path_or_url": "README.md",
            "snippet": "needle",
            "content_sha256": "a" * 64,
        }],
    }, required_fragment="needle")
    assert len(GOLD_CASES) == 15
    assert all(case.expected_kind == "docs_context" for case in GOLD_CASES)
    assert all(
        case.relevant_paths or case.expected_kind == "insufficient_evidence"
        for case in GOLD_CASES
    )
    invalid_citation = {
        "kind": "docs_context",
        "context_status": "ready",
            "answer_supported": False,
            "answer_available": False,
            "edit_ready": False,
            "answer_policy": "cite_only",
            "facets": [],
        "sources": [{"snippet": "grounded", "content_sha256": "z" * 64}],
    }
    assert _validate_context_result(invalid_citation) == "source lacks a grounded snippet or content hash"

    passing_metrics = {
        "false_supported_count": 0,
        "operational_contamination_count": 0,
        "useful_result_count": 13,
        "top1_fact_bearing_count": 12,
        "top3_relevant_count": 15,
        "original_query_covered_count": 12,
        "metadata_only_evidence_count": 0,
        "packs_contamination_count": 0,
        "docs_analysis_contamination_count": 0,
        "false_docs_answer_count": 0,
        "source_budget_violation_count": 0,
        "token_budget_violation_count": 0,
    }
    assert _threshold_failures(passing_metrics, 20) == []
    for key, value in (
        ("false_supported_count", 1),
        ("operational_contamination_count", 1),
        ("useful_result_count", 12),
        ("top1_fact_bearing_count", 11),
        ("top3_relevant_count", 14),
        ("original_query_covered_count", 11),
        ("metadata_only_evidence_count", 1),
        ("packs_contamination_count", 1),
        ("docs_analysis_contamination_count", 1),
        ("false_docs_answer_count", 1),
        ("source_budget_violation_count", 1),
        ("token_budget_violation_count", 1),
    ):
        assert _threshold_failures({**passing_metrics, key: value}, 20)

    maintained_contracts = (
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs/mcp-docs-server.md",
        ROOT / "docs/project-docs-mcp-workflow.md",
        ROOT / "docs/project-docs-demo.md",
        ROOT / "docs/INDEX.md",
        ROOT / "wiki/Architecture.md",
        ROOT / "docmancer/mcp/_docs_server_resources.py",
    )
    for contract_path in maintained_contracts:
        contract_text = contract_path.read_text(encoding="utf-8")
        for result_kind in (
            "docs_answer", "docs_context", "patch_context", "insufficient_evidence",
        ):
            assert result_kind in contract_text, (contract_path, result_kind)


def test_opencode_installer_enables_text_fallback_without_overwriting_other_environment() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert '"DOCATLAS_MCP_TEXT_FALLBACK": "1"' in text
    assert '"environment": {**environment, **desired["environment"]}' in text
    assert "has a different command; refusing to overwrite it" in text


def test_installer_compares_exact_version_output() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert '[ "$INSTALLED_VERSION" = "doc-atlas $EXPECTED_VERSION" ]' in text


def test_installer_accepts_pinned_and_local_sources() -> None:
    text = (ROOT / "scripts/install.sh").read_text()
    assert "DOCATLAS_INSTALL_SOURCE" in text
    assert "DOCATLAS_INSTALL_VERSION" in text
    assert "DOCATLAS_EXPECT_VERSION" in text


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
