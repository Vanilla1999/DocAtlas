from __future__ import annotations

from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsResult, ProjectDocsResult


def test_trust_contract_selects_project_sources_and_forbids_webfetch():
    project_docs = ProjectDocsResult(
        project_path="/repo",
        query="architecture",
        indexed_sources=[{"path": "README.md", "source": "/repo/README.md"}],
    )

    contract = build_project_context_trust_contract(
        project_docs=project_docs,
        dependency_docs=None,
        requested_library=None,
        mode="auto",
    )

    assert contract["schema_version"] == "trust-contract-1.0-mvp"
    assert contract["selected_sources"] == contract["trusted_sources"]
    assert contract["selected"] == contract["selected_sources"]
    assert contract["trusted"] == contract["trusted_sources"]
    assert contract["rejected"] == contract["rejected_sources"]
    assert contract["risky"] == contract["risky_sources"]
    assert contract["rejected_or_risky"] == contract["rejected_or_risky_sources"]
    assert contract["selected_sources"][0]["source_class"] == "project_file"
    assert contract["policy"] == {"direct_webfetch": "forbidden", "reason_code": "trusted_context_available"}


def test_trust_contract_reports_risky_dependency_warnings_and_rejections():
    dependency_docs = DocsResult(
        library_id="pub/go_router/14/api",
        library="go_router",
        version="14.8.1",
        topic="routing",
        refreshed=False,
        stale_before_refresh=True,
        warning="ambiguous source",
        last_refreshed_at=None,
        status="ambiguous",
        warnings=["best_effort_docs"],
        results=[DocsChunk(title="GoRouter", content="Use GoRouter.", source="https://pub.dev", url="https://pub.dev")],
        requested_version="14.8.1",
        resolved_version="14.8.1",
        version_source="lockfile_exact",
        docs_exactness="best_effort",
        docs_binding_source="pub_dartdoc",
        confidence="medium",
        next_actions=["retry with docs_url"],
    )

    contract = build_project_context_trust_contract(
        project_docs=None,
        dependency_docs=dependency_docs,
        requested_library="go_router",
        mode="deps-only",
    )

    assert contract["selected_sources"][0]["source_class"] == "dependency_docs"
    assert contract["selected_sources"][0]["trust_level"] == "best_effort"
    assert any(item["reason_code"] == "best_effort_docs" for item in contract["risky_sources"])
    assert any(item["reason_code"] == "ambiguous" for item in contract["rejected_sources"])
    assert any(item["reason_code"] == "project_docs_skipped" for item in contract["risky_sources"])


def test_trust_contract_requests_prefetch_when_dependency_not_resolved():
    contract = build_project_context_trust_contract(
        project_docs=None,
        dependency_docs=None,
        requested_library="go_router",
        mode="auto",
    )

    assert contract["policy"]["direct_webfetch"] == "discovery_only"
    assert contract["rejected_sources"] == [{
        "source_class": "dependency_docs",
        "library": "go_router",
        "reason_code": "not_resolved",
        "reason": "Requested dependency docs were not resolved.",
        "risk_level": "high",
    }]
    assert contract["next_actions"][0]["tool"] == "prefetch_project_docs"
