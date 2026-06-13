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


def test_metric_formula_unit_tests():
    relevance = [False, True, False]
    assert hit_at_k(relevance, 1) == 0.0
    assert hit_at_k(relevance, 2) == 1.0
    assert mrr(relevance) == 0.5
    assert latency_percentile_ms([10, 20, 30, 40], 95) == 40


def test_eval_quality_metrics_use_canonical_sources():
    class Chunk:
        def __init__(self, source, canonical_url=None):
            self.source = source
            self.metadata = {"canonical_url": canonical_url} if canonical_url else {}

    chunks = [
        Chunk("https://example.com/docs?page=1", "https://example.com/docs"),
        Chunk("https://example.com/docs?page=2", "https://example.com/docs"),
        Chunk("https://example.com/fr/docs", "https://example.com/fr/docs"),
    ]

    assert source_diversity_metrics(chunks, k=3) == {"unique_sources_at_3": 2, "redundancy_rate_at_3": 0.3333}
    assert locale_contamination(chunks) == {
        "locale_contamination_count": 1,
        "locale_contamination_sources": ["https://example.com/fr/docs"],
    }


def test_eval_aggregates_quality_metrics():
    items = [
        {
            "source_diversity": {"unique_sources_at_5": 5, "redundancy_rate_at_5": 0.0},
            "snippet_presence": {"snippet_present_at_5": True, "snippet_sections_at_5": 2},
            "locale_contamination": {"locale_contamination_count": 0},
        },
        {
            "source_diversity": {"unique_sources_at_5": 3, "redundancy_rate_at_5": 0.4},
            "snippet_presence": {"snippet_present_at_5": False, "snippet_sections_at_5": 0},
            "locale_contamination": {"locale_contamination_count": 2},
        },
    ]

    assert aggregate_quality_metrics(items, k=5) == {
        "unique_sources_at_5_avg": 4.0,
        "redundancy_rate_at_5_avg": 0.2,
        "snippet_present_at_5_rate": 0.5,
        "snippet_sections_at_5_avg": 1.0,
        "locale_contamination_count": 2,
        "locale_contamination_rate": 0.5,
    }


def test_task_context_benchmark_reports_cold_warm_and_context7_lanes():
    scenarios = [{"id": "repo-rule-version", "description": "project rule plus exact dependency docs"}]
    report = run_task_context_benchmark(
        scenarios=scenarios,
        runners={
            "context7-only": lambda scenario: {
                "task_completion": True,
                "tests_passed": False,
                "wrong_version_api_usage": True,
                "project_rule_violation": True,
                "docs_tool_calls": 1,
                "total_docs_tokens": 1400,
                "correction_loops": 1,
            },
            "docmancer-cold": lambda scenario: {
                "task_completion": True,
                "tests_passed": True,
                "wrong_version_api_usage": False,
                "project_rule_violation": False,
                "docs_tool_calls": 3,
                "total_docs_tokens": 900,
                "correction_loops": 0,
            },
            "docmancer-warm": lambda scenario: {
                "task_completion": True,
                "tests_passed": True,
                "wrong_version_api_usage": False,
                "project_rule_violation": False,
                "docs_tool_calls": 1,
                "total_docs_tokens": 700,
                "correction_loops": 0,
            },
        },
    )

    assert report["benchmark_type"] == "task_context"
    assert report["lanes"] == ["context7-only", "docmancer-cold", "docmancer-warm"]
    assert report["metrics"]["context7-only"]["wrong_version_api_usage_rate"] == 1.0
    assert report["metrics"]["docmancer-warm"]["tests_passed_rate"] == 1.0
    assert "wall_clock_ms" in report["items"][0]["lanes"]["docmancer-cold"]


def test_eval_counts_snippet_presence():
    class Chunk:
        def __init__(self, snippets=None):
            self.metadata = {"code_snippets": snippets or []}

    assert snippet_presence_metrics([Chunk([{"language": "py", "code": "print(1)"}]), Chunk()], k=2) == {
        "snippet_sections_at_2": 1,
        "snippet_present_at_2": True,
    }


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


def test_trace_includes_source_version_snippet_and_degraded_fields():
    class Chunk:
        source = "https://pub.dev/documentation/go_router/14.8.1/"
        score = 1.0
        metadata = {
            "section_id": 42,
            "canonical_url": "https://pub.dev/documentation/go_router/14.8.1/go_router/GoRouter-class.html",
            "source_class": "library_docs",
            "ecosystem": "pub",
            "library": "go_router",
            "version": "14.8.1",
            "version_source": "lockfile_exact",
            "has_code_snippet": True,
        }

    trace = build_explain_trace(
        query="GoRouter example",
        selected_mode="hybrid/dense_degraded",
        chunks=[Chunk()],
        limit=5,
        budget=1200,
        expand=None,
        failures={"sparse": "not configured"},
    )

    validate_explain_trace(trace)
    result = trace["results"][0]
    assert result["source_class"] == "library_docs"
    assert result["ecosystem"] == "pub"
    assert result["library"] == "go_router"
    assert result["version"] == "14.8.1"
    assert result["version_source"] == "lockfile_exact"
    assert result["has_code_snippet"] is True
    assert trace["warnings"] == [{"kind": "degraded_retrieval", "sources": ["sparse"]}]


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
