import json

import yaml
from click.testing import CliRunner

from docmancer.agent import DocmancerAgent
from docmancer.cli.__main__ import cli
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.eval.health import source_health_report
from docmancer.eval.metrics import hit_at_k, latency_percentile_ms, mrr
from docmancer.eval.runner import aggregate_quality_metrics, locale_contamination, run_retrieval_eval, run_task_context_benchmark, snippet_presence_metrics, source_diversity_metrics
from docmancer.eval.schema import load_golden_dataset
from docmancer.eval.trace import build_explain_trace, validate_explain_trace


def _config(tmp_path):
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return config


def _agent(tmp_path):
    agent = DocmancerAgent(config=_config(tmp_path))
    agent.ingest_documents(
        [
            Document(
                source="docs/auth.md",
                content="# Auth\n\nAuthenticate with OAuth tokens.\n\n## Refresh\n\nRefresh tokens before expiry.",
                metadata={"format": "markdown"},
            ),
            Document(
                source="docs/config.md",
                content="# Config\n\nSet query.default_budget in docmancer.yaml.",
                metadata={"format": "markdown"},
            ),
        ],
        recreate=True,
    )
    return agent


















def test_offline_retrieval_eval_tiny_corpus(tmp_path):
    agent = _agent(tmp_path)
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "auth",
                        "query": "OAuth tokens",
                        "taxonomy_class": "exact_api_signature",
                        "expected_sources": [{"source": "auth.md", "title": "Auth"}],
                    },
                    {
                        "id": "config",
                        "query": "query.default_budget",
                        "taxonomy_class": "config_key_cli_flag",
                        "expected_sources": [{"source": "config.md", "title": "Config"}],
                    },
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=agent.config, limit=5)

    assert report["metrics"]["queries"] == 2
    assert report["metrics"]["hit_at"]["5"] == 1.0
    assert report["metrics"]["mrr"] > 0
    assert "quality" in report["metrics"]


def test_eval_scores_facts_forbidden_versions_and_diversity(tmp_path):
    agent = _agent(tmp_path)
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "auth",
                        "query": "OAuth tokens",
                        "taxonomy_class": "exact_api_signature",
                        "expected_sources": ["auth.md"],
                        "required_facts": ["OAuth tokens"],
                        "forbidden_versions": ["Riverpod 3.0"],
                        "forbidden_sources": ["missing.md"],
                    }
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=agent.config, limit=5)
    item = report["items"][0]

    assert item["required_facts"] == {"OAuth tokens": True}
    assert item["required_facts_passed"] is True
    assert item["forbidden_checks_passed"] is True
    assert item["token_metrics"]["docmancer_tokens"] > 0
    assert "unique_sources_at_5" in item["source_diversity"]
    assert "snippet_present_at_5" in item["snippet_presence"]
    assert item["locale_contamination"]["locale_contamination_count"] == 0


def test_eval_reports_code_snippet_presence(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [
            Document(
                source="docs/testing.md",
                content="# Testing\n\n```python\nfrom fastapi.testclient import TestClient\nclient = TestClient(app)\n```",
                metadata={"format": "markdown"},
            )
        ],
        recreate=True,
    )
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "testing",
                        "query": "fastapi TestClient example",
                        "taxonomy_class": "code_example",
                        "expected_sources": ["testing.md"],
                    }
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=config, limit=5)

    assert report["items"][0]["snippet_presence"]["snippet_present_at_5"] is True
    assert report["items"][0]["results"][0]["has_code_snippet"] is True
    assert report["items"][0]["snippet_relevance"]["snippet_relevance_at_1"] is True
    assert report["items"][0]["snippet_relevance"]["has_directly_usable_snippet"] is True
    assert report["metrics"]["quality"]["snippet_present_at_5_rate"] == 1.0


def test_eval_reports_flattened_code_snippet_presence(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [
            Document(
                source="docs/family.md",
                content=(
                    "# Family\n\n"
                    "final userProvider = FutureProvider.family<User, String>((ref, id) async {\n\n"
                    "final response = await dio.get('https://api.example.com/users/$id');\n\n"
                    "return User.fromJson(response.data);\n\n"
                    "});"
                ),
                metadata={"format": "markdown"},
            )
        ],
        recreate=True,
    )
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "family",
                        "query": "FutureProvider family userProvider example",
                        "taxonomy_class": "code_example",
                        "expected_sources": ["family.md"],
                    }
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=config, limit=5)

    assert report["items"][0]["snippet_presence"]["snippet_present_at_5"] is True
    assert report["items"][0]["results"][0]["has_code_snippet"] is True


def test_eval_flags_forbidden_versions(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(source="https://riverpod.dev/docs/whats_new", content="# What's new\n\nRiverpod 3.0 changed APIs.", metadata={"format": "markdown"})],
        recreate=True,
    )
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "forbidden",
                        "query": "Riverpod changed APIs",
                        "taxonomy_class": "migration_version_specific",
                        "forbidden_versions": ["Riverpod 3.0"],
                    }
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=config, limit=5)

    assert report["items"][0]["forbidden_checks_passed"] is False
    assert report["items"][0]["forbidden_version_hits"][0]["versions"] == ["Riverpod 3.0"]


def test_eval_flags_forbidden_version_metadata(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(source="https://pub.dev/documentation/go_router/15.0.0/", content="# GoRouter\n\nGoRouter APIs.", metadata={"format": "markdown", "version": "15.0.0"})],
        recreate=True,
    )
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "versioned",
                        "query": "GoRouter APIs",
                        "taxonomy_class": "exact_api_signature",
                        "version_policy": "exact",
                        "project_context": {"ecosystem": "pub", "library": "go_router", "version": "14.8.1"},
                    }
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=config, limit=5)
    hit = report["items"][0]["forbidden_version_hits"][0]

    assert hit["versions"] == ["15.0.0"]
    assert hit["expected_version"] == "14.8.1"


def test_eval_reports_unknown_version_for_exact_policy(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(source="https://pub.dev/documentation/go_router/latest/", content="# GoRouter\n\nGoRouter APIs.", metadata={"format": "markdown"})],
        recreate=True,
    )
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "unknown-version",
                        "query": "GoRouter APIs",
                        "taxonomy_class": "exact_api_signature",
                        "version_policy": "exact",
                        "project_context": {"ecosystem": "pub", "library": "go_router", "version": "14.8.1"},
                    }
                ]
            }
        )
    )

    report = run_retrieval_eval(dataset_path=str(dataset), agent=agent, config=config, limit=5)

    assert report["items"][0]["unknown_version_hits"][0]["expected_version"] == "14.8.1"
    assert report["items"][0]["explain_context"]["explain_has_selected_sources"] is True
    assert report["items"][0]["explain_context"]["explain_has_rejected_or_risky_sources"] is True


def test_source_health_report_counts_sparse_sections(tmp_path):
    agent = _agent(tmp_path)

    report = source_health_report(agent)

    assert report["sources_count"] == 2
    assert report["sections_count"] >= 2
    assert "sparse_sections" in report


def test_eval_cli_json_report(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(source="docs/auth.md", content="# Auth\n\nAuthenticate with OAuth tokens.", metadata={"format": "markdown"})],
        recreate=True,
    )
    config_path = tmp_path / "docmancer.yaml"
    config_path.write_text(yaml.safe_dump(config.model_dump()))
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "id": "auth",
                        "query": "OAuth tokens",
                        "taxonomy_class": "exact_api_signature",
                        "expected_sources": ["auth.md"],
                    }
                ]
            }
        )
    )

    result = CliRunner().invoke(cli, ["--config", str(config_path), "eval", str(dataset), "--format", "json", "--source-health"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["metrics"]["hit_at"]["5"] == 1.0
    assert payload["source_health"]["sources_count"] == 1


def test_list_and_inspect_operational_state(tmp_path):
    config = _config(tmp_path)
    agent = DocmancerAgent(config=config)
    agent.ingest_documents(
        [Document(source="docs/auth.md", content="# Auth\n\nAuthenticate with OAuth tokens.", metadata={"format": "markdown"})],
        recreate=True,
        with_vectors=False,
    )
    config_path = tmp_path / "docmancer.yaml"
    config_path.write_text(yaml.safe_dump(config.model_dump()))

    list_result = CliRunner().invoke(cli, ["--config", str(config_path), "list", "--format", "json"])

    assert list_result.exit_code == 0, list_result.output
    cards = json.loads(list_result.output)
    assert cards[0]["source"] == "docs/auth.md"
    assert cards[0]["status"] in {"ready", "degraded"}
    assert "next_action" in cards[0]

    inspect_result = CliRunner().invoke(cli, ["--config", str(config_path), "inspect", "auth.md", "--json"])

    assert inspect_result.exit_code == 0, inspect_result.output
    card = json.loads(inspect_result.output)
    assert card["source"] == "docs/auth.md"
    assert "details" in card
