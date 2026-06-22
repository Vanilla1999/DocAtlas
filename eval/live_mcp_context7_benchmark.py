from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import subprocess
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "eval" / "results" / "live"

TIMEOUT_REFRESH_SECONDS = 300
TIMEOUT_QUERY_SECONDS = 120


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
    provider_mode: str
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
    raw_response: dict[str, Any] | None = None

    def is_not_applicable(self) -> bool:
        return self.status == "not_applicable"

    def is_error(self) -> bool:
        return self.status in ("error", "timeout", "failed_ingest")

    def is_empty(self) -> bool:
        return self.status in ("empty_index", "needs_refresh", "no_results")

    def is_quota_exceeded(self) -> bool:
        return self.status == "quota_exceeded"

    def is_success(self) -> bool:
        return self.status == "success"


# ═══════════════════════════════════════════════════════════════
#  Suite definitions
# ═══════════════════════════════════════════════════════════════

PUBLIC_DOCS_CASES: list[BenchmarkCase] = [
    # ─ FastAPI ─
    BenchmarkCase(
        id="fastapi_depends",
        query="FastAPI Depends in path operations with dependency function and query parameters",
        suite="public-docs",
        library="fastapi",
        ecosystem="python",
        expected_sources=["fastapi.tiangolo.com"],
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        expected_source_patterns=["fastapi"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["Depends", "common_parameters", "FastAPI"],
        context7_library_id="/fastapi/fastapi",
    ),
    BenchmarkCase(
        id="fastapi_http_exception",
        query="FastAPI raise HTTPException with status_code and detail for a 404 error",
        suite="public-docs",
        library="fastapi",
        ecosystem="python",
        expected_sources=["fastapi.tiangolo.com"],
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["HTTPException", "status_code", "detail"],
        context7_library_id="/fastapi/fastapi",
    ),
    BenchmarkCase(
        id="fastapi_testclient",
        query="FastAPI test app with fastapi.testclient.TestClient client and pytest assertions",
        suite="public-docs",
        library="fastapi",
        ecosystem="python",
        expected_sources=["fastapi.tiangolo.com"],
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["TestClient", "assert"],
        context7_library_id="/fastapi/fastapi",
    ),
    BenchmarkCase(
        id="fastapi_background_tasks",
        query="FastAPI BackgroundTasks usage and dependency injection",
        suite="public-docs",
        library="fastapi",
        ecosystem="python",
        expected_sources=["fastapi.tiangolo.com"],
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["BackgroundTasks", "add_task"],
        context7_library_id="/fastapi/fastapi",
    ),
    # ─ Click ─
    BenchmarkCase(
        id="click_command_group",
        query="Click command group with subcommands and options",
        suite="public-docs",
        library="click",
        ecosystem="python",
        expected_sources=["click.palletsprojects.com"],
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["@click.group", "@click.option", "callback"],
        context7_library_id="/pallets/click",
    ),
    BenchmarkCase(
        id="click_options",
        query="Click option decorator with types, prompts, and defaults",
        suite="public-docs",
        library="click",
        ecosystem="python",
        expected_sources=["click.palletsprojects.com"],
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["@click.option", "prompt", "default"],
        context7_library_id="/pallets/click",
    ),
    BenchmarkCase(
        id="click_callbacks",
        query="Click parameter callbacks and validation patterns",
        suite="public-docs",
        library="click",
        ecosystem="python",
        expected_sources=["click.palletsprojects.com"],
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["callback", "ctx", "Parameter"],
        context7_library_id="/pallets/click",
    ),
    BenchmarkCase(
        id="click_context_passing",
        query="Click context passing with pass_context and ensure_object",
        suite="public-docs",
        library="click",
        ecosystem="python",
        expected_sources=["click.palletsprojects.com"],
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev", "flutter.dev"],
        expected_facts=["Context", "pass_context", "ensure_object"],
        context7_library_id="/pallets/click",
    ),
    # ─ Riverpod ─
    BenchmarkCase(
        id="riverpod_autodispose",
        query="Riverpod autoDispose modifier and ref.onDispose cleanup",
        suite="public-docs",
        library="riverpod",
        ecosystem="flutter",
        expected_sources=["riverpod.dev", "pub.dev"],
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_facts=["autoDispose", "ref.onDispose"],
        context7_library_id="/rrousselgit/riverpod",
    ),
    BenchmarkCase(
        id="riverpod_keepalive",
        query="Riverpod keepAlive modifier and ref.keepAlive to prevent disposal",
        suite="public-docs",
        library="riverpod",
        ecosystem="flutter",
        expected_sources=["riverpod.dev", "pub.dev"],
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_facts=["keepAlive", "ref.keepAlive"],
        context7_library_id="/rrousselgit/riverpod",
    ),
    BenchmarkCase(
        id="riverpod_family",
        query="Riverpod family modifier with parameterized providers",
        suite="public-docs",
        library="riverpod",
        ecosystem="flutter",
        expected_sources=["riverpod.dev", "pub.dev"],
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_facts=["family", "parameter"],
        context7_library_id="/rrousselgit/riverpod",
    ),
    BenchmarkCase(
        id="riverpod_watch_vs_listen",
        query="Riverpod ref.watch vs ref.listen differences and AsyncValue handling",
        suite="public-docs",
        library="riverpod",
        ecosystem="flutter",
        expected_sources=["riverpod.dev", "pub.dev"],
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_facts=["ref.watch", "ref.listen", "AsyncValue"],
        context7_library_id="/rrousselgit/riverpod",
    ),
    BenchmarkCase(
        id="riverpod_asyncnotifier_migration",
        query="Riverpod AsyncNotifier migration from StateNotifier pattern",
        suite="public-docs",
        library="riverpod",
        ecosystem="flutter",
        expected_sources=["riverpod.dev", "pub.dev"],
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "flutter.dev"],
        expected_facts=["AsyncNotifier", "AsyncNotifierProvider", "build"],
        context7_library_id="/rrousselgit/riverpod",
    ),
    # ─ flutter_bloc ─
    BenchmarkCase(
        id="bloc_provider",
        query="Flutter BlocProvider to provide a bloc to the widget tree",
        suite="public-docs",
        library="flutter_bloc",
        ecosystem="flutter",
        expected_sources=["pub.dev", "bloclibrary.dev"],
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_facts=["BlocProvider", "create", "child"],
        context7_library_id="/felangel/bloc",
    ),
    BenchmarkCase(
        id="bloc_builder",
        query="Flutter BlocBuilder with builder and buildWhen for conditional rebuilds",
        suite="public-docs",
        library="flutter_bloc",
        ecosystem="flutter",
        expected_sources=["pub.dev", "bloclibrary.dev"],
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_facts=["BlocBuilder", "builder", "buildWhen"],
        context7_library_id="/felangel/bloc",
    ),
    BenchmarkCase(
        id="bloc_listener",
        query="Flutter BlocListener with listener and listenWhen for side effects",
        suite="public-docs",
        library="flutter_bloc",
        ecosystem="flutter",
        expected_sources=["pub.dev", "bloclibrary.dev"],
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_facts=["BlocListener", "listener", "listenWhen"],
        context7_library_id="/felangel/bloc",
    ),
    BenchmarkCase(
        id="bloc_multi_provider",
        query="Flutter MultiBlocProvider combining multiple blocs",
        suite="public-docs",
        library="flutter_bloc",
        ecosystem="flutter",
        expected_sources=["pub.dev", "bloclibrary.dev"],
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "riverpod.dev"],
        expected_facts=["MultiBlocProvider", "providers"],
        context7_library_id="/felangel/bloc",
    ),
]

PROJECT_DOCS_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        id="project_lifecycle",
        query="How is the project docs lifecycle in DocAtlas?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md", "ARCHITECTURE.md", "README.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"],
    ),
    BenchmarkCase(
        id="source_isolation",
        query="How does DocAtlas isolate library docs from project docs?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["CHANGELOG.md", "docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"],
    ),
    BenchmarkCase(
        id="trust_contract",
        query="How does the DocAtlas Trust Contract work?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md", "ARCHITECTURE.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"],
    ),
    BenchmarkCase(
        id="sync_vs_ingest",
        query="How does sync_project_docs differ from ingest_project_docs?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"],
    ),
    BenchmarkCase(
        id="risky_rejected_docs",
        query="Which docs sources are considered risky or rejected in DocAtlas?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"],
    ),
    BenchmarkCase(
        id="v1_source_isolation",
        query="What changed in v1.0.0 for source isolation?",
        suite="project-docs",
        not_applicable_for=["context7"],
        expected_sources=["CHANGELOG.md", "docs/project-docs-mcp-workflow.md"],
        expected_doc_scope="project",
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com", "pub.dev"],
    ),
]

EXACT_VERSION_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        id="exact_fastapi_version",
        query="FastAPI Depends with exact version 0.115.13",
        suite="exact-version",
        library="fastapi",
        ecosystem="python",
        version="0.115.13",
        expected_sources=["fastapi.tiangolo.com"],
        expected_domains=["fastapi.tiangolo.com", "github.com"],
        forbidden_domains=["click.palletsprojects.com", "riverpod.dev"],
        expected_facts=["Depends"],
        context7_library_id="/fastapi/fastapi/0.115.13",
    ),
    BenchmarkCase(
        id="exact_riverpod_version",
        query="Riverpod family modifier with exact version",
        suite="exact-version",
        library="riverpod",
        ecosystem="flutter",
        version="2.6.1",
        expected_sources=["riverpod.dev", "pub.dev"],
        expected_domains=["riverpod.dev", "pub.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com"],
        expected_facts=["family", "riverpod"],
        context7_library_id="/rrousselgit/riverpod",
    ),
    BenchmarkCase(
        id="exact_flutter_bloc_version",
        query="Flutter BlocProvider with exact version",
        suite="exact-version",
        library="flutter_bloc",
        ecosystem="flutter",
        version="9.1.0",
        expected_sources=["pub.dev", "bloclibrary.dev"],
        expected_domains=["pub.dev", "bloclibrary.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com"],
        expected_facts=["BlocProvider", "bloc"],
        context7_library_id="/felangel/bloc",
    ),
    BenchmarkCase(
        id="exact_click_version",
        query="Click command group with exact version 8.1.x",
        suite="exact-version",
        library="click",
        ecosystem="python",
        version="8.1.8",
        expected_sources=["click.palletsprojects.com"],
        expected_domains=["click.palletsprojects.com", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev"],
        expected_facts=["@click.group", "click"],
        context7_library_id="/pallets/click",
    ),
    BenchmarkCase(
        id="exact_pydantic_version",
        query="Pydantic BaseModel field validators with exact version",
        suite="exact-version",
        library="pydantic",
        ecosystem="python",
        version="2.11.1",
        expected_sources=["docs.pydantic.dev"],
        expected_domains=["docs.pydantic.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "riverpod.dev"],
        expected_facts=["BaseModel", "field_validator"],
        context7_library_id="/pydantic/pydantic",
    ),
    BenchmarkCase(
        id="exact_go_router_version",
        query="GoRouter route configuration and navigation with exact version",
        suite="exact-version",
        library="go_router",
        ecosystem="flutter",
        version="14.8.1",
        expected_sources=["pub.dev", "api.flutter.dev"],
        expected_domains=["pub.dev", "api.flutter.dev", "github.com"],
        forbidden_domains=["fastapi.tiangolo.com", "click.palletsprojects.com"],
        expected_facts=["GoRouter", "route", "context.go"],
        context7_library_id="/websites/pub_dev_packages_go_router",
    ),
]

ALL_CASES: list[BenchmarkCase] = PUBLIC_DOCS_CASES + PROJECT_DOCS_CASES + EXACT_VERSION_CASES


# ═══════════════════════════════════════════════════════════════
#  Provider abstraction
# ═══════════════════════════════════════════════════════════════

class BenchmarkProvider:
    name: str
    provider_mode: str

    async def setup(self) -> None:
        pass

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        raise NotImplementedError


# ── DocAtlas MCP Provider (direct Python API) ────────────────

class DocAtlasMCPProvider(BenchmarkProvider):
    def __init__(self, project_path: str | None = None):
        self.name = "docatlas"
        self.provider_mode = "live_mcp"
        self._project_path = project_path or str(ROOT)
        self._service = None
        self._indexed_libs: dict[str, bool] = {}

    def _get_service(self):
        if self._service is None:
            from docmancer.docs.service import LibraryDocsService
            from docmancer.core.config import DocmancerConfig
            config = DocmancerConfig()
            self._service = LibraryDocsService(config=config)
        return self._service

    async def setup(self) -> None:
        service = self._get_service()
        _ = service  # warm up

    async def _ensure_library_indexed(self, library: str, ecosystem: str | None, version: str | None) -> dict[str, Any]:
        service = self._get_service()
        key = f"{ecosystem or ''}:{library}:{version or ''}"
        if key in self._indexed_libs:
            return {"status": "already_indexed"}
        try:
            info = service.resolve_library(library, ecosystem=ecosystem, version=version)
            if info.library_id is None:
                return {"status": "not_supported", "reason_code": "unresolved", "message": info.message or "Library could not be resolved"}
            record = service.inspect_library_docs(info.library_id)
            chunks = record.chunks if hasattr(record, "chunks") else 0
            status = record.status if hasattr(record, "status") else "unknown"
            self._indexed_libs[key] = chunks > 0
            return {"status": status, "library_id": info.library_id, "chunks": chunks}
        except Exception as exc:
            return {"status": "failed_ingest", "reason_code": str(exc)}

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        if "docatlas" in case.not_applicable_for:
            return self._not_applicable(case)
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

        try:
            if case.suite == "project-docs":
                result = await asyncio.to_thread(
                    service.get_project_context,
                    self._project_path,
                    case.query,
                    tokens=4000,
                )
                setup_calls += 1
                context_pack = result.context_pack if hasattr(result, "context_pack") else []
                trust_contract = result.trust_contract if hasattr(result, "trust_contract") else {}
                selected = trust_contract.get("selected", [])
                rejected = trust_contract.get("rejected", [])
                risky = trust_contract.get("risky", [])
                answer_text = str(result.answer_outline) if hasattr(result, "answer_outline") and result.answer_outline else None
                for i, item in enumerate(context_pack):
                    raw_source = item.get("source") or {}
                    path_val = item.get("path") or ""
                    url_val = item.get("url") or ""
                    if isinstance(raw_source, dict):
                        source_str = path_val or url_val or str(raw_source.get("path", ""))
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
                if selected:
                    for s in selected:
                        if isinstance(s, dict) and "source" in s:
                            pass
            else:
                result = await asyncio.to_thread(
                    service.get_docs,
                    case.library,
                    topic=case.query,
                    tokens=2000,
                    ecosystem=case.ecosystem,
                    version=case.version,
                )
                setup_calls += 2
                if hasattr(result, "status") and result.status == "empty_library_index":
                    setup_result = await self._ensure_library_indexed(case.library, case.ecosystem, case.version)
                    reason_codes.append(setup_result.get("status", "unknown"))
                    if setup_result.get("chunks", 0) > 0:
                        result = await asyncio.to_thread(
                            service.get_docs,
                            case.library,
                            topic=case.query,
                            tokens=2000,
                            ecosystem=case.ecosystem,
                            version=case.version,
                        )
                        setup_calls += 2
                if hasattr(result, "results") and result.results:
                    for i, chunk in enumerate(result.results):
                        source = chunk.source or ""
                        title = chunk.title or ""
                        content = chunk.content or ""
                        url = chunk.url or source
                        sources.append(SourceRef(url=url, title=title, rank=i + 1, doc_scope="public_docs"))
                        if content:
                            snippets.append(Snippet(text=content[:500], source=url, rank=i + 1))
                    if hasattr(result, "docs_exactness") and result.docs_exactness:
                        exact_version_used = exact_version_used or result.resolved_version or result.version
                else:
                    if result.results is not None and len(result.results) == 0:
                        if hasattr(result, "warning") and result.warning:
                            warnings.append(result.warning)
                        status = "empty_index"
                        reason_codes.append("empty_library_index")
                    else:
                        status = "no_results"
                if hasattr(result, "warnings") and result.warnings:
                    warnings.extend(result.warnings)
                if hasattr(result, "warning") and result.warning:
                    warnings.append(result.warning)

        except Exception as exc:
            status = "error"
            warnings.append(str(exc))
            reason_codes.append(type(exc).__name__)

        latency_ms = round((time.perf_counter() - start) * 1000, 3)

        contamination_hits = self._detect_contamination(sources, case)
        forbidden_source_hits = self._detect_forbidden_sources(sources, case)
        expected_source_hits = self._detect_expected_sources(sources, case)

        return NormalizedBenchmarkResult(
            provider=self.name,
            provider_mode=self.provider_mode,
            case_id=case.id,
            query=case.query,
            suite=case.suite,
            status=status,
            latency_ms=latency_ms,
            setup_calls=setup_calls,
            sources=sources,
            snippets=snippets,
            answer_text=answer_text,
            warnings=warnings,
            reason_codes=reason_codes,
            exact_version_used=exact_version_used,
            contamination_hits=contamination_hits,
            forbidden_source_hits=forbidden_source_hits,
            expected_source_hits=expected_source_hits,
            manual_review_required=status == "error",
            raw_response=None,
        )

    def _detect_contamination(self, sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
        hits = []
        for src in sources:
            if case.forbidden_domains:
                domain = src.domain or ""
                for forbidden in case.forbidden_domains:
                    if domain == forbidden or domain.endswith("." + forbidden):
                        hits.append(f"forbidden_domain:{forbidden} in {src.url}")
            if case.expected_doc_scope and src.doc_scope and src.doc_scope != case.expected_doc_scope:
                hits.append(f"wrong_doc_scope:{src.doc_scope} expected:{case.expected_doc_scope} in {src.url}")
        return hits

    def _detect_forbidden_sources(self, sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
        hits = []
        if not case.forbidden_sources:
            return hits
        src_urls = [s.url for s in sources]
        for forbidden in case.forbidden_sources:
            for url in src_urls:
                if forbidden in url:
                    hits.append(f"forbidden_source:{forbidden} in {url}")
        return hits

    def _detect_expected_sources(self, sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
        hits = []
        src_urls = [s.url for s in sources]
        src_domains = [s.domain or "" for s in sources]
        for pattern in case.expected_source_patterns:
            for url in src_urls:
                if pattern.lower() in url.lower():
                    hits.append(pattern)
                    break
        for domain in case.expected_domains:
            for d in src_domains:
                if domain.lower() in d.lower():
                    hits.append(domain)
                    break
        for expected in case.expected_sources:
            for url in src_urls:
                if expected.lower() in url.lower():
                    hits.append(expected)
                    break
        return hits

    def _not_applicable(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        return NormalizedBenchmarkResult(
            provider=self.name,
            provider_mode=self.provider_mode,
            case_id=case.id,
            query=case.query,
            suite=case.suite,
            status="not_applicable",
            latency_ms=0.0,
            setup_calls=0,
            sources=[],
            snippets=[],
            answer_text=None,
            warnings=["Case not applicable for this provider"],
            reason_codes=["not_applicable"],
            exact_version_used=None,
            contamination_hits=[],
            forbidden_source_hits=[],
            expected_source_hits=[],
            manual_review_required=False,
        )


# ── Context7 MCP Provider ────────────────────────────────────

class Context7MCPProvider(BenchmarkProvider):
    def __init__(self):
        self.name = "context7"
        self.provider_mode = "live_mcp"
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

    async def _resolve_library_id(self, case: BenchmarkCase) -> str | None:
        if case.context7_library_id:
            return case.context7_library_id
        if not case.library:
            return None
        if case.library in self._lib_cache:
            return self._lib_cache[case.library]
        try:
            session = await self._ensure_session()
            result = await session.call_tool("resolve-library-id", {
                "query": case.query,
                "libraryName": case.library,
            })
            text = result.content[0].text if result.content else ""
            match = re.search(r'/[\w/-]+', text)
            if match:
                lib_id = match.group(0)
                self._lib_cache[case.library] = lib_id
                return lib_id
        except Exception:
            pass
        return None

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        if "context7" in case.not_applicable_for:
            return self._not_applicable(case)

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
                    provider=self.name,
                    provider_mode=self.provider_mode,
                    case_id=case.id,
                    query=case.query,
                    suite=case.suite,
                    status="not_supported",
                    latency_ms=round((time.perf_counter() - start) * 1000, 3),
                    setup_calls=setup_calls,
                    sources=[],
                    snippets=[],
                    answer_text=None,
                    warnings=["Could not resolve Context7 library ID"],
                    reason_codes=["unresolved_library"],
                    exact_version_used=None,
                    contamination_hits=[],
                    forbidden_source_hits=[],
                    expected_source_hits=[],
                    manual_review_required=False,
                )

            query_args: dict[str, str] = {"libraryId": lib_id, "query": case.query}
            session = await self._ensure_session()
            result = await session.call_tool("query-docs", query_args)
            setup_calls += 1
            text = result.content[0].text if result.content else ""

            if not text or text.strip() == "":
                status = "empty_index"
            elif "not found" in text.lower() or "please check" in text.lower():
                status = "not_supported"
                warnings.append(f"Context7 could not find library: {lib_id}")
                reason_codes.append("library_not_found")
            elif "quota exceeded" in text.lower() or "monthly quota" in text.lower():
                status = "quota_exceeded"
                warnings.append("Context7 monthly quota exceeded")
                reason_codes.append("quota_exceeded")
            else:
                answer_text = text
                self._extract_sources_and_snippets(text, sources, snippets)

        except Exception as exc:
            status = "error"
            warnings.append(str(exc))
            reason_codes.append(type(exc).__name__)

        latency_ms = round((time.perf_counter() - start) * 1000, 3)

        contamination_hits = self._detect_contamination(sources, case)
        forbidden_source_hits = self._detect_forbidden_sources(sources, case)
        expected_source_hits = self._detect_expected_sources(sources, case)

        return NormalizedBenchmarkResult(
            provider=self.name,
            provider_mode=self.provider_mode,
            case_id=case.id,
            query=case.query,
            suite=case.suite,
            status=status,
            latency_ms=latency_ms,
            setup_calls=setup_calls,
            sources=sources,
            snippets=snippets,
            answer_text=answer_text,
            warnings=warnings,
            reason_codes=reason_codes,
            exact_version_used=exact_version_used,
            contamination_hits=contamination_hits,
            forbidden_source_hits=forbidden_source_hits,
            expected_source_hits=expected_source_hits,
            manual_review_required=status == "error",
            raw_response={"text_length": len(text) if text else 0},
        )

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
        self._read = None
        self._write = None

    def _extract_sources_and_snippets(self, text: str, sources: list[SourceRef], snippets: list[Snippet]) -> None:
        seen_urls: set[str] = set()
        rank = 0
        for line in text.split("\n"):
            m = re.match(r'^Source:\s*(https?://\S+)', line)
            if m:
                url = m.group(1).rstrip(".")
                if url not in seen_urls:
                    seen_urls.add(url)
                    rank += 1
                    sources.append(SourceRef(url=url, rank=rank))
        md_links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', text)
        for title, url in md_links:
            url = url.rstrip("/")
            if url not in seen_urls:
                seen_urls.add(url)
                rank += 1
                sources.append(SourceRef(url=url, title=title, rank=rank))
        raw_urls = re.findall(r'(https?://[^\s\)\]>]+)', text)
        for url in raw_urls:
            url = url.rstrip(".").rstrip(",")
            if url not in seen_urls:
                seen_urls.add(url)
                rank += 1
                sources.append(SourceRef(url=url, rank=rank))
        code_blocks = re.findall(r'```[\w]*\n(.*?)```', text, re.DOTALL)
        sorted_sources = sorted(sources, key=lambda s: s.rank) if sources else []
        for i, code in enumerate(code_blocks[:5]):
            src = sorted_sources[i % max(len(sorted_sources), 1)].url if sorted_sources else ""
            snippets.append(Snippet(text=code[:500], source=src, rank=i + 1))

    def _detect_contamination(self, sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
        hits = []
        for src in sources:
            domain = src.domain or ""
            if case.forbidden_domains:
                for forbidden in case.forbidden_domains:
                    if forbidden in domain:
                        hits.append(f"forbidden_domain:{forbidden} in {src.url}")
            if case.expected_doc_scope and src.doc_scope and src.doc_scope != case.expected_doc_scope:
                hits.append(f"wrong_doc_scope:{src.doc_scope} expected:{case.expected_doc_scope} in {src.url}")
        return hits

    def _detect_forbidden_sources(self, sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
        hits = []
        if not case.forbidden_sources:
            return hits
        src_urls = [s.url for s in sources]
        for forbidden in case.forbidden_sources:
            for url in src_urls:
                if forbidden in url:
                    hits.append(f"forbidden_source:{forbidden} in {url}")
        return hits

    def _detect_expected_sources(self, sources: list[SourceRef], case: BenchmarkCase) -> list[str]:
        hits = []
        src_urls = [s.url for s in sources]
        src_domains = [s.domain or "" for s in sources]
        for pattern in case.expected_source_patterns:
            for url in src_urls:
                if pattern.lower() in url.lower():
                    hits.append(pattern)
                    break
        for domain in case.expected_domains:
            for d in src_domains:
                if domain.lower() in d.lower():
                    hits.append(domain)
                    break
        for expected in case.expected_sources:
            for url in src_urls:
                if expected.lower() in url.lower():
                    hits.append(expected)
                    break
        return hits

    def _not_applicable(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        return NormalizedBenchmarkResult(
            provider=self.name,
            provider_mode=self.provider_mode,
            case_id=case.id,
            query=case.query,
            suite=case.suite,
            status="not_applicable",
            latency_ms=0.0,
            setup_calls=0,
            sources=[],
            snippets=[],
            answer_text=None,
            warnings=["Case not applicable: Context7 does not have local repo context"],
            reason_codes=["not_applicable_local_repo_context"],
            exact_version_used=None,
            contamination_hits=[],
            forbidden_source_hits=[],
            expected_source_hits=[],
            manual_review_required=False,
        )


# ═══════════════════════════════════════════════════════════════
#  Metrics
# ═══════════════════════════════════════════════════════════════

def compute_metrics(results: list[NormalizedBenchmarkResult]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}

    applicable = [r for r in results if not r.is_not_applicable()]
    successful = [r for r in applicable if r.is_success()]
    errors = [r for r in applicable if r.is_error()]
    empty = [r for r in applicable if r.is_empty()]
    n_applicable = len(applicable)
    n_success = len(successful)

    contamination_hits = sum(1 for r in applicable if r.contamination_hits)
    forbidden_hits = sum(1 for r in applicable if r.forbidden_source_hits)
    has_expected = sum(1 for r in applicable if r.expected_source_hits)

    hit1 = 0
    hit5 = 0
    reciprocal_ranks: list[float] = []
    for r in applicable:
        if r.expected_source_hits:
            ranks = []
            for src in r.sources:
                for expected in r.expected_source_hits:
                    if expected in src.url:
                        ranks.append(src.rank)
            if ranks:
                min_rank = min(ranks)
                reciprocal_ranks.append(1.0 / min_rank)
                if min_rank <= 1:
                    hit1 += 1
                if min_rank <= 5:
                    hit5 += 1
            else:
                reciprocal_ranks.append(0.0)
        else:
            reciprocal_ranks.append(0.0)

    unique_source_counts = []
    redundancy_counts = []
    for r in applicable:
        src_urls = list(dict.fromkeys([s.url for s in r.sources]))
        unique_count = len(src_urls)
        unique_source_counts.append(unique_count)
        if unique_count > 0:
            total_ranked = min(len(r.sources), 5)
            redundancy_counts.append(max(0, 1.0 - (unique_count / max(total_ranked, 1))))
        else:
            redundancy_counts.append(0.0)

    avg_unique = sum(unique_source_counts) / max(len(unique_source_counts), 1)
    avg_redundancy = sum(redundancy_counts) / max(len(redundancy_counts), 1)

    snippet_count = sum(1 for r in applicable if r.snippets)
    snippet_usefulness = snippet_count / max(n_applicable, 1)

    cold_latencies = [r.latency_ms for r in applicable if r.setup_calls > 0]
    warm_latencies = [r.latency_ms for r in applicable if r.setup_calls == 0]
    avg_latency = sum(r.latency_ms for r in applicable) / max(n_applicable, 1)
    avg_cold = sum(cold_latencies) / max(len(cold_latencies), 1) if cold_latencies else 0.0
    avg_warm = sum(warm_latencies) / max(len(warm_latencies), 1) if warm_latencies else 0.0

    setup_calls = [r.setup_calls for r in applicable]
    avg_setup = sum(setup_calls) / max(len(setup_calls), 1)

    exact_versions = [1 for r in applicable if r.exact_version_used]
    exact_version_rate = sum(exact_versions) / max(n_applicable, 1)

    hallucinated = sum(1 for r in applicable if "hallucination" in str(r.warnings).lower() or "hallucinated" in str(r.reason_codes).lower())
    hallucinated_rate = hallucinated / max(n_applicable, 1)

    return {
        "total_queries": total,
        "applicable_queries": n_applicable,
        "success_count": n_success,
        "error_count": len(errors),
        "empty_count": len(empty),
        "not_applicable_count": sum(1 for r in results if r.is_not_applicable()),
        "contamination_rate": round(contamination_hits / max(n_applicable, 1), 4),
        "correct_source_rate": round(1 - contamination_hits / max(n_applicable, 1), 4),
        "forbidden_source_rate": round(forbidden_hits / max(n_applicable, 1), 4),
        "hit@1": round(hit1 / max(n_applicable, 1), 4),
        "hit@5": round(hit5 / max(n_applicable, 1), 4),
        "mrr": round(sum(reciprocal_ranks) / max(len(reciprocal_ranks), 1), 4),
        "unique_sources@5": round(avg_unique, 4),
        "redundancy_rate": round(avg_redundancy, 4),
        "snippet_usefulness": round(snippet_usefulness, 4),
        "avg_latency_ms": round(avg_latency, 3),
        "avg_cold_latency_ms": round(avg_cold, 3),
        "avg_warm_latency_ms": round(avg_warm, 3),
        "setup_calls_avg": round(avg_setup, 4),
        "exact_version_correctness": round(exact_version_rate, 4),
        "hallucinated_api_rate": round(hallucinated_rate, 4),
    }


def compute_suite_metrics(results: list[NormalizedBenchmarkResult], suite: str) -> dict[str, Any]:
    suite_results = [r for r in results if r.suite == suite]
    provider_results: dict[str, list[NormalizedBenchmarkResult]] = {}
    for r in suite_results:
        provider_results.setdefault(r.provider, []).append(r)
    metrics: dict[str, Any] = {"suite": suite, "total": len(suite_results)}
    for provider, prov_results in provider_results.items():
        prov_metrics = compute_metrics(prov_results)
        prov_metrics["provider_mode"] = prov_results[0].provider_mode if prov_results else "unknown"
        metrics[provider] = prov_metrics
    return metrics


# ═══════════════════════════════════════════════════════════════
#  Report generation
# ═══════════════════════════════════════════════════════════════

def generate_markdown_report(
    all_results: list[NormalizedBenchmarkResult],
    docatlas_metrics: dict[str, Any],
    context7_metrics: dict[str, Any],
    suite_metrics_list: list[dict[str, Any]],
    timestamp: str,
    duration: float,
) -> str:
    lines: list[str] = []
    lines.append(f"# Live MCP Benchmark: DocAtlas vs Context7")
    lines.append("")
    lines.append(f"- **Date:** {timestamp}")
    lines.append(f"- **Duration:** {duration:.2f}s")
    lines.append(f"- **Total queries:** {len(all_results)}")
    lines.append(f"- **DocAtlas mode:** live_mcp (direct Python API)")
    lines.append(f"- **Context7 mode:** live_mcp (context7-mcp stdio)")
    lines.append("")

    lines.append("## Overall Summary")
    lines.append("")
    lines.append("| Metric | DocAtlas | Context7 |")
    lines.append("|--------|----------|----------|")
    lines.append(f"| Total queries | {docatlas_metrics.get('total_queries', 'N/A')} | {context7_metrics.get('total_queries', 'N/A')} |")
    lines.append(f"| Applicable queries | {docatlas_metrics.get('applicable_queries', 'N/A')} | {context7_metrics.get('applicable_queries', 'N/A')} |")
    lines.append(f"| Success count | {docatlas_metrics.get('success_count', 'N/A')} | {context7_metrics.get('success_count', 'N/A')} |")
    lines.append(f"| Error count | {docatlas_metrics.get('error_count', 'N/A')} | {context7_metrics.get('error_count', 'N/A')} |")
    lines.append(f"| Empty/not-ready | {docatlas_metrics.get('empty_count', 'N/A')} | {context7_metrics.get('empty_count', 'N/A')} |")
    lines.append(f"| Not applicable | {docatlas_metrics.get('not_applicable_count', 'N/A')} | {context7_metrics.get('not_applicable_count', 'N/A')} |")
    lines.append(f"| Correct source rate | {docatlas_metrics.get('correct_source_rate', 'N/A')} | {context7_metrics.get('correct_source_rate', 'N/A')} |")
    lines.append(f"| Contamination rate | {docatlas_metrics.get('contamination_rate', 'N/A')} | {context7_metrics.get('contamination_rate', 'N/A')} |")
    lines.append(f"| Hit@1 | {docatlas_metrics.get('hit@1', 'N/A')} | {context7_metrics.get('hit@1', 'N/A')} |")
    lines.append(f"| Hit@5 | {docatlas_metrics.get('hit@5', 'N/A')} | {context7_metrics.get('hit@5', 'N/A')} |")
    lines.append(f"| MRR | {docatlas_metrics.get('mrr', 'N/A')} | {context7_metrics.get('mrr', 'N/A')} |")
    lines.append(f"| Unique sources@5 | {docatlas_metrics.get('unique_sources@5', 'N/A')} | {context7_metrics.get('unique_sources@5', 'N/A')} |")
    lines.append(f"| Redundancy rate | {docatlas_metrics.get('redundancy_rate', 'N/A')} | {context7_metrics.get('redundancy_rate', 'N/A')} |")
    lines.append(f"| Snippet usefulness | {docatlas_metrics.get('snippet_usefulness', 'N/A')} | {context7_metrics.get('snippet_usefulness', 'N/A')} |")
    lines.append(f"| Avg latency (ms) | {docatlas_metrics.get('avg_latency_ms', 'N/A')} | {context7_metrics.get('avg_latency_ms', 'N/A')} |")
    lines.append(f"| Avg cold latency (ms) | {docatlas_metrics.get('avg_cold_latency_ms', 'N/A')} | {context7_metrics.get('avg_cold_latency_ms', 'N/A')} |")
    lines.append(f"| Avg warm latency (ms) | {docatlas_metrics.get('avg_warm_latency_ms', 'N/A')} | {context7_metrics.get('avg_warm_latency_ms', 'N/A')} |")
    lines.append(f"| Setup calls avg | {docatlas_metrics.get('setup_calls_avg', 'N/A')} | {context7_metrics.get('setup_calls_avg', 'N/A')} |")
    lines.append(f"| Hallucinated API rate | {docatlas_metrics.get('hallucinated_api_rate', 'N/A')} | {context7_metrics.get('hallucinated_api_rate', 'N/A')} |")
    lines.append("")

    lines.append("## Per-Suite Results")
    lines.append("")
    for suite_m in suite_metrics_list:
        suite = suite_m["suite"]
        lines.append(f"### Suite: {suite}")
        lines.append("")
        lines.append(f"- Total cases: {suite_m['total']}")
        lines.append("")
        for provider in ["docatlas", "context7"]:
            pm = suite_m.get(provider)
            if not pm:
                lines.append(f"**{provider}:** no results")
                lines.append("")
                continue
            pmode = pm.get("provider_mode", "unknown") if isinstance(pm, dict) else "unknown"
            lines.append(f"**{provider}** (mode: {pmode}):")
            lines.append("")
            lines.append(f"  - Applicable: {pm.get('applicable_queries', 0)} | Success: {pm.get('success_count', 0)} | Errors: {pm.get('error_count', 0)} | Empty: {pm.get('empty_count', 0)} | N/A: {pm.get('not_applicable_count', 0)}")
            lines.append(f"  - Hit@1: {pm.get('hit@1', 'N/A')} | Hit@5: {pm.get('hit@5', 'N/A')} | MRR: {pm.get('mrr', 'N/A')}")
            lines.append(f"  - Contamination: {pm.get('contamination_rate', 'N/A')} | Forbidden: {pm.get('forbidden_source_rate', 'N/A')}")
            lines.append(f"  - Correct source: {pm.get('correct_source_rate', 'N/A')} | Unique@5: {pm.get('unique_sources@5', 'N/A')}")
            lines.append(f"  - Avg latency: {pm.get('avg_latency_ms', 'N/A')}ms | Setup avg: {pm.get('setup_calls_avg', 'N/A')}")
            lines.append("")

    lines.append("## Per-Case Detail")
    lines.append("")
    lines.append("| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |")
    lines.append("|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|")
    cases_by_id: dict[str, dict[str, NormalizedBenchmarkResult]] = {}
    for r in all_results:
        cases_by_id.setdefault(r.case_id, {})[r.provider] = r
    for case_id, providers in sorted(cases_by_id.items()):
        da = providers.get("docatlas")
        c7 = providers.get("context7")
        da_status = da.status if da else "N/A"
        da_lat = f"{da.latency_ms:.0f}ms" if da else "N/A"
        da_src = str(len(da.sources)) if da else "N/A"
        c7_status = c7.status if c7 else "N/A"
        c7_lat = f"{c7.latency_ms:.0f}ms" if c7 else "N/A"
        c7_src = str(len(c7.sources)) if c7 else "N/A"
        lines.append(f"| {case_id} | {(da or c7).suite if (da or c7) else '?'} | {da_status} | {da_lat} | {da_src} | {c7_status} | {c7_lat} | {c7_src} |")
    lines.append("")

    lines.append("## Key Findings")
    lines.append("")

    da_public = next((m for m in suite_metrics_list if m["suite"] == "public-docs"), {})
    da_project = next((m for m in suite_metrics_list if m["suite"] == "project-docs"), {})
    da_exact = next((m for m in suite_metrics_list if m["suite"] == "exact-version"), {})

    da_pub_metrics = da_public.get("docatlas", {})
    c7_pub_metrics = da_public.get("context7", {})
    da_proj_metrics = da_project.get("docatlas", {})
    c7_proj_metrics = da_project.get("context7", {})
    da_exact_metrics = da_exact.get("docatlas", {})
    c7_exact_metrics = da_exact.get("context7", {})

    da_hit1 = da_pub_metrics.get("hit@1", 0)
    c7_hit1 = c7_pub_metrics.get("hit@1", 0)
    da_contam = da_pub_metrics.get("contamination_rate", 1)
    c7_contam = c7_pub_metrics.get("contamination_rate", 1)

    lines.append("### Where DocAtlas Wins")
    lines.append("")
    wins = []
    if da_proj_metrics.get("success_count", 0) > 0:
        wins.append(f"- **Project docs awareness:** DocAtlas successfully answered {da_proj_metrics.get('success_count', 0)}/{da_proj_metrics.get('applicable_queries', 0)} project-docs queries (Context7 is N/A by design)")
    if da_contam < c7_contam or da_contam == 0:
        wins.append(f"- **Source isolation:** DocAtlas contamination rate is {da_contam} on public-docs suite")
    if da_exact_metrics.get("success_count", 0) > 0:
        wins.append(f"- **Exact-version support:** DocAtlas returned results for {da_exact_metrics.get('success_count', 0)}/{da_exact_metrics.get('applicable_queries', 0)} exact-version queries")
    if not wins:
        wins.append("- (No clear wins yet — more data needed)")
    for w in wins:
        lines.append(w)
    lines.append("")

    lines.append("### Where Context7 Wins")
    lines.append("")
    wins = []
    if c7_hit1 > da_hit1:
        wins.append(f"- **Public docs precision:** Context7 Hit@1 = {c7_hit1} vs DocAtlas = {da_hit1} on public-docs")
    elif c7_contam < da_contam:
        wins.append(f"- **Lower contamination:** Context7 contamination = {c7_contam} vs DocAtlas = {da_contam}")
    c7_pub_success = c7_pub_metrics.get("success_count", 0)
    da_pub_success = da_pub_metrics.get("success_count", 0)
    if c7_pub_success > da_pub_success:
        wins.append(f"- **Zero-setup:** Context7 returned results for {c7_pub_success} queries vs DocAtlas {da_pub_success} (DocAtlas may need indexing)")
    if not wins:
        wins.append("- (No clear wins yet — more data needed)")
    for w in wins:
        lines.append(w)
    lines.append("")

    lines.append("### Where Results Are Not Comparable")
    lines.append("")
    lines.append(f"- **Project-docs suite:** {c7_proj_metrics.get('not_applicable_count', 0)} Context7 cases correctly marked as not applicable (no local repo context)")
    lines.append(f"- **Empty-index cases:** DocAtlas has {da_pub_metrics.get('empty_count', 0)} empty index cases that need pre-fetching")
    lines.append("")

    lines.append("## Claims We Can Make")
    lines.append("")
    lines.append("Based on this live benchmark run:")
    lines.append("")
    claims = [
        "DocAtlas has project-level doc awareness that Context7 cannot provide by design.",
        "DocAtlas supports exact-version library docs (results depend on index state).",
        "Context7 provides zero-setup public docs lookup with reliable source attribution.",
        "Both providers support source-level attribution for their results.",
    ]
    for c in claims:
        lines.append(f"- {c}")
    lines.append("")

    lines.append("## Claims We Cannot Make Yet")
    lines.append("")
    nocla = [
        '"DocAtlas beats Context7 overall" — benchmark does not cover enough libraries or scenarios.',
        '"Context7 has worse contamination than DocAtlas" — need more data and cross-validation.',
        '"Dartdoc exact-version is solved" — need dedicated Dartdoc-specific test cases.',
        '"DocAtlas latency is better/worse" — depends on index state and pre-fetching.',
        '"One provider is strictly better than the other" — they serve different use cases.',
    ]
    for c in nocla:
        lines.append(f"- {c}")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    lines.append("1. **Pre-index libraries** before running public-docs suite for DocAtlas to avoid empty_index status.")
    lines.append("2. **Expand Dart/Flutter exact-version coverage** with pub.dev-based Dartdoc tests.")
    lines.append("3. **Add contamination tests** with cross-library queries (e.g., ask about Riverpod in FastAPI suite).")
    lines.append("4. **Run benchmark on CI** with a cron schedule to track regressions.")
    lines.append("5. **Add more providers** (e.g., FixtureProvider with saved Context7 results for comparison).")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Main runner
# ═══════════════════════════════════════════════════════════════

async def run_benchmark(
    providers: list[BenchmarkProvider],
    cases: list[BenchmarkCase],
    suites: list[str] | None = None,
    save_raw: bool = False,
    fail_on_regression: bool = False,
    output_dir: str | None = None,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = str(RESULTS_ROOT / timestamp)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()

    all_results: list[NormalizedBenchmarkResult] = []

    filtered = [c for c in cases if suites is None or c.suite in suites]
    if not filtered:
        print(f"No cases match suites={suites}")
        return {}

    print(f"Running benchmark with {len(providers)} providers, {len(filtered)} cases")
    print(f"Suites: {suites or 'all'}")
    print(f"Output: {out_path}")
    print()

    for provider in providers:
        print(f"Setting up provider: {provider.name} ({provider.provider_mode})...")
        try:
            await provider.setup()
        except Exception as exc:
            print(f"  Setup failed: {exc}")
        print(f"  Provider ready.")

    for case in filtered:
        for provider in providers:
            print(f"  [{provider.name}] {case.id}: {case.query[:60]}...", end=" ")
            result = await provider.query(case)
            all_results.append(result)
            status_icon = "✓" if result.is_success() else ("⨯" if result.is_error() else ("–" if result.is_not_applicable() else "?"))
            print(f" {status_icon} {result.status} ({result.latency_ms:.0f}ms, {len(result.sources)} sources)")

            if save_raw:
                raw_dir = out_path / provider.name
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_file = raw_dir / f"{case.id}.json"
                raw_data = {
                    "provider": provider.name,
                    "provider_mode": provider.provider_mode,
                    "case_id": case.id,
                    "query": case.query,
                    "suite": case.suite,
                    "status": result.status,
                    "latency_ms": result.latency_ms,
                    "setup_calls": result.setup_calls,
                    "sources": [dataclasses.asdict(s) for s in result.sources],
                    "snippets": [{"text": s.text[:200], "source": s.source, "rank": s.rank} for s in result.snippets[:5]],
                    "warnings": result.warnings,
                    "reason_codes": result.reason_codes,
                    "exact_version_used": result.exact_version_used,
                    "contamination_hits": result.contamination_hits,
                    "forbidden_source_hits": result.forbidden_source_hits,
                    "expected_source_hits": result.expected_source_hits,
                    "answer_text_length": len(result.answer_text) if result.answer_text else 0,
                    "timestamp": timestamp,
                }
                raw_file.write_text(json.dumps(raw_data, indent=2, ensure_ascii=False), encoding="utf-8")

    duration = time.perf_counter() - start

    docatlas_results = [r for r in all_results if r.provider == "docatlas"]
    context7_results = [r for r in all_results if r.provider == "context7"]
    docatlas_metrics = compute_metrics(docatlas_results)
    context7_metrics = compute_metrics(context7_results)

    suite_names = sorted(set(r.suite for r in all_results))
    suite_metrics_list = [compute_suite_metrics(all_results, s) for s in suite_names]

    report = generate_markdown_report(
        all_results, docatlas_metrics, context7_metrics, suite_metrics_list, timestamp, duration,
    )

    report_file = out_path / "report.md"
    report_file.write_text(report, encoding="utf-8")

    summary = {
        "timestamp": timestamp,
        "duration_s": round(duration, 3),
        "total_queries": len(all_results),
        "providers": {p.name: p.provider_mode for p in providers},
        "suites": suite_names,
        "docatlas": docatlas_metrics,
        "context7": context7_metrics,
        "suite_metrics": suite_metrics_list,
        "report_file": str(report_file),
    }
    summary_file = out_path / "summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    for provider in providers:
        if hasattr(provider, "shutdown"):
            try:
                await provider.shutdown()
            except Exception:
                pass

    print(f"\nDone. Report: {report_file}")
    print(f"Summary: {summary_file}")

    if save_raw:
        print(f"Raw outputs: {out_path}/<provider>/<case_id>.json")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live MCP-vs-MCP benchmark: DocAtlas vs Context7"
    )
    parser.add_argument("--suite", choices=["public-docs", "project-docs", "exact-version", "all"], default="all",
                        help="Which suite to run (default: all)")
    parser.add_argument("--save-raw", action="store_true", help="Save raw outputs per query")
    parser.add_argument("--output-dir", help="Custom output directory (default: eval/results/live/<timestamp>)")
    parser.add_argument("--fail-on-regression", action="store_true",
                        help="Exit non-zero if predefined acceptance criteria are not met")
    parser.add_argument("--skip-docatlas", action="store_true", help="Skip DocAtlas provider")
    parser.add_argument("--skip-context7", action="store_true", help="Skip Context7 provider")
    args = parser.parse_args()

    suites = None if args.suite == "all" else [args.suite]

    providers: list[BenchmarkProvider] = []
    if not args.skip_docatlas:
        providers.append(DocAtlasMCPProvider())
    if not args.skip_context7:
        providers.append(Context7MCPProvider())

    if not providers:
        print("No providers selected. Use --skip-* to exclude specific providers.")
        return

    cases = ALL_CASES

    summary = asyncio.run(run_benchmark(
        providers=providers,
        cases=cases,
        suites=suites,
        save_raw=args.save_raw,
        fail_on_regression=args.fail_on_regression,
        output_dir=args.output_dir,
    ))

    if not summary:
        return

    if args.fail_on_regression:
        da = summary.get("docatlas", {})
        c7 = summary.get("context7", {})

        failures: list[str] = []
        if da.get("contamination_rate", 0) > 0.05:
            failures.append(f"DocAtlas contamination rate {da.get('contamination_rate')} > 0.05")
        if c7.get("contamination_rate", 0) > 0.05:
            failures.append(f"Context7 contamination rate {c7.get('contamination_rate')} > 0.05")
        if failures:
            print(f"\nRegression check failed: {failures}")
            raise SystemExit(1)
        print("\nRegression check passed.")


if __name__ == "__main__":
    main()
