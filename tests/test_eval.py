import json

import yaml
from click.testing import CliRunner

from docmancer.agent import DocmancerAgent
from docmancer.cli.__main__ import cli
from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document
from docmancer.eval.health import source_health_report
from docmancer.eval.metrics import hit_at_k, latency_percentile_ms, mrr
from docmancer.eval.runner import run_retrieval_eval
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


def test_metric_formula_unit_tests():
    relevance = [False, True, False]
    assert hit_at_k(relevance, 1) == 0.0
    assert hit_at_k(relevance, 2) == 1.0
    assert mrr(relevance) == 0.5
    assert latency_percentile_ms([10, 20, 30, 40], 95) == 40


def test_golden_dataset_schema_loads_yaml(tmp_path):
    dataset = tmp_path / "golden.yaml"
    dataset.write_text(
        yaml.safe_dump(
            {
                "corpus_snapshot": "tiny-v1",
                "items": [
                    {
                        "id": "q1",
                        "query": "OAuth tokens",
                        "taxonomy_class": "exact_api_signature",
                        "expected_sources": ["docs/auth.md"],
                    }
                ],
            }
        )
    )

    loaded = load_golden_dataset(str(dataset))

    assert loaded.corpus_snapshot == "tiny-v1"
    assert loaded.items[0].expected_sources[0].source == "docs/auth.md"


def test_trace_schema_validation():
    trace = build_explain_trace(
        query="OAuth tokens",
        selected_mode="lexical",
        chunks=[],
        limit=5,
        budget=1200,
        expand=None,
        latency_ms=1.0,
    )

    validate_explain_trace(trace)
    assert trace["query_normalization"]["normalized"] == "oauth tokens"


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
    assert item["locale_contamination"]["locale_contamination_count"] == 0


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
