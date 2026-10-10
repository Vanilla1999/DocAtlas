"""Bounded corpus narrowing and delivered literal-policy regression checks."""
from __future__ import annotations

import hashlib
import json

import pytest

from docmancer.connectors.fetchers.github import Context7Config, GitHubFetcher
from docmancer.connectors.fetchers.pipeline.filtering import (
    ContentDeduplicator,
    infer_docset_root,
    is_docs_url,
    normalize_url,
)


@pytest.mark.parametrize("url", [
    "https://docs.example.com/deep/page",
    "https://example.com/docs/topic/page",
    "https://example.com/ru/reference/page",
    "https://example.com/llms.txt",
    "https://example.com/llms-full.txt",
    "https://example.com/arbitrary/page",
    "file:///docs/page",
])
def test_url_does_not_infer_docset_identity(url):
    assert infer_docset_root(url) is None


@pytest.mark.parametrize("path", ["docs/topic/page", "a/b/c", "ru/api/page"])
def test_scope_retains_exact_seed_path(path):
    base = "https://example.com/" + path
    assert is_docs_url(base, base)
    assert is_docs_url(base + "/child", base)
    assert not is_docs_url(base.rsplit("/", 1)[0] + "/sibling", base)
    assert not is_docs_url(base + "-other", base)


@pytest.mark.parametrize("candidate", [
    "https://other.example/docs",
    "https://example.com:8443/docs",
    "ftp://example.com/docs",
    "https://user@example.com/docs",
    "https://example.com/docs-extra",
    "https://example.com/docs/page.pdf",
    "https://example.com/docs/page.png",
    "https://example.com/docs/login",
    "https://example.com/docs/account",
    "https://example.com/docs/../outside",
    "https://example.com/docs/%2e%2e/outside",
    "https://example.com/docs/%252e%252e/outside",
    "https://example.com/docs/%5c../outside",
])
def test_existing_transport_host_path_binary_security_barriers(candidate):
    assert not is_docs_url(candidate, "https://example.com/docs")


def test_blocked_locale_and_topic_exclusions_do_not_silently_broaden():
    counter = [0]
    assert not is_docs_url("https://example.com/docs/ru/page", "https://example.com/docs", counter)
    assert counter == [1]
    assert is_docs_url("https://example.com/ru/docs/page", "https://example.com/ru/docs")
    assert not is_docs_url("https://example.com/docs/blog/post", "https://example.com/docs")
    fetcher = GitHubFetcher()
    assert fetcher._select_documentation_files([
        "README.md", "docs/current.md", "docs/legacy/page.md", "docs/CHANGELOG.md",
    ]) == ["README.md", "docs/current.md"]


def test_github_ranking_uses_explicit_folder_order_not_topic_path():
    fetcher = GitHubFetcher(file_patterns=["**/*.md"])
    paths = ["docs/z.md", "README.md", "a.md", "reference/b.md"]
    assert fetcher._select_documentation_files(paths) == sorted(paths)
    config = Context7Config(folders=["reference", "docs"])
    assert fetcher._rank_file("reference/b.md", config) < fetcher._rank_file("docs/z.md", config)


def test_explicit_github_exclusions_and_file_types_remain():
    config = Context7Config(
        folders=["manual"], exclude_files=["secret.md"], exclude_folders=["manual/private"],
    )
    assert GitHubFetcher()._select_documentation_files([
        "manual/public.md", "manual/secret.md", "manual/private/page.md", "manual/image.png",
        "elsewhere/page.md",
    ], config) == ["manual/public.md"]


def test_url_normalization_and_content_hash_dedup_remain():
    assert normalize_url("https://example.com/docs/?utm_source=x#section") == "https://example.com/docs"
    dedup = ContentDeduplicator()
    assert not dedup.is_content_duplicate("Source context")
    assert dedup.is_content_duplicate(" Source   context ")
    assert not dedup.is_url_duplicate("https://example.com/docs/#one")
    assert dedup.is_url_duplicate("https://example.com/docs#two")


def test_github_source_branch_path_provenance_remains(monkeypatch):
    fetcher = GitHubFetcher()
    monkeypatch.setattr(fetcher, "_fetch_raw_file", lambda *args: "# Source\n\nExact cited context.")
    document, = fetcher._fetch_single_file("owner", "repo", "v1.2", "manual/page.md", None)
    assert document.source == "https://raw.githubusercontent.com/owner/repo/v1.2/manual/page.md"
    assert document.content == "# Source\n\nExact cited context."
    assert document.metadata["repo"] == "owner/repo"
    assert document.metadata["branch"] == "v1.2"
    assert document.metadata["file_path"] == "manual/page.md"
    assert document.metadata["docset_root"] == "https://github.com/owner/repo"
    assert document.metadata["fetch_method"] == "github"
    assert document.metadata["fetched_at"]


def test_delivered_contract_no_inferred_semantics_or_authority():
    from docmancer.mcp.agent_workflow_contract import public_agent_contract

    contract = public_agent_contract()
    workflow = contract["workflow"]
    lookup = workflow["free_form_lookup"]
    assert lookup["maximum_lookup_queries"] == 5
    assert lookup["original_question_unchanged"] is True
    assert lookup["inferred_semantic_equivalence"] is False
    assert lookup["authorizes_answer_or_edit"] is False
    assert "decomposition_triggers" not in lookup
    scope = workflow["scope_planning"]
    assert set(scope) == {
        "explicit_scope_is_authoritative", "module_path_implies_scope", "all_requires_no_module_filter",
        "never_widen_project_to_all", "all_is_repository_local",
    }
    answer = workflow["retrieval_only_answer"]
    assert answer["context_is_answer_proof"] is False
    assert answer["lookup_coverage_transfers_to_original"] is False
    assert answer["authorizes_edit"] is False
    assert workflow["recovery"]["hard_stop_false_authorizes_edit"] is False
    assert workflow["version_binding"]["cached_previous_version_is_current_evidence"] is False
    assert workflow["prepare_docs"]["speculative"] is False
    assert workflow["docs_status"]["discovery"] is False


def test_runtime_schema_hashes_and_identity_remain_bound_and_isolated():
    from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts

    def digest(value):
        return hashlib.sha256(json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()

    contract = public_agent_contract()
    identity = contract.pop("identity")
    assert identity == "sha256:" + digest(contract)
    for record, tool in zip(contract["tools"], runtime_public_tool_dicts(), strict=True):
        assert record["input_schema_sha256"] == digest(tool["inputSchema"])
        assert record["tool_contract_sha256"] == digest(tool)
    contract["workflow"]["free_form_lookup"]["maximum_lookup_queries"] = 999
    assert public_agent_contract()["workflow"]["free_form_lookup"]["maximum_lookup_queries"] == 5


@pytest.mark.parametrize("template", [
    "skill.md", "claude_code_skill.md", "claude_desktop_skill.md", "cursor_agents_md.md",
    "copilot_instructions.md", "project_bootstrap.md",
])
def test_installed_templates_render_literal_policy_and_current_identity(template):
    from docmancer.cli._commands_part01 import _get_template_content
    from docmancer.mcp.agent_workflow_contract import public_agent_contract_identity

    rendered = _get_template_content(template)
    assert public_agent_contract_identity() in rendered
    assert "{{CANONICAL_AGENT_CONTRACT}}" not in rendered
    assert "Use only explicitly supplied `lookup_queries`" in rendered
    assert ("A lookup does not establish coverage of the original question." in rendered
            or "Lookup coverage does not transfer to the original question." in rendered)
    assert "Mutation requires a separate explicit target and authorization" in rendered
    assert "Accept explicit logical implications" not in rendered
    assert "For onboarding/cross-module" not in rendered
    assert "split only for a concrete missing" not in rendered
