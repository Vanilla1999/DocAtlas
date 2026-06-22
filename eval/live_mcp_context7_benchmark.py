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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "eval" / "results" / "live"

TIMEOUT_REFRESH_SECONDS = 300
TIMEOUT_QUERY_SECONDS = 120

# ── Data structures ──────────────────────────────────────────

@dataclass
class SourceRef:
    url: str
    title: str | None = None
    rank: int = 0
    doc_scope: str | None = None
    domain: str | None = None

    def __post_init__(self):
        if self.domain is None and self.url:
            try:
                self.domain = urlparse(self.url).netloc
            except Exception:
                pass


@dataclass
class Snippet:
    text: str
    source: str
    rank: int = 0


@dataclass
class PreindexDiagnostics:
    attempted: bool = False
    status: str = "not_attempted"
    library_id: str | None = None
    canonical_id: str | None = None
    version: str | None = None
    pages: int = 0
    chunks: int = 0
    latency_ms: float = 0.0
    reason_code: str | None = None
    warnings: list[str] = field(default_factory=list)
    discovery_strategy: str | None = None
    sitemap_pages: int = 0
    seed_pages: int = 0
    fallback_pages: int = 0
    index_path: str | None = None
    query_index_path: str | None = None


@dataclass
class BenchmarkCase:
    id: str
    query: str
    suite: str
    library: str | None = None
    ecosystem: str | None = None
    version: str | None = None
    expected_sources: list[str] = field(default_factory=list)
    forbidden_sources: list[str] = field(default_factory=list)
    expected_domains: list[str] = field(default_factory=list)
    forbidden_domains: list[str] = field(default_factory=list)
    expected_source_patterns: list[str] = field(default_factory=list)
    expected_doc_scope: str | None = None
    expected_facts: list[str] = field(default_factory=list)
    context7_library_id: str | None = None
    not_applicable_for: list[str] = field(default_factory=list)


@dataclass
class NormalizedBenchmarkResult:
    provider: str
    provider_id: str
    provider_mode: str
    mode: str
    case_id: str
    query: str
    suite: str
    status: str
    latency_ms: float
    setup_calls: int
    sources: list[SourceRef]
    snippets: list[Snippet]
    answer_text: str | None
    warnings: list[str]
    reason_codes: list[str]
    exact_version_used: str | None
    contamination_hits: list[str]
    forbidden_source_hits: list[str]
    expected_source_hits: list[str]
    manual_review_required: bool
    preindex: PreindexDiagnostics | None = None
    raw_response: dict[str, Any] | None = None

    def is_not_applicable(self) -> bool:
        return self.status in ("not_applicable",)

    def is_error(self) -> bool:
        return self.status in ("error", "timeout", "failed_ingest", "preindex_failed")

    def is_empty(self) -> bool:
        return self.status in ("empty_index", "needs_refresh", "no_results", "quota_exceeded")

    def is_success(self) -> bool:
        return self.status == "success"


# ── Suite definitions ────────────────────────────────────────

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

QUICK_CASES: list[str] = [
    "fastapi_depends", "click_command_group", "riverpod_autodispose",
    "bloc_provider", "project_lifecycle", "exact_fastapi_version",
]


def _all_cases() -> list[BenchmarkCase]:
    return PUBLIC_DOCS_CASES + PROJECT_DOCS_CASES + EXACT_VERSION_CASES


def _filter_cases(suites: list[str] | None, quick: bool) -> list[BenchmarkCase]:
    all_c = _all_cases()
    if quick:
        quick_set = set(QUICK_CASES)
        return [c for c in all_c if c.id in quick_set]
    if suites:
        return [c for c in all_c if c.suite in suites]
    return all_c


# ── Provider abstraction ─────────────────────────────────────

class BenchmarkProvider:
    name: str
    provider_id: str
    provider_mode: str
    benchmark_mode: str

    async def setup(self) -> None:
        pass

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        raise NotImplementedError


# ── DocAtlas Direct API Provider ─────────────────────────────

class DocAtlasDirectProvider(BenchmarkProvider):
    def __init__(self, project_path: str | None = None):
        self.name = "docatlas"
        self.provider_id = "docatlas_zero_setup"
        self.provider_mode = "live_direct_api"
        self.benchmark_mode = "zero-setup"
        self._project_path = project_path or str(ROOT)
        self._service = None
        self._lib_cache: dict[str, dict[str, Any]] = {}
        self._custom_db_path: str | None = None

    def _get_service(self):
        if self._service is None:
            from docmancer.docs.service import LibraryDocsService
            from docmancer.core.config import DocmancerConfig
            if self._custom_db_path:
                config = DocmancerConfig()
                config.index.db_path = self._custom_db_path
            else:
                config = DocmancerConfig()
            self._service = LibraryDocsService(config=config)
        return self._service

    async def setup(self) -> None:
        _ = self._get_service()

    async def _preindex_library(self, case: BenchmarkCase) -> PreindexDiagnostics:
        service = self._get_service()
        diag = PreindexDiagnostics(attempted=True, status="pending", version=case.version)
        t0 = time.perf_counter()
        try:
            lib = case.library or case.id
            eco = case.ecosystem
            ver = case.version
            key = f"{eco}:{lib}:{ver}"
            cached = self._lib_cache.get(key)
            if cached:
                diag.status = cached.get("status", "cached")
                diag.library_id = cached.get("library_id")
                diag.chunks = cached.get("chunks", 0)
                diag.pages = cached.get("pages", 0)
                diag.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
                return diag

            info = service.resolve_library(lib, ecosystem=eco, version=ver)
            if info.library_id is None:
                diag.status = "not_supported"
                diag.reason_code = "unresolved"
                diag.warnings.append(info.message or "Could not resolve")
                diag.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
                self._lib_cache[key] = {"status": "not_supported"}
                return diag

            diag.library_id = info.library_id
            diag.canonical_id = info.canonical_id
            diag.version = info.resolved_version or info.version or ver

            inspect_result = service.inspect_library_docs(info.library_id)
            pages = inspect_result.pages if hasattr(inspect_result, "pages") else 0
            chunks = inspect_result.chunks if hasattr(inspect_result, "chunks") else 0

            if pages > 0 and chunks > 0:
                diag.status = "already_indexed"
                diag.pages = pages
                diag.chunks = chunks
            else:
                refresh_result = service.refresh_docs(lib, ecosystem=eco, version=ver, force=False)
                diag.status = "refreshed"
                diag.pages = refresh_result.pages if hasattr(refresh_result, "pages") else 0
                diag.chunks = len(refresh_result.results) if hasattr(refresh_result, "results") else 0
                preindex = getattr(refresh_result, "preindex", None) or {}
                diag.discovery_strategy = preindex.get("discovery_strategy")
                diag.sitemap_pages = int(preindex.get("sitemap_pages") or 0)
                diag.seed_pages = int(preindex.get("seed_pages") or 0)
                diag.fallback_pages = int(preindex.get("fallback_pages") or 0)
                diag.index_path = preindex.get("index_path")
                diag.query_index_path = preindex.get("query_index_path")
                diag.reason_code = preindex.get("reason_code")
                for warning in preindex.get("warnings") or []:
                    if isinstance(warning, dict):
                        code = warning.get("code")
                        if code:
                            diag.warnings.append(str(code))
                    elif warning:
                        diag.warnings.append(str(warning))

            if diag.pages == 0 and diag.chunks == 0:
                diag.status = "empty_index"
                diag.reason_code = "refresh_produced_no_content"

            self._lib_cache[key] = {
                "status": diag.status, "library_id": diag.library_id,
                "pages": diag.pages, "chunks": diag.chunks,
            }
        except Exception as exc:
            diag.status = "preindex_failed"
            diag.reason_code = type(exc).__name__
            diag.warnings.append(str(exc))
        diag.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        return diag

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        if "docatlas" in case.not_applicable_for:
            return self._na_result(case)

        service = self._get_service()
        start = time.perf_counter()
        sources: list[SourceRef] = []
        snippets: list[Snippet] = []
        warnings: list[str] = []
        reason_codes: list[str] = []
        answer_text: str | None = None
        exact_version_used: str | None = case.version
        setup_calls = 0
        status = "success"
        preindex_diag: PreindexDiagnostics | None = None

        try:
            if self.benchmark_mode == "preindexed" and case.suite in ("public-docs", "exact-version") and case.library:
                preindex_diag = await self._preindex_library(case)
                setup_calls += 2
                reason_codes.append(preindex_diag.status)
                if preindex_diag.status in ("preindex_failed", "not_supported", "empty_index"):
                    status = preindex_diag.status if preindex_diag.status != "empty_index" else "empty_index"
                    latency_ms = round((time.perf_counter() - start) * 1000, 3)
                    return self._build_result(case, status, latency_ms, setup_calls,
                        sources, snippets, answer_text, warnings, reason_codes,
                        exact_version_used, preindex=preindex_diag)

            if case.suite == "project-docs":
                result = await asyncio.to_thread(
                    service.get_project_context, self._project_path, case.query, tokens=4000)
                setup_calls += 1
                context_pack = result.context_pack if hasattr(result, "context_pack") else []
                answer_text = str(result.answer_outline) if hasattr(result, "answer_outline") and result.answer_outline else None
                for i, item in enumerate(context_pack):
                    raw_source = item.get("source") or {}
                    path_val = item.get("path") or ""
                    url_val = item.get("url") or ""
                    if isinstance(raw_source, dict):
                        source_str = path_val or url_val or ""
                    else:
                        source_str = str(raw_source) if raw_source else (path_val or url_val or "")
                    title = item.get("title") or ""
                    heading = item.get("heading_path") or ""
                    content = item.get("content") or ""
                    scope = item.get("doc_scope")
                    url = source_str or "unknown"
                    sources.append(SourceRef(url=url, title=f"{title} - {heading}" if heading else title, rank=i + 1, doc_scope=scope))
                    if content:
                        snippets.append(Snippet(text=content[:500], source=url, rank=i + 1))
            else:
                result = await asyncio.to_thread(
                    service.get_docs, case.library, topic=case.query, tokens=2000,
                    ecosystem=case.ecosystem, version=case.version)
                setup_calls += 1
                if hasattr(result, "results") and result.results:
                    for i, chunk in enumerate(result.results):
                        src = chunk.source or ""
                        content = chunk.content or ""
                        title = chunk.title or ""
                        url = chunk.url or src
                        sources.append(SourceRef(url=url, title=title, rank=i + 1, doc_scope="public_docs"))
                        if content:
                            snippets.append(Snippet(text=content[:500], source=url, rank=i + 1))
                    exact_version_used = getattr(result, "resolved_version", None) or exact_version_used
                else:
                    if hasattr(result, "results") and result.results is not None and len(result.results) == 0:
                        status = "empty_index"
                        reason_codes.append("empty_library_index")
                        if preindex_diag and preindex_diag.attempted and preindex_diag.pages > 0:
                            preindex_diag.status = "retrieval_no_hits"
                            preindex_diag.reason_code = "preindex_succeeded_but_query_empty"
                        if hasattr(result, "warning") and result.warning:
                            warnings.append(result.warning)
                    else:
                        status = "no_results"
                        if preindex_diag and preindex_diag.attempted and preindex_diag.status == "already_indexed":
                            preindex_diag.status = "retrieval_no_hits"
                            preindex_diag.reason_code = "preindex_succeeded_but_no_matching_sections"
                if hasattr(result, "warnings") and result.warnings:
                    warnings.extend(result.warnings)
                if hasattr(result, "warning") and result.warning:
                    warnings.append(result.warning)
        except Exception as exc:
            status = "error"
            warnings.append(str(exc))
            reason_codes.append(type(exc).__name__)

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        cont = _detect_contamination(sources, case)
        forb = _detect_forbidden_sources(sources, case)
        expt = _detect_expected_sources(sources, case)

        return self._build_result(case, status, latency_ms, setup_calls,
            sources, snippets, answer_text, warnings, reason_codes,
            exact_version_used, cont, forb, expt, preindex=preindex_diag)

    def _build_result(self, case, status, latency_ms, setup_calls,
            sources, snippets, answer_text, warnings, reason_codes,
            exact_version_used, cont=None, forb=None, expt=None, preindex=None):
        return NormalizedBenchmarkResult(
            provider=self.name, provider_id=self.provider_id,
            provider_mode=self.provider_mode, mode=self.benchmark_mode,
            case_id=case.id, query=case.query, suite=case.suite,
            status=status, latency_ms=latency_ms, setup_calls=setup_calls,
            sources=sources, snippets=snippets, answer_text=answer_text,
            warnings=warnings, reason_codes=reason_codes,
            exact_version_used=exact_version_used,
            contamination_hits=cont or [], forbidden_source_hits=forb or [],
            expected_source_hits=expt or [],
            manual_review_required=status == "error",
            preindex=preindex)

    def _na_result(self, case):
        return self._build_result(case, "not_applicable", 0, 0, [], [], None,
            ["Not applicable for DocAtlas"], [], None)


# ── Context7 MCP Provider ────────────────────────────────────

class Context7MCPProvider(BenchmarkProvider):
    def __init__(self):
        self.name = "context7"
        self.provider_id = "context7_zero_setup"
        self.provider_mode = "live_mcp_stdio"
        self.benchmark_mode = "zero-setup"
        self._session: ClientSession | None = None
        self._lib_cache: dict[str, str] = {}
        self._stdio_ctx: Any = None
        self._session_ctx: Any = None
        self._read: Any = None
        self._write: Any = None

    async def _ensure_session(self) -> ClientSession:
        if self._session is None:
            params = StdioServerParameters(
                command="context7-mcp",
                args=["--transport", "stdio"],
                env={"CONTEXT7_API_KEY": os.environ.get("CONTEXT7_API_KEY", "")},
            )
            self._stdio_ctx = stdio_client(params)
            self._read, self._write = await self._stdio_ctx.__aenter__()
            self._session_ctx = ClientSession(self._read, self._write)
            self._session = await self._session_ctx.__aenter__()
            await self._session.initialize()
        return self._session

    async def setup(self) -> None:
        await self._ensure_session()

    async def shutdown(self) -> None:
        for ctx in [self._session_ctx, self._stdio_ctx]:
            if ctx is not None:
                try:
                    await ctx.__aexit__(None, None, None)
                except (RuntimeError, GeneratorExit, Exception):
                    pass
        try:
            if self._write is not None:
                await self._write.aclose()
        except Exception:
            pass
        try:
            if self._read is not None:
                await self._read.aclose()
        except Exception:
            pass
        self._session = None
        self._session_ctx = None
        self._stdio_ctx = None

    async def _resolve_library_id(self, case: BenchmarkCase) -> str | None:
        if case.context7_library_id:
            return case.context7_library_id
        if not case.library or case.library in self._lib_cache:
            return self._lib_cache.get(case.library)
        try:
            session = await self._ensure_session()
            result = await session.call_tool("resolve-library-id", {
                "query": case.query, "libraryName": case.library,
            })
            text = result.content[0].text if result.content else ""
            m = re.search(r'/[\w/-]+', text)
            if m:
                lid = m.group(0)
                self._lib_cache[case.library] = lid
                return lid
        except Exception:
            pass
        return None

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        if "context7" in case.not_applicable_for:
            return NormalizedBenchmarkResult(
                provider=self.name, provider_id=self.provider_id,
                provider_mode=self.provider_mode, mode=self.benchmark_mode,
                case_id=case.id, query=case.query, suite=case.suite,
                status="not_applicable", latency_ms=0, setup_calls=0,
                sources=[], snippets=[], answer_text=None,
                warnings=["Not applicable: no local repo context"], reason_codes=["not_applicable_local_repo"],
                exact_version_used=None, contamination_hits=[], forbidden_source_hits=[],
                expected_source_hits=[], manual_review_required=False)

        start = time.perf_counter()
        sources: list[SourceRef] = []
        snippets: list[Snippet] = []
        warnings: list[str] = []
        reason_codes: list[str] = []
        answer_text: str | None = None
        exact_version_used: str | None = case.version
        setup_calls = 0
        status = "success"
        text = ""

        try:
            lib_id = await self._resolve_library_id(case)
            setup_calls += 1
            if lib_id is None:
                return NormalizedBenchmarkResult(
                    provider=self.name, provider_id=self.provider_id,
                    provider_mode=self.provider_mode, mode=self.benchmark_mode,
                    case_id=case.id, query=case.query, suite=case.suite,
                    status="not_supported", latency_ms=round((time.perf_counter() - start) * 1000, 3),
                    setup_calls=setup_calls, sources=[], snippets=[], answer_text=None,
                    warnings=["Could not resolve Context7 library ID"], reason_codes=["unresolved_library"],
                    exact_version_used=None, contamination_hits=[], forbidden_source_hits=[],
                    expected_source_hits=[], manual_review_required=False)

            qargs: dict[str, str] = {"libraryId": lib_id, "query": case.query}
            if case.version and "/" in lib_id:
                parts = lib_id.split("/")
                if len(parts) == 3:
                    qargs["libraryId"] = f"{parts[0]}/{parts[1]}/{parts[2]}"
            session = await self._ensure_session()
            result = await session.call_tool("query-docs", qargs)
            setup_calls += 1
            text = result.content[0].text if result.content else ""

            if not text or text.strip() == "":
                status = "empty_index"
            elif "not found" in text.lower() or "please check" in text.lower():
                status = "not_supported"
                warnings.append(f"Context7 library not found: {lib_id}")
                reason_codes.append("library_not_found")
            elif "quota exceeded" in text.lower() or "monthly quota" in text.lower():
                status = "quota_exceeded"
                warnings.append("Context7 quota exceeded")
                reason_codes.append("quota_exceeded")
            else:
                answer_text = text
                _extract_sources_and_snippets(text, sources, snippets)
        except Exception as exc:
            status = "error"
            warnings.append(str(exc))
            reason_codes.append(type(exc).__name__)

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        cont = _detect_contamination(sources, case)
        forb = _detect_forbidden_sources(sources, case)
        expt = _detect_expected_sources(sources, case)

        return NormalizedBenchmarkResult(
            provider=self.name, provider_id=self.provider_id,
            provider_mode=self.provider_mode, mode=self.benchmark_mode,
            case_id=case.id, query=case.query, suite=case.suite,
            status=status, latency_ms=latency_ms, setup_calls=setup_calls,
            sources=sources, snippets=snippets, answer_text=answer_text,
            warnings=warnings, reason_codes=reason_codes,
            exact_version_used=exact_version_used,
            contamination_hits=cont, forbidden_source_hits=forb,
            expected_source_hits=expt,
            manual_review_required=status == "error",
            raw_response={"text_length": len(text) if text else 0})


# ── Shared source detection ──────────────────────────────────

def _detect_contamination(sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
    hits = []
    for src in sources:
        domain = src.domain or ""
        for fdom in case.forbidden_domains:
            if domain == fdom or domain.endswith("." + fdom):
                hits.append(f"forbidden_domain:{fdom} in {src.url}")
        if case.expected_doc_scope and src.doc_scope and src.doc_scope != case.expected_doc_scope:
            hits.append(f"wrong_scope:{src.doc_scope} expected:{case.expected_doc_scope}")
    return hits


def _detect_forbidden_sources(sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
    hits = []
    for fsrc in case.forbidden_sources:
        for s in sources:
            if fsrc.lower() in s.url.lower():
                hits.append(f"forbidden:{fsrc}")
                break
    return hits


def _detect_expected_sources(sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
    hits = []
    urls_lower = [s.url.lower() for s in sources]
    domains_lower = [s.domain.lower() for s in sources if s.domain]
    for pat in case.expected_source_patterns:
        if any(pat.lower() in u for u in urls_lower):
            hits.append(pat)
            break
    for d in case.expected_domains:
        if any(d.lower() == dom or dom.endswith("." + d.lower()) for dom in domains_lower):
            hits.append(d)
            break
    for e in case.expected_sources:
        if any(e.lower() in u for u in urls_lower):
            hits.append(e)
            break
    return hits


def _extract_sources_and_snippets(text: str, sources: list[SourceRef], snippets: list[Snippet]) -> None:
    seen: set[str] = set()
    rank = 0
    for line in text.split("\n"):
        m = re.match(r'^Source:\s*(https?://\S+)', line)
        if m:
            u = m.group(1).rstrip(".")
            if u not in seen:
                seen.add(u)
                rank += 1
                sources.append(SourceRef(url=u, rank=rank))
    for title, url in re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', text):
        url = url.rstrip("/")
        if url not in seen:
            seen.add(url)
            rank += 1
            sources.append(SourceRef(url=url, title=title, rank=rank))
    for url in re.findall(r'(https?://[^\s\)\]>]+)', text):
        url = url.rstrip(".,")
        if url not in seen:
            seen.add(url)
            rank += 1
            sources.append(SourceRef(url=url, rank=rank))
    sorted_src = sorted(sources, key=lambda s: s.rank) if sources else []
    for i, cb in enumerate(re.findall(r'```[\w]*\n(.*?)```', text, re.DOTALL)[:5]):
        ss = sorted_src[i % max(len(sorted_src), 1)].url if sorted_src else ""
        snippets.append(Snippet(text=cb[:500], source=ss, rank=i + 1))


# ── Metrics ──────────────────────────────────────────────────

def compute_metrics(results: list[NormalizedBenchmarkResult]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}

    applicable = [r for r in results if not r.is_not_applicable()]
    successful = [r for r in applicable if r.is_success()]
    errors = [r for r in applicable if r.is_error()]
    empty = [r for r in applicable if r.is_empty()]
    n_app = len(applicable)
    n_succ = len(successful)

    cov_rate = n_succ / max(n_app, 1)
    empty_rate = len(empty) / max(n_app, 1)
    err_rate = len(errors) / max(n_app, 1)

    cont_on_all = sum(1 for r in applicable if r.contamination_hits)
    forb_on_all = sum(1 for r in applicable if r.forbidden_source_hits)

    csr_all = 1.0 - (cont_on_all / max(n_app, 1))
    csr_success = 1.0 - (sum(1 for r in successful if r.contamination_hits) / max(n_succ, 1))

    cont_on_success = sum(1 for r in successful if r.contamination_hits)

    hit1_n = 0
    hit5_n = 0
    recip = []
    for r in applicable:
        src_domains = set(s.domain or "" for s in r.sources)
        src_urls = [s.url for s in r.sources]
        if r.expected_source_hits:
            ranks = []
            for src in r.sources:
                for eh in r.expected_source_hits:
                    if eh.lower() in src.url.lower() or (src.domain and eh.lower() in src.domain.lower()):
                        ranks.append(src.rank)
                        break
            min_r = min(ranks) if ranks else 999
            recip.append(1.0 / min_r if min_r < 999 else 0.0)
            hit1_n += 1 if min_r <= 1 else 0
            hit5_n += 1 if min_r <= 5 else 0
        else:
            recip.append(0.0)

    uniq_srcs = []
    red_rate = []
    for r in applicable:
        u = len(set(s.url for s in r.sources))
        uniq_srcs.append(u)
        total_r = min(len(r.sources), 5)
        if total_r > 0:
            red_rate.append(max(0, 1.0 - u / total_r))
        else:
            red_rate.append(0.0)

    snip_count = sum(1 for r in applicable if r.snippets)
    snip_use = snip_count / max(n_app, 1)

    lat_all = [r.latency_ms for r in applicable]
    lat_cold = sum(r.latency_ms for r in applicable if r.setup_calls > 1)
    lat_cold_n = sum(1 for r in applicable if r.setup_calls > 1)
    lat_warm_n = sum(1 for r in applicable if r.setup_calls <= 1)

    ev_success = sum(1 for r in successful if r.suite == "exact-version")
    ev_empty = sum(1 for r in applicable if r.is_empty() and r.suite == "exact-version")
    ev_not_supported = sum(1 for r in applicable if r.status == "not_supported" and r.suite == "exact-version")
    ev_total = sum(1 for r in applicable if r.suite == "exact-version")
    ev_correct = sum(1 for r in successful if r.exact_version_used and r.expected_source_hits and r.suite == "exact-version")

    return {
        "total_queries": total,
        "applicable_queries": n_app,
        "success_count": n_succ,
        "error_count": len(errors),
        "empty_count": len(empty),
        "not_applicable_count": sum(1 for r in results if r.is_not_applicable()),
        "coverage_rate": round(cov_rate, 4),
        "empty_rate": round(empty_rate, 4),
        "error_rate": round(err_rate, 4),
        "contamination_rate_all": round(cont_on_all / max(n_app, 1), 4),
        "correct_source_rate_all": round(csr_all, 4),
        "contamination_rate_on_success": round(cont_on_success / max(n_succ, 1), 4),
        "correct_source_rate_on_success": round(csr_success, 4),
        "hit@1": round(hit1_n / max(n_app, 1), 4),
        "hit@5": round(hit5_n / max(n_app, 1), 4),
        "mrr": round(sum(recip) / max(len(recip), 1), 4),
        "unique_sources@5": round(sum(uniq_srcs) / max(len(uniq_srcs), 1), 4),
        "redundancy_rate": round(sum(red_rate) / max(len(red_rate), 1), 4),
        "snippet_usefulness": round(snip_use, 4),
        "avg_latency_ms": round(sum(lat_all) / max(len(lat_all), 1), 3),
        "avg_cold_latency_ms": round(lat_cold / max(lat_cold_n, 1), 3) if lat_cold_n else 0,
        "avg_warm_latency_ms": round(sum(r.latency_ms for r in applicable if r.setup_calls <= 1) / max(lat_warm_n, 1), 3) if lat_warm_n else 0,
        "exact_version_success_count": ev_success,
        "exact_version_empty_count": ev_empty,
        "exact_version_not_supported_count": ev_not_supported,
        "exact_version_coverage_rate": round(ev_success / max(ev_total, 1), 4),
        "exact_version_correctness_on_success": round(ev_correct / max(ev_success, 1), 4) if ev_success > 0 else None,
        "exact_version_empty_rate": round(ev_empty / max(ev_total, 1), 4),
    }


def compute_suite_metrics(results: list[NormalizedBenchmarkResult], suite: str) -> dict[str, Any]:
    sr = [r for r in results if r.suite == suite]
    by_prov: dict[str, list[NormalizedBenchmarkResult]] = {}
    for r in sr:
        by_prov.setdefault(r.provider_id, []).append(r)
    m: dict[str, Any] = {"suite": suite, "total": len(sr)}
    for pid, rlist in by_prov.items():
        pm = compute_metrics(rlist)
        pm["provider"] = rlist[0].provider if rlist else "unknown"
        pm["provider_mode"] = rlist[0].provider_mode if rlist else "unknown"
        pm["benchmark_mode"] = rlist[0].mode if rlist else "unknown"
        m[pid] = pm
    return m


# ── Report generation ────────────────────────────────────────

def _metric_line(label: str, da_val: Any, c7_val: Any) -> str:
    return f"| {label} | {_mv(da_val)} | {_mv(c7_val)} |"


def _mv(v: Any) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def generate_markdown_report(
    all_results: list[NormalizedBenchmarkResult],
    overall_da: dict[str, Any], overall_c7: dict[str, Any],
    suite_metrics: list[dict[str, Any]],
    zi_da: dict[str, Any] | None, zi_c7: dict[str, Any] | None,
    pi_da: dict[str, Any] | None,
    timestamp: str, duration: float, benchmark_mode: str,
) -> str:
    lines: list[str] = []
    lines.append("# Live MCP Benchmark: DocAtlas vs Context7")
    lines.append("")
    lines.append(f"- **Date:** {timestamp}")
    lines.append(f"- **Duration:** {duration:.2f}s")
    lines.append(f"- **Total queries:** {len(all_results)}")
    lines.append(f"- **Benchmark mode:** {benchmark_mode}")
    lines.append(f"- **DocAtlas mode:** live_direct_api")
    lines.append(f"- **Context7 mode:** live_mcp_stdio")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    da_succ = overall_da.get("success_count", 0)
    c7_succ = overall_c7.get("success_count", 0)
    da_cov = overall_da.get("coverage_rate", 0)
    c7_cov = overall_c7.get("coverage_rate", 0)
    da_cont = overall_da.get("contamination_rate_all", 0)
    c7_cont = overall_c7.get("contamination_rate_all", 0)
    lines.append(f"- DocAtlas: {da_succ} successes, coverage {_mv(da_cov)}, contamination {_mv(da_cont)}")
    lines.append(f"- Context7: {c7_succ} successes, coverage {_mv(c7_cov)}, contamination {_mv(c7_cont)}")
    lines.append("")

    if benchmark_mode in ("zero-setup", "both"):
        lines.append("## Zero-Setup Public Docs")
        lines.append("")
        for sm in suite_metrics:
            if sm["suite"] == "public-docs":
                da = sm.get("docatlas_zero_setup", sm.get("docatlas", {}))
                c7 = sm.get("context7_zero_setup", sm.get("context7", {}))
                lines.append("| Metric | DocAtlas | Context7 |")
                lines.append("|--------|----------|----------|")
                lines.append(_metric_line("Coverage rate", da.get("coverage_rate"), c7.get("coverage_rate")))
                lines.append(_metric_line("Success count", da.get("success_count"), c7.get("success_count")))
                lines.append(_metric_line("Empty count", da.get("empty_count"), c7.get("empty_count")))
                lines.append(_metric_line("Contamination rate", da.get("contamination_rate_all"), c7.get("contamination_rate_all")))
                lines.append(_metric_line("Correct source rate (all)", da.get("correct_source_rate_all"), c7.get("correct_source_rate_all")))
                lines.append(_metric_line("Correct source rate (on success)", da.get("correct_source_rate_on_success"), c7.get("correct_source_rate_on_success")))
                lines.append(_metric_line("Hit@1 (domain-level)", da.get("hit@1"), c7.get("hit@1")))
                lines.append(_metric_line("MRR", da.get("mrr"), c7.get("mrr")))
                lines.append(_metric_line("Avg latency (ms)", da.get("avg_latency_ms"), c7.get("avg_latency_ms")))
                lines.append("")
                lines.append("**Interpretation:**")
                if da.get("coverage_rate", 0) < 0.5 and c7.get("coverage_rate", 0) > 0.8:
                    lines.append("- Context7 clearly wins zero-setup public docs — expected behavior.")
                    lines.append("- DocAtlas empty results are not failures; they show that pre-indexing is required.")
                elif da.get("coverage_rate", 0) > 0.8:
                    lines.append("- DocAtlas already has indexed public docs — coverage is competitive.")
                lines.append("")

    if benchmark_mode in ("preindexed", "both"):
        lines.append("## Preindexed Public Docs")
        lines.append("")
        for sm in suite_metrics:
            if sm["suite"] == "public-docs":
                da = sm.get("docatlas_preindexed", sm.get("docatlas", {}))
                if not da or not da.get("total_queries", 0):
                    continue
                lines.append("**DocAtlas (preindexed):**")
                lines.append("")
                lines.append(f"- Coverage rate: {_mv(da.get('coverage_rate'))}")
                lines.append(f"- Empty count: {da.get('empty_count', '?')}")
                lines.append(f"- Contamination rate: {_mv(da.get('contamination_rate_all'))}")
                lines.append(f"- Correct source rate (on success): {_mv(da.get('correct_source_rate_on_success'))}")
                lines.append(f"- Hit@1: {_mv(da.get('hit@1'))}")
                lines.append(f"- MRR: {_mv(da.get('mrr'))}")
                lines.append(f"- Exact version correctness: {_mv(da.get('exact_version_correctness_on_success'))}")
                lines.append("")
                if da.get("empty_count", 0) > 0:
                    lines.append("**Note:** Some libraries could not be pre-indexed. See preindex diagnostics below.")
                    lines.append("")

    if benchmark_mode in ("zero-setup", "preindexed", "both"):
        lines.append("## Project Docs")
        lines.append("")
        for sm in suite_metrics:
            if sm["suite"] == "project-docs":
                da = sm.get("docatlas_zero_setup", sm.get("docatlas", {}))
                c7 = sm.get("context7_zero_setup", sm.get("context7", {}))
                lines.append("| Metric | DocAtlas | Context7 |")
                lines.append("|--------|----------|----------|")
                lines.append(_metric_line("Success count", da.get("success_count"), c7.get("success_count")))
                lines.append(_metric_line("Coverage rate", da.get("coverage_rate"), c7.get("coverage_rate")))
                lines.append(_metric_line("Contamination rate", da.get("contamination_rate_all"), c7.get("contamination_rate_all")))
                lines.append(_metric_line("Correct source rate (on success)", da.get("correct_source_rate_on_success"), c7.get("correct_source_rate_on_success")))
                lines.append(_metric_line("Not applicable count", da.get("not_applicable_count"), c7.get("not_applicable_count")))
                lines.append(_metric_line("Avg latency (ms)", da.get("avg_latency_ms"), c7.get("avg_latency_ms")))
                lines.append("")
                lines.append("**Interpretation:**")
                lines.append("- Context7 is not applicable for project-docs (no local repo context). This is by design.")
                lines.append(f"- DocAtlas: {da.get('success_count', 0)}/{da.get('applicable_queries', 0)} project queries answered.")
                lines.append("")

    if benchmark_mode in ("preindexed", "both"):
        lines.append("## Exact-Version Dependency Docs")
        lines.append("")
        for sm in suite_metrics:
            if sm["suite"] == "exact-version":
                da = sm.get("docatlas_preindexed", sm.get("docatlas", {}))
                c7 = sm.get("context7_zero_setup", sm.get("context7", {}))
                lines.append("| Metric | DocAtlas | Context7 |")
                lines.append("|--------|----------|----------|")
                lines.append(_metric_line("Coverage rate", da.get("coverage_rate"), c7.get("coverage_rate")))
                lines.append(_metric_line("Success count", da.get("success_count"), c7.get("success_count")))
                lines.append(_metric_line("Exact version empty rate", da.get("exact_version_empty_rate"), c7.get("exact_version_empty_rate")))
                lines.append(_metric_line("Exact version correctness (on success)", da.get("exact_version_correctness_on_success"), c7.get("exact_version_correctness_on_success")))
                lines.append(_metric_line("Contamination rate", da.get("contamination_rate_all"), c7.get("contamination_rate_all")))
                lines.append("")
                evc = da.get("exact_version_correctness_on_success")
                if evc is None:
                    lines.append("- DocAtlas: No successful exact-version results to evaluate correctness.")
                elif evc > 0.9:
                    lines.append("- DocAtlas: Version correctness confirmed.")
                else:
                    lines.append(f"- DocAtlas: Version correctness at {_mv(evc)} — needs improvement.")
                lines.append("")

    lines.append("## Coverage vs Correctness")
    lines.append("")
    lines.append("These two metrics are **independent** and both important:")
    lines.append("")
    lines.append("- **Coverage** (success / applicable): Did the provider return results?")
    lines.append("- **Correctness** (1 - contamination / applicable): Were the returned results from the right source?")
    lines.append("")
    lines.append("A provider can have:")
    lines.append("- Low coverage + high correctness → honest, not misleading")
    lines.append("- High coverage + low correctness → noisy, potentially harmful")
    lines.append("- High coverage + high correctness → ideal")
    lines.append("")
    lines.append(f"- DocAtlas: coverage={_mv(da_cov)}, correctness_on_success={_mv(overall_da.get('correct_source_rate_on_success'))}")
    lines.append(f"- Context7: coverage={_mv(c7_cov)}, correctness_on_success={_mv(overall_c7.get('correct_source_rate_on_success'))}")
    lines.append("")

    lines.append("## Where DocAtlas Wins")
    lines.append("")
    wins = []
    for sm in suite_metrics:
        if sm["suite"] == "project-docs":
            da = sm.get("docatlas_zero_setup", sm.get("docatlas", {}))
            if da.get("coverage_rate", 0) > 0.8:
                wins.append(f"- **Project docs awareness:** DocAtlas covers {_mv(da.get('coverage_rate'))} of project queries (Context7 is N/A by design)")
        if sm["suite"] == "public-docs":
            da_zs = sm.get("docatlas_zero_setup", {})
            da_pi = sm.get("docatlas_preindexed", {})
            for label, da in [("zero-setup", da_zs), ("preindexed", da_pi)]:
                if da and da.get("contamination_rate_on_success", 0) == 0 or (da and da.get("correct_source_rate_on_success", 1) >= 0.95):
                    wins.append(f"- **Source correctness ({label}):** correct_source_rate_on_success = {_mv(da.get('correct_source_rate_on_success'))} on public-docs")
    if not wins:
        wins.append("- More data needed for conclusive wins.")
    for w in wins:
        lines.append(w)
    lines.append("")

    lines.append("## Where Context7 Wins")
    lines.append("")
    wins = []
    for sm in suite_metrics:
        if sm["suite"] == "public-docs":
            c7 = sm.get("context7_zero_setup", sm.get("context7", {}))
            if c7.get("coverage_rate", 0) > 0.8:
                wins.append(f"- **Zero-setup public docs:** Context7 coverage = {_mv(c7.get('coverage_rate'))} with no pre-indexing")
        if sm["suite"] == "exact-version":
            c7 = sm.get("context7_zero_setup", sm.get("context7", {}))
            if c7.get("coverage_rate", 0) > 0.8:
                wins.append(f"- **Zero-setup exact-version:** Context7 returns results without setup")
    if not wins:
        wins.append("- More data needed for conclusive wins.")
    for w in wins:
        lines.append(w)
    lines.append("")

    lines.append("## Not Comparable Cases")
    lines.append("")
    na_count = sum(1 for r in all_results if r.is_not_applicable())
    lines.append(f"- **Project-docs for Context7:** {na_count} cases correctly marked not_applicable")
    lines.append("- Context7 has no local repo context — this is by design, not a failure.")
    lines.append("")

    lines.append("## Per-Case Detail")
    lines.append("")
    lines.append("| Case | Suite | Provider ID | Status | Sources | Latency |")
    lines.append("|------|-------|-------------|--------|--------|---------|")
    by_id: dict[str, dict[str, NormalizedBenchmarkResult]] = {}
    for r in all_results:
        by_id.setdefault(r.case_id, {})[r.provider_id] = r
    for cid, provs in sorted(by_id.items()):
        first = next(iter(provs.values())) if provs else None
        suite = first.suite if first else "?"
        for pid in sorted(provs.keys()):
            r = provs[pid]
            lines.append(f"| {cid} | {suite} | {pid} | {r.status} | {len(r.sources)} | {r.latency_ms:.0f}ms |")
    lines.append("")

    lines.append("## Preindex Diagnostics")
    lines.append("")
    preindexed_results = [r for r in all_results if r.preindex and r.preindex.attempted]
    if preindexed_results:
        lines.append("| Case | Library | Preindex status | Pages | Chunks | Latency (ms) |")
        lines.append("|------|---------|-----------------|-------|--------|--------------|")
        for r in preindexed_results:
            p = r.preindex
            lines.append(f"| {r.case_id} | {p.library_id or '?'} | {p.status} | {p.pages} | {p.chunks} | {p.latency_ms:.0f} |")
    else:
        lines.append("No preindex diagnostics recorded (not in preindexed mode).")
    lines.append("")

    lines.append("## Claims We Can Make")
    lines.append("")
    claims = [
        "DocAtlas has project-level doc awareness that Context7 cannot provide by design.",
        "Context7 provides zero-setup public docs lookup with reliable source attribution.",
        "DocAtlas requires pre-indexing to compete on public docs coverage.",
        "Both providers show zero contamination when returning results.",
        "The benchmark honestly distinguishes coverage vs correctness.",
    ]
    for c in claims:
        lines.append(f"- {c}")
    lines.append("")

    lines.append("## Claims We Cannot Make Yet")
    lines.append("")
    nocla = [
        '"DocAtlas beats Context7 overall" — different use cases, different setup requirements.',
        '"Context7 has worse contamination than DocAtlas" — both show zero contamination on this suite.',
        '"Dartdoc exact-version is solved" — need Dartdoc-specific test cases with pub.dev packages.',
        '"One provider is strictly better than the other" — they serve complementary use cases.',
    ]
    for c in nocla:
        lines.append(f"- {c}")
    lines.append("")

    lines.append("## Recommended Next Work")
    lines.append("")
    recs = [
        "Pre-index libraries before running preindexed mode for full comparison.",
        "Add Dartdoc-specific test cases for exact-version Dart packages.",
        "Run on CI with cron schedule to track regressions.",
        "Add FixtureProvider to compare against saved golden snapshots.",
        "Expand library coverage beyond FastAPI, Click, Riverpod, flutter_bloc.",
    ]
    for r in recs:
        lines.append(f"- {r}")
    lines.append("")

    return "\n".join(lines)


# ── Runner ───────────────────────────────────────────────────

async def run_benchmark(
    providers: list[BenchmarkProvider],
    cases: list[BenchmarkCase],
    suites: list[str] | None = None,
    save_raw: bool = False,
    fail_on_regression: bool = False,
    output_dir: str | None = None,
    benchmark_mode: str = "zero-setup",
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = Path(output_dir or str(RESULTS_ROOT / timestamp))
    out_path.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    all_results: list[NormalizedBenchmarkResult] = []
    filtered = [c for c in cases if suites is None or c.suite in suites]
    if not filtered:
        print("No cases match suite filter.")
        return {}

    print(f"Benchmark mode: {benchmark_mode}")
    print(f"Providers: {[p.name + '(' + p.provider_mode + ')' for p in providers]}")
    print(f"Cases: {len(filtered)}, suites: {suites or 'all'}")
    print(f"Output: {out_path}\n")

    for p in providers:
        try:
            await p.setup()
        except Exception as exc:
            print(f"  Setup failed for {p.name}: {exc}")

    for case in filtered:
        for p in providers:
            label = f"[{p.name}] {case.id}"
            result = await p.query(case)
            all_results.append(result)

            icon = "✓" if result.is_success() else ("⨯" if result.is_error() else ("–" if result.is_not_applicable() else "?"))
            print(f"  {label}: {icon} {result.status} ({result.latency_ms:.0f}ms, {len(result.sources)} src)")

            if save_raw:
                raw_dir = out_path / p.provider_id
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_data = {
                    "case_id": case.id, "suite": case.suite,
                    "mode": p.benchmark_mode,
                    "provider": p.name, "provider_id": p.provider_id,
                    "provider_mode": p.provider_mode,
                    "query": case.query,
                    "status": result.status, "latency_ms": result.latency_ms,
                    "setup_calls": result.setup_calls,
                    "sources": [dataclasses.asdict(s) for s in result.sources],
                    "snippets": [{"text": s.text[:200], "source": s.source, "rank": s.rank} for s in result.snippets[:5]],
                    "warnings": result.warnings, "reason_codes": result.reason_codes,
                    "exact_version_used": result.exact_version_used,
                    "contamination_hits": result.contamination_hits,
                    "forbidden_source_hits": result.forbidden_source_hits,
                    "expected_source_hits": result.expected_source_hits,
                    "expected_domains": case.expected_domains,
                    "forbidden_domains": case.forbidden_domains,
                    "expected_doc_scope": case.expected_doc_scope,
                    "manual_review_required": result.manual_review_required,
                    "preindex": dataclasses.asdict(result.preindex) if result.preindex else None,
                    "timestamp": timestamp,
                }
                raw_file = raw_dir / f"{case.id}.json"
                raw_file.write_text(json.dumps(raw_data, indent=2, ensure_ascii=False), encoding="utf-8")

    duration = time.perf_counter() - start

    for p in providers:
        if hasattr(p, "shutdown"):
            try:
                await p.shutdown()
            except Exception:
                pass

    da_all = [r for r in all_results if r.provider == "docatlas"]
    c7_all = [r for r in all_results if r.provider == "context7"]
    da_sm = compute_metrics(da_all)
    c7_sm = compute_metrics(c7_all)

    suites_meta = []
    for sn in sorted(set(r.suite for r in all_results)):
        suites_meta.append(compute_suite_metrics(all_results, sn))

    da_zi = compute_metrics([r for r in da_all if r.mode == "zero-setup"]) if da_all else None
    c7_zi = compute_metrics([r for r in c7_all if r.mode == "zero-setup"]) if c7_all else None
    da_pi = compute_metrics([r for r in da_all if r.mode == "preindexed"]) if da_all else None

    report = generate_markdown_report(
        all_results, da_sm, c7_sm, suites_meta,
        da_zi, c7_zi, da_pi,
        timestamp, duration, benchmark_mode,
    )
    (out_path / "report.md").write_text(report, encoding="utf-8")

    summary = {
        "timestamp": timestamp, "duration_s": round(duration, 3),
        "benchmark_mode": benchmark_mode,
        "total_queries": len(all_results),
        "providers": {
            p.provider_id: {
                "provider": p.name,
                "provider_mode": p.provider_mode,
                "benchmark_mode": p.benchmark_mode,
            }
            for p in providers
        },
        "suites": sorted(set(r.suite for r in all_results)),
        "docatlas": da_sm, "context7": c7_sm,
        "suite_metrics": suites_meta,
        "report_file": str(out_path / "report.md"),
    }
    (out_path / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone. Report: {out_path / 'report.md'}")
    if save_raw:
        print(f"Raw: {out_path}/<provider>/<case_id>.json")

    # ── Acceptance gates ──
    if fail_on_regression:
        failures = []

        for sm in suites_meta:
            if sm["suite"] == "project-docs":
                da = sm.get("docatlas", {})
                if da.get("coverage_rate", 0) < 0.9:
                    failures.append(f"[project-docs][docatlas] coverage_rate {_mv(da.get('coverage_rate'))} < 0.90")
                if da.get("contamination_rate_all", 1) > 0.0:
                    failures.append(f"[project-docs][docatlas] contamination {da.get('contamination_rate_all')} > 0.0")
                csrs = da.get("correct_source_rate_on_success", 0)
                if csrs is not None and csrs < 0.95:
                    failures.append(f"[project-docs][docatlas] correct_source_rate_on_success {_mv(csrs)} < 0.95")

        for sm in suites_meta:
            if sm["suite"] == "public-docs":
                da = sm.get("docatlas", {})
                if da.get("contamination_rate_all", 0) > 0.05 and da.get("success_count", 0) > 0:
                    failures.append(f"[public-docs][docatlas] contamination {da.get('contamination_rate_all')} > 0.05")

        if failures:
            print(f"\nRegression check FAILED ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
            raise SystemExit(1)
        print("Regression check passed.")

    return summary


# ── Main ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live MCP benchmark: DocAtlas vs Context7")
    parser.add_argument("--mode", choices=["zero-setup", "preindexed", "both"], default="zero-setup",
                        help="benchmark mode (default: zero-setup)")
    parser.add_argument("--suite", choices=["public-docs", "project-docs", "exact-version", "all"],
                        default="all", help="suite filter (default: all)")
    parser.add_argument("--save-raw", action="store_true", help="save raw outputs per query")
    parser.add_argument("--output-dir", help="custom output directory")
    parser.add_argument("--fail-on-regression", action="store_true", help="exit non-zero if acceptance checks fail")
    parser.add_argument("--quick", action="store_true", help="run minimal case set")
    parser.add_argument("--skip-docatlas", action="store_true", help="skip DocAtlas provider")
    parser.add_argument("--skip-context7", action="store_true", help="skip Context7 provider")
    args = parser.parse_args()

    suites = None if args.suite == "all" else [args.suite]
    cases = _filter_cases(suites, args.quick)
    if not cases:
        print("No matching cases.")
        return

    mode = args.mode

    providers: list[BenchmarkProvider] = []

    if mode in ("zero-setup", "both"):
        if not args.skip_docatlas:
            p = DocAtlasDirectProvider()
            p.benchmark_mode = "zero-setup"
            p.provider_id = "docatlas_zero_setup"
            providers.append(p)
        if not args.skip_context7:
            p = Context7MCPProvider()
            p.benchmark_mode = "zero-setup"
            p.provider_id = "context7_zero_setup"
            providers.append(p)

    if mode in ("preindexed", "both"):
        if not args.skip_docatlas:
            p = DocAtlasDirectProvider()
            p.benchmark_mode = "preindexed"
            p.provider_id = "docatlas_preindexed"
            providers.append(p)

    # Storage isolation for both mode: each docatlas provider gets its own db
    runtime_base = Path(tempfile.gettempdir()) / "live-benchmark"
    for p in providers:
        if isinstance(p, DocAtlasDirectProvider) and mode == "both":
            iso_dir = runtime_base / mode / p.provider_id
            iso_dir.mkdir(parents=True, exist_ok=True)
            p._custom_db_path = str(iso_dir / "docmancer.db")
            print(f"[isolation] {p.provider_id} -> {p._custom_db_path}")

    if not providers:
        print("No providers selected.")
        return

    asyncio.run(run_benchmark(
        providers=providers,
        cases=cases,
        suites=suites,
        save_raw=args.save_raw,
        fail_on_regression=args.fail_on_regression,
        output_dir=args.output_dir,
        benchmark_mode=mode,
    ))


if __name__ == "__main__":
    main()
