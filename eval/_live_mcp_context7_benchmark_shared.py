from __future__ import annotations

import argparse

import asyncio

import dataclasses

import json

import os

import re

import shutil

import tempfile

import time

import traceback

from dataclasses import dataclass, field

from datetime import datetime, timezone

from pathlib import Path

from typing import Any

from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

RESULTS_ROOT = ROOT / "eval" / "results" / "live"

TIMEOUT_REFRESH_SECONDS = 300

TIMEOUT_QUERY_SECONDS = 120

@dataclass
class BenchmarkCase:
    id: str
    query: str
    suite: str
    library: str | None = None
    ecosystem: str | None = None
    version: str | None = None
    source_type: str | None = None
    docs_url: str | None = None
    expected_sources: list[str] = field(default_factory=list)
    forbidden_sources: list[str] = field(default_factory=list)
    expected_domains: list[str] = field(default_factory=list)
    forbidden_domains: list[str] = field(default_factory=list)
    expected_source_patterns: list[str] = field(default_factory=list)
    expected_doc_scope: str | None = None
    expected_facts: list[str] = field(default_factory=list)
    expected_symbols: list[str] = field(default_factory=list)
    expected_languages: list[str] = field(default_factory=list)
    context7_library_id: str | None = None
    not_applicable_for: list[str] = field(default_factory=list)
    mode: str | None = None

PUBLIC_DOCS_CASES: list[BenchmarkCase] = [
    BenchmarkCase(id="fastapi_depends",
        query="FastAPI Depends in path operations with dependency function and query parameters",
        suite="public-docs", library="fastapi", ecosystem="python",
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="fastapi_http_exception",
        query="FastAPI raise HTTPException with status_code and detail for a 404 error",
        suite="public-docs", library="fastapi", ecosystem="python",
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="fastapi_testclient",
        query="FastAPI test app with fastapi.testclient.TestClient client and pytest assertions",
        suite="public-docs", library="fastapi", ecosystem="python",
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="fastapi_background_tasks",
        query="FastAPI BackgroundTasks usage and dependency injection",
        suite="public-docs", library="fastapi", ecosystem="python",
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="click_command_group",
        query="Click command group with subcommands and options",
        suite="public-docs", library="click", ecosystem="python",
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["click"],
        context7_library_id="/pallets/click"),
    BenchmarkCase(id="click_options",
        query="Click option decorator with types, prompts, and defaults",
        suite="public-docs", library="click", ecosystem="python",
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["click"],
        context7_library_id="/pallets/click"),
    BenchmarkCase(id="click_callbacks",
        query="Click parameter callbacks and validation patterns",
        suite="public-docs", library="click", ecosystem="python",
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["click"],
        context7_library_id="/pallets/click"),
    BenchmarkCase(id="click_context_passing",
        query="Click context passing with pass_context and ensure_object",
        suite="public-docs", library="click", ecosystem="python",
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_source_patterns=["click"],
        context7_library_id="/pallets/click"),
    BenchmarkCase(id="riverpod_autodispose",
        query="Riverpod autoDispose modifier and ref.onDispose cleanup",
        suite="public-docs", library="riverpod", ecosystem="flutter",
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_source_patterns=["riverpod"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="riverpod_keepalive",
        query="Riverpod keepAlive modifier and ref.keepAlive to prevent disposal",
        suite="public-docs", library="riverpod", ecosystem="flutter",
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_source_patterns=["riverpod"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="riverpod_family",
        query="Riverpod family modifier with parameterized providers",
        suite="public-docs", library="riverpod", ecosystem="flutter",
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_source_patterns=["riverpod"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="riverpod_watch_vs_listen",
        query="Riverpod ref.watch vs ref.listen differences and AsyncValue handling",
        suite="public-docs", library="riverpod", ecosystem="flutter",
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_source_patterns=["riverpod"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="riverpod_asyncnotifier_migration",
        query="Riverpod AsyncNotifier migration from StateNotifier pattern",
        suite="public-docs", library="riverpod", ecosystem="flutter",
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_source_patterns=["riverpod"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="bloc_provider",
        query="Flutter BlocProvider to provide a bloc to the widget tree",
        suite="public-docs", library="flutter_bloc", ecosystem="flutter",
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_source_patterns=["bloc"],
        context7_library_id="/felangel/bloc"),
    BenchmarkCase(id="bloc_builder",
        query="Flutter BlocBuilder with builder and buildWhen for conditional rebuilds",
        suite="public-docs", library="flutter_bloc", ecosystem="flutter",
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_source_patterns=["bloc"],
        context7_library_id="/felangel/bloc"),
    BenchmarkCase(id="bloc_listener",
        query="Flutter BlocListener with listener and listenWhen for side effects",
        suite="public-docs", library="flutter_bloc", ecosystem="flutter",
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_source_patterns=["bloc"],
        context7_library_id="/felangel/bloc"),
    BenchmarkCase(id="bloc_multi_provider",
        query="Flutter MultiBlocProvider combining multiple blocs",
        suite="public-docs", library="flutter_bloc", ecosystem="flutter",
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_source_patterns=["bloc"],
        context7_library_id="/felangel/bloc"),
]

PROJECT_DOCS_CASES: list[BenchmarkCase] = [
    BenchmarkCase(id="project_lifecycle",
        query="How is the project docs lifecycle in DocAtlas?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"]),
    BenchmarkCase(id="source_isolation",
        query="How does DocAtlas isolate library docs from project docs?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["CHANGELOG.md", "docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project"),
    BenchmarkCase(id="trust_contract",
        query="How does the DocAtlas Trust Contract work?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project"),
    BenchmarkCase(id="sync_vs_ingest",
        query="How does sync_project_docs differ from ingest_project_docs?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project"),
    BenchmarkCase(id="risky_rejected_docs",
        query="Which docs sources are considered risky or rejected in DocAtlas?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project"),
    BenchmarkCase(id="v1_source_isolation",
        query="What changed in v1.0.0 for source isolation?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["CHANGELOG.md", "docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project"),
]

EXACT_VERSION_CASES: list[BenchmarkCase] = [
    BenchmarkCase(id="exact_fastapi_version",
        query="FastAPI Depends with exact version 0.115.13",
        suite="exact-version", library="fastapi", ecosystem="python", version="0.115.13",
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi/0.115.13"),
    BenchmarkCase(id="exact_riverpod_version",
        query="Riverpod family modifier with exact version",
        suite="exact-version", library="riverpod", ecosystem="flutter", version="2.6.1",
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        expected_source_patterns=["riverpod"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="exact_flutter_bloc_version",
        query="Flutter BlocProvider with exact version",
        suite="exact-version", library="flutter_bloc", ecosystem="flutter", version="9.1.0",
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        expected_source_patterns=["bloc"],
        context7_library_id="/felangel/bloc"),
    BenchmarkCase(id="exact_click_version",
        query="Click command group with exact version 8.1.x",
        suite="exact-version", library="click", ecosystem="python", version="8.1.8",
        expected_domains=["click.palletsprojects.com", "github.com"],
        expected_source_patterns=["click"],
        context7_library_id="/pallets/click"),
    BenchmarkCase(id="exact_pydantic_version",
        query="Pydantic BaseModel field validators with exact version",
        suite="exact-version", library="pydantic", ecosystem="python", version="2.11.1",
        expected_domains=["docs.pydantic.dev", "github.com"],
        expected_source_patterns=["pydantic"],
        context7_library_id="/pydantic/pydantic"),
    BenchmarkCase(id="exact_go_router_version",
        query="GoRouter route configuration and navigation with exact version",
        suite="exact-version", library="go_router", ecosystem="flutter", version="14.8.1",
        expected_domains=["pub.dev", "api.flutter.dev", "github.com"],
        expected_source_patterns=["go_router"],
        context7_library_id="/websites/pub_dev_packages_go_router"),
]

UNIFIED_CONTEXT_CASES: list[BenchmarkCase] = [
    BenchmarkCase(id="unified_project_auto",
        query="How does DocAtlas isolate project docs from library docs?",
        suite="unified-context", mode="auto",
        not_applicable_for=["context7"], expected_doc_scope="project",
        expected_sources=["docs/", "CHANGELOG.md"]),
    BenchmarkCase(id="unified_dependency_auto",
        query="How do I use anyhow Context for the dependency version in this project?",
        suite="unified-context", ecosystem="rust", mode="auto",
        not_applicable_for=["context7"], expected_source_patterns=["anyhow"]),
    BenchmarkCase(id="unified_library_only",
        query="How do I use FastAPI Depends?",
        suite="unified-context", library="fastapi", ecosystem="python", mode="auto",
        expected_domains=["fastapi.tiangolo.com", "github.com"], expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="unified_mixed_partial_confirmation",
        query="How does this project use FastAPI dependency injection?",
        suite="unified-context", library="definitely_unindexed_unified_pr5_lib", ecosystem="python", mode="auto",
        not_applicable_for=["context7"], expected_doc_scope="project",
        expected_source_patterns=["docatlas"]),
    BenchmarkCase(id="unified_latest_fallback",
        query="FastAPI Depends with unsupported exact version and latest fallback",
        suite="unified-context", library="fastapi", ecosystem="python", version="0.115.0", mode="auto",
        expected_domains=["fastapi.tiangolo.com", "github.com"], expected_source_patterns=["fastapi"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="unified_dependency",
        query="How do I use anyhow Context with an explicit dependency request?",
        suite="unified-context", library="anyhow", ecosystem="rust", version="1.0.86", mode="dependency",
        not_applicable_for=["context7"], expected_source_patterns=["anyhow"]),
]

SNIPPET_FIRST_CASES: list[BenchmarkCase] = [
    BenchmarkCase(id="fastapi_depends_snippet",
        query="How do I use FastAPI Depends?",
        suite="snippet-first", library="fastapi", ecosystem="python",
        expected_domains=["fastapi.tiangolo.com"], forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "bloclibrary.dev"],
        expected_source_patterns=["fastapi"], expected_symbols=["Depends"], expected_languages=["python"],
        context7_library_id="/fastapi/fastapi"),
    BenchmarkCase(id="click_command_group_snippet",
        query="Show a Click command group example.",
        suite="snippet-first", library="click", ecosystem="python", docs_url="https://click.palletsprojects.com/",
        expected_domains=["click.palletsprojects.com"], forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "bloclibrary.dev"],
        expected_source_patterns=["click"], expected_symbols=["@click.group", "click.group"], expected_languages=["python"],
        context7_library_id="/pallets/click"),
    BenchmarkCase(id="riverpod_autodispose_snippet",
        query="Riverpod ref.watch provider example.",
        suite="snippet-first", library="riverpod", ecosystem="dart", source_type="web",
        expected_domains=["riverpod.dev", "pub.dev"], forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "bloclibrary.dev"],
        expected_source_patterns=["riverpod"], expected_symbols=["ref.watch"], expected_languages=["dart"],
        context7_library_id="/rrousselgit/riverpod"),
    BenchmarkCase(id="flutter_bloc_provider_snippet",
        query="flutter_bloc BlocProvider example.",
        suite="snippet-first", library="flutter_bloc", ecosystem="dart", source_type="web",
        expected_domains=["bloclibrary.dev", "pub.dev"], forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_source_patterns=["bloc"], expected_symbols=["BlocProvider"], expected_languages=["dart"],
        context7_library_id="/felangel/bloc"),
    BenchmarkCase(id="anyhow_context_snippet",
        query="How do I wrap an error with anyhow Context for the dependency version in this project?",
        suite="snippet-first", ecosystem="rust", mode="auto",
        not_applicable_for=["context7"], expected_domains=["docs.rs"], expected_source_patterns=["anyhow"],
        expected_symbols=["Context", "with_context"], expected_languages=["rust"]),
    BenchmarkCase(id="project_command_snippet",
        query="Show the project test command.",
        suite="snippet-first", mode="project",
        not_applicable_for=["context7"], expected_doc_scope="project", expected_symbols=["uv run pytest"], expected_languages=["bash"]),
    BenchmarkCase(id="mixed_fastapi_project_snippet",
        query="How do I use FastAPI Depends while following this project?",
        suite="snippet-first", library="fastapi", ecosystem="python", mode="auto",
        not_applicable_for=["context7"], expected_domains=["fastapi.tiangolo.com"], expected_source_patterns=["fastapi"],
        expected_symbols=["Depends"], expected_languages=["python"]),
]

QUICK_CASES: list[str] = [
    "fastapi_depends", "click_command_group", "riverpod_autodispose",
    "bloc_provider", "project_lifecycle", "exact_fastapi_version",
    "unified_project_auto", "unified_dependency_auto", "unified_library_only", "unified_mixed_partial_confirmation", "unified_latest_fallback", "unified_dependency",
    "fastapi_depends_snippet", "click_command_group_snippet", "riverpod_autodispose_snippet", "flutter_bloc_provider_snippet", "anyhow_context_snippet", "project_command_snippet", "mixed_fastapi_project_snippet",
]

__all__=[n for n in globals() if not n.startswith("__")]
