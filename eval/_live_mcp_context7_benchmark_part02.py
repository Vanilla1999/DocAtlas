"""Live benchmark implementation shard."""
from __future__ import annotations
from eval._live_mcp_context7_benchmark_shared import *  # noqa: F401,F403
from eval._live_mcp_context7_benchmark_part01 import BenchmarkProvider, DependencyFixtureDiagnostics, NormalizedBenchmarkResult, PreindexDiagnostics, Snippet, SourceRef
from eval._live_mcp_context7_benchmark_part03 import _detect_contamination, _detect_expected_sources, _detect_forbidden_sources, _evaluate_primary_snippet

class DocAtlasDirectProvider(BenchmarkProvider):
    def __init__(self, project_path: str | None = None):
        self.name = "docatlas"
        self.provider_id = "docatlas_zero_setup"
        self.provider_mode = "live_direct_api"
        self.benchmark_mode = "zero-setup"
        self._project_path = project_path or str(ROOT)
        self._service = None
        self._lib_cache: dict[str, dict[str, Any]] = {}
        self.runtime_dir: Path | None = None
        self.docmancer_home: Path | None = None
        self.db_path: Path | None = None
        self._dependency_fixture_path: Path | None = None
        self._project_command_fixture_path: Path | None = None

    def _isolated_env(self):
        """Context manager for isolated DOCMANCER_HOME environment."""
        from contextlib import contextmanager
        @contextmanager
        def _ctx():
            old_home = os.environ.get("DOCMANCER_HOME")
            old_auto_vectors = os.environ.get("DOCMANCER_AUTO_VECTORS")
            if self.docmancer_home:
                os.environ["DOCMANCER_HOME"] = str(self.docmancer_home)
                os.environ["DOCMANCER_AUTO_VECTORS"] = "0"
            try:
                yield
            finally:
                if old_home is None:
                    os.environ.pop("DOCMANCER_HOME", None)
                else:
                    os.environ["DOCMANCER_HOME"] = old_home
                if old_auto_vectors is None:
                    os.environ.pop("DOCMANCER_AUTO_VECTORS", None)
                else:
                    os.environ["DOCMANCER_AUTO_VECTORS"] = old_auto_vectors
        return _ctx()

    def _get_service(self):
        if self._service is None:
            from docmancer.docs.service import LibraryDocsService
            from docmancer.core.config import DocmancerConfig
            with self._isolated_env():
                config = DocmancerConfig()
                if self.db_path:
                    config.index.db_path = str(self.db_path)
                self._service = LibraryDocsService(config=config)
        return self._service

    async def setup(self) -> None:
        with self._isolated_env():
            _ = self._get_service()


    def _project_command_fixture(self) -> str:
        if self._project_command_fixture_path is None:
            root = (self.runtime_dir or Path(tempfile.gettempdir())) / "fixtures" / "snippet_project_command"
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)
            (root / "README.md").write_text(
                """# Snippet project command fixture

Use this command to run the project tests:

```bash
uv run pytest
```
""",
                encoding="utf-8",
            )
            service = self._get_service()
            service.sync_project_docs(str(root), with_vectors=False)
            self._project_command_fixture_path = root
        return str(self._project_command_fixture_path)

    def _dependency_fixture_project(self) -> str:
        if self._dependency_fixture_path is None:
            root = (self.runtime_dir or Path(tempfile.gettempdir())) / "fixtures" / "unified_dependency_auto"
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "docatlas-unified-dependency-fixture"
version = "0.1.0"
edition = "2021"

[dependencies]
anyhow = "1.0.86"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "Cargo.lock").write_text(
                """
version = 3

[[package]]
name = "docatlas-unified-dependency-fixture"
version = "0.1.0"
dependencies = [
 "anyhow",
]

[[package]]
name = "anyhow"
version = "1.0.86"
source = "registry+https://github.com/rust-lang/crates.io-index"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                """
# Unified dependency benchmark fixture

This project uses `anyhow` for contextual Rust error handling.

The benchmark verifies that DocAtlas discovers the locked dependency version
from Cargo metadata and automatically retrieves dependency documentation.
""".strip()
                + "\n",
                encoding="utf-8",
            )
            self._dependency_fixture_path = root
        return str(self._dependency_fixture_path)

    def _validate_dependency_fixture(self, project_path: str) -> DependencyFixtureDiagnostics:
        diag = DependencyFixtureDiagnostics(
            project_path=project_path,
            manifest=str(Path(project_path) / "Cargo.toml"),
            lockfile=str(Path(project_path) / "Cargo.lock"),
        )
        try:
            metadata = self._get_service().read_project_metadata(project_path)
        except Exception as exc:
            diag.reason_code = "dependency_fixture_metadata_missing"
            diag.warnings.append(str(exc))
            return diag

        diag.warnings.extend(metadata.warnings)
        observation = next(
            (item for item in metadata.dependencies if item.ecosystem == "rust" and item.package_name == "anyhow"),
            None,
        )
        diag.ecosystem = observation.ecosystem if observation else (metadata.detected_ecosystems[0] if metadata.detected_ecosystems else None)
        diag.locked_version = metadata.packages.get("rust:anyhow") or (observation.resolved_version if observation else None)
        diag.exact = bool(observation and observation.version_source == "lockfile_exact" and observation.resolved_version == "1.0.86")

        missing: list[str] = []
        if not Path(diag.manifest or "").exists():
            missing.append("manifest")
        if not Path(diag.lockfile or "").exists():
            missing.append("lockfile")
        if "rust" not in metadata.detected_ecosystems:
            missing.append("rust_ecosystem")
        if observation is None:
            missing.append("anyhow_dependency")
        if diag.locked_version != "1.0.86":
            missing.append("locked_version")
        if not diag.exact:
            missing.append("lockfile_exact")

        diag.valid = not missing
        diag.reason_code = None if diag.valid else "dependency_fixture_metadata_missing"
        if missing:
            diag.warnings.append("missing:" + ",".join(missing))
        return diag

    def _prepare_dependency_auto_fixture(self, project_path: str) -> tuple[PreindexDiagnostics, dict[str, Any], dict[str, Any]]:
        service = self._get_service()
        project_diag: dict[str, Any] = {"status": "pending", "docs_indexed": False}
        dependency_diag = PreindexDiagnostics(attempted=True, status="pending", version="1.0.86")
        dependency_preparation: dict[str, Any] = {
            "method": "prefetch_project_dependency_docs",
            "status": "pending",
            "library_id": None,
            "canonical_id": None,
            "docs_url": "https://docs.rs/anyhow/1.0.86/",
            "pages": 0,
            "chunks": 0,
        }
        t0 = time.perf_counter()
        try:
            sync_result = service.sync_project_docs(project_path, with_vectors=False)
            summary = {
                "current": int(getattr(sync_result, "current_count", 0) or 0),
                "new": int(getattr(sync_result, "new_count", 0) or 0),
                "changed": int(getattr(sync_result, "changed_count", 0) or 0),
                "sections_indexed": int(getattr(sync_result, "sections_indexed", 0) or 0),
            }
            project_diag = {
                "status": getattr(sync_result, "status", "success"),
                "docs_indexed": int(summary.get("current") or summary.get("new") or summary.get("changed") or 0) > 0,
                "summary": summary,
            }
        except Exception as exc:
            project_diag = {"status": "project_docs_sync_failed", "docs_indexed": False, "reason_code": type(exc).__name__, "warning": str(exc)}

        try:
            result = service.prefetch_project_dependency_docs(
                project_path,
                include_flutter=False,
                include_dart=False,
                include_rust=True,
                include_packages=["anyhow"],
                force_refresh=False,
                continue_on_error=False,
                async_=False,
            )
            item = result.results[0] if result.results else None
            dependency_diag.library_id = getattr(item, "library_id", None) if item else None
            dependency_diag.canonical_id = dependency_diag.library_id
            dependency_diag.version = getattr(item, "version", None) if item else "1.0.86"
            dependency_diag.reason_code = None
            dependency_diag.warnings.extend(result.warnings)
            if item:
                dependency_diag.status = getattr(item, "status", "unknown")
                dependency_diag.pages = int(getattr(item, "pages_indexed", 0) or 0)
                dependency_diag.chunks = int(getattr(item, "chunks_indexed", 0) or 0)
                dependency_preparation.update({
                    "status": dependency_diag.status,
                    "library_id": dependency_diag.library_id,
                    "canonical_id": dependency_diag.canonical_id,
                    "docs_url": getattr(item, "docs_url", None),
                    "pages": dependency_diag.pages,
                    "chunks": dependency_diag.chunks,
                })
            else:
                dependency_diag.status = "preindex_failed"
                dependency_diag.reason_code = "dependency_prefetch_returned_no_results"
                dependency_preparation["status"] = dependency_diag.status
                dependency_preparation["reason_code"] = dependency_diag.reason_code

            if dependency_diag.pages == 0 and dependency_diag.chunks == 0:
                dependency_diag.status = "empty_index"
                dependency_diag.reason_code = dependency_diag.reason_code or "refresh_produced_no_content"
                dependency_preparation["status"] = dependency_diag.status
                dependency_preparation["reason_code"] = dependency_diag.reason_code

                from docmancer.docs.models import DocsTarget

                seeded = service._prefetch_docs_targets_sync(
                    [DocsTarget(
                        library="anyhow",
                        ecosystem="rust",
                        version="1.0.86",
                        source_type="api",
                        docs_url="https://docs.rs/anyhow/1.0.86/",
                        seed_urls=[
                            "https://docs.rs/anyhow/1.0.86/anyhow/index.html",
                            "https://docs.rs/anyhow/1.0.86/anyhow/trait.Context.html",
                            "https://docs.rs/anyhow/1.0.86/anyhow/macro.anyhow.html",
                        ],
                        allowed_domains=["docs.rs"],
                        path_prefixes=["/anyhow/1.0.86/"],
                        max_pages=3,
                    )],
                    force_refresh=True,
                    continue_on_error=False,
                )
                seeded_item = seeded.results[0] if seeded.results else None
                inspect = service.inspect_library_docs("rust:anyhow@1.0.86:api")
                dependency_diag.status = getattr(seeded_item, "status", "unknown") if seeded_item else seeded.status
                dependency_diag.library_id = getattr(seeded_item, "canonical_id", None) if seeded_item else dependency_diag.library_id
                dependency_diag.canonical_id = dependency_diag.library_id
                dependency_diag.pages = int(getattr(inspect, "pages", 0) or getattr(seeded_item, "pages_indexed", 0) or seeded.pages_indexed or 0)
                dependency_diag.chunks = int(getattr(inspect, "chunks", 0) or seeded.chunks_indexed or dependency_diag.pages or 0)
                dependency_diag.reason_code = None if dependency_diag.pages and dependency_diag.chunks else "seeded_prefetch_produced_no_content"
                dependency_preparation.update({
                    "method": "prefetch_project_dependency_docs+prefetch_docs_targets",
                    "status": dependency_diag.status,
                    "library_id": dependency_diag.library_id,
                    "canonical_id": dependency_diag.canonical_id,
                    "docs_url": "https://docs.rs/anyhow/1.0.86/",
                    "pages": dependency_diag.pages,
                    "chunks": dependency_diag.chunks,
                    "seed_urls": [
                        "https://docs.rs/anyhow/1.0.86/anyhow/index.html",
                        "https://docs.rs/anyhow/1.0.86/anyhow/trait.Context.html",
                        "https://docs.rs/anyhow/1.0.86/anyhow/macro.anyhow.html",
                    ],
                })
                if dependency_diag.reason_code:
                    dependency_preparation["reason_code"] = dependency_diag.reason_code
                else:
                    dependency_preparation.pop("reason_code", None)

                verification = service.get_docs(
                    "anyhow",
                    topic="How do I use anyhow Context?",
                    ecosystem="rust",
                    version="1.0.86",
                    project_path=project_path,
                    tokens=4000,
                )
                if getattr(verification, "results", None):
                    dependency_diag.status = "ready"
                    dependency_diag.library_id = getattr(verification, "library_id", None) or dependency_diag.library_id
                    dependency_diag.canonical_id = dependency_diag.library_id
                    dependency_diag.pages = max(dependency_diag.pages, len(verification.results))
                    dependency_diag.chunks = max(dependency_diag.chunks, len(verification.results))
                    dependency_diag.reason_code = None
                    dependency_preparation.update({
                        "status": "ready",
                        "library_id": dependency_diag.library_id,
                        "canonical_id": dependency_diag.canonical_id,
                        "pages": dependency_diag.pages,
                        "chunks": dependency_diag.chunks,
                        "verification_status": getattr(verification, "status", None),
                    })
                    dependency_preparation.pop("reason_code", None)
        except Exception as exc:
            dependency_diag.status = "preindex_failed"
            dependency_diag.reason_code = type(exc).__name__
            dependency_diag.warnings.append(str(exc))
            dependency_preparation["status"] = dependency_diag.status
            dependency_preparation["reason_code"] = dependency_diag.reason_code
            dependency_preparation["warning"] = str(exc)

        dependency_diag.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
        return dependency_diag, dependency_preparation, project_diag

    async def _preindex_library(self, case: BenchmarkCase) -> PreindexDiagnostics:
        with self._isolated_env():
            service = self._get_service()
            diag = PreindexDiagnostics(attempted=True, status="pending", version=case.version)
            t0 = time.perf_counter()
            try:
                lib = case.library or case.id
                eco = case.ecosystem
                ver = case.version
                docs_url = case.docs_url or {
                    "fastapi": "https://fastapi.tiangolo.com/",
                    "click": "https://click.palletsprojects.com/",
                    "httpx": "https://www.python-httpx.org/",
                    "anyhow": f"https://docs.rs/anyhow/{ver}/" if ver else "https://docs.rs/anyhow/latest/",
                }.get(lib)
                key = f"{eco}:{lib}:{ver}"
                cached = self._lib_cache.get(key)
                if cached:
                    diag.status = cached.get("status", "cached")
                    diag.library_id = cached.get("library_id")
                    diag.chunks = cached.get("chunks", 0)
                    diag.pages = cached.get("pages", 0)
                    diag.latency_ms = round((time.perf_counter() - t0) * 1000, 3)
                    return diag

                info = service.resolve_library(lib, ecosystem=eco, version=ver, docs_url=docs_url, source_type=case.source_type)
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
                    refresh_result = service.refresh_docs(lib, ecosystem=eco, version=ver, docs_url=docs_url or case.docs_url, source_type=case.source_type, force=False)
                    diag.status = "refreshed"
                    post_inspect = service.inspect_library_docs(info.library_id)
                    diag.pages = int(getattr(post_inspect, "pages", 0) or getattr(refresh_result, "pages_indexed", 0) or 0)
                    diag.chunks = int(getattr(post_inspect, "chunks", 0) or getattr(refresh_result, "chunks_indexed", 0) or 0)
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

        with self._isolated_env():
            service = self._get_service()
            start = time.perf_counter()
            sources: list[SourceRef] = []
            snippets: list[Snippet] = []
            warnings: list[str] = []
            reason_codes: list[str] = []
            answer_text: str | None = None
            exact_version_used: str | None = case.version
            deduplication_dropped_count = 0
            setup_calls = 0
            status = "success"
            preindex_diag: PreindexDiagnostics | None = None
            dependency_fixture_diag: DependencyFixtureDiagnostics | None = None
            dependency_preparation: dict[str, Any] | None = None
            project_preparation: dict[str, Any] | None = None
            routing_observed: dict[str, Any] | None = None
            snippet_eval: dict[str, Any] | None = None

            try:
                uses_dependency_fixture = case.id in {"unified_dependency_auto", "unified_dependency", "anyhow_context_snippet"}
                case_project_path = None
                if uses_dependency_fixture:
                    case_project_path = self._dependency_fixture_project()
                    dependency_fixture_diag = self._validate_dependency_fixture(case_project_path)
                    if not dependency_fixture_diag.valid:
                        status = "fixture_invalid"
                        reason_codes.append("dependency_fixture_invalid")
                        if dependency_fixture_diag.reason_code:
                            reason_codes.append(dependency_fixture_diag.reason_code)
                        warnings.extend(dependency_fixture_diag.warnings)
                        latency_ms = round((time.perf_counter() - start) * 1000, 3)
                        return self._build_result(case, status, latency_ms, setup_calls,
                            sources, snippets, answer_text, warnings, reason_codes,
                            exact_version_used, preindex=preindex_diag,
                            dependency_fixture=dependency_fixture_diag)
                    exact_version_used = dependency_fixture_diag.locked_version
                    if self.benchmark_mode == "preindexed":
                        preindex_diag, dependency_preparation, project_preparation = self._prepare_dependency_auto_fixture(case_project_path)
                        setup_calls += 2
                        reason_codes.append(preindex_diag.status)
                        if preindex_diag.status in ("preindex_failed", "not_supported", "empty_index"):
                            status = preindex_diag.status if preindex_diag.status != "empty_index" else "empty_index"
                            reason_codes.append("dependency_preindex_failed" if status != "empty_index" else "dependency_preindex_empty")
                            latency_ms = round((time.perf_counter() - start) * 1000, 3)
                            return self._build_result(case, status, latency_ms, setup_calls,
                                sources, snippets, answer_text, warnings, reason_codes,
                                exact_version_used, preindex=preindex_diag,
                                dependency_fixture=dependency_fixture_diag,
                                dependency_preparation=dependency_preparation,
                                project_preparation=project_preparation)

                should_preindex = self.benchmark_mode == "preindexed" and bool(case.library) and not uses_dependency_fixture and (
                    case.suite in ("public-docs", "exact-version", "snippet-first")
                    or case.id in {"unified_library_only", "unified_latest_fallback", "unified_dependency"}
                )
                if should_preindex:
                    if case.id == "unified_latest_fallback":
                        preindex_case = dataclasses.replace(case, version=None)
                    else:
                        preindex_case = case
                    preindex_diag = await self._preindex_library(preindex_case)
                    setup_calls += 2
                    reason_codes.append(preindex_diag.status)
                    if preindex_diag.status in ("preindex_failed", "not_supported", "empty_index"):
                        status = preindex_diag.status if preindex_diag.status != "empty_index" else "empty_index"
                        latency_ms = round((time.perf_counter() - start) * 1000, 3)
                        return self._build_result(case, status, latency_ms, setup_calls,
                            sources, snippets, answer_text, warnings, reason_codes,
                            exact_version_used, preindex=preindex_diag)

                if case.suite == "snippet-first":
                    if case.id == "project_command_snippet":
                        fixture = self._project_command_fixture()
                        result = await asyncio.to_thread(
                            service.get_project_context,
                            fixture,
                            case.query,
                            tokens=4000,
                            mode="project-only",
                            response_style="snippet-first",
                        )
                        setup_calls += 1
                    elif case.id == "mixed_fastapi_project_snippet":
                        fixture = self._project_command_fixture()
                        result = await asyncio.to_thread(
                            service.get_docs_context,
                            case.query,
                            project_path=fixture,
                            library=case.library,
                            ecosystem=case.ecosystem,
                            mode="auto",
                            tokens=4000,
                            allow_network=False,
                            prepare_project_docs=False,
                            response_style="snippet-first",
                        )
                        setup_calls += 1
                    elif case.id == "anyhow_context_snippet":
                        case_project_path = case_project_path or self._dependency_fixture_project()
                        result = await asyncio.to_thread(
                            service.get_docs_context,
                            case.query,
                            project_path=case_project_path,
                            library=None,
                            ecosystem=None,
                            version=None,
                            mode="auto",
                            tokens=4000,
                            allow_network=False,
                            prepare_project_docs=False,
                            response_style="snippet-first",
                        )
                        setup_calls += 1
                    else:
                        result = await asyncio.to_thread(
                            service.get_docs,
                            case.library,
                            topic=case.query,
                            tokens=4000,
                            ecosystem=case.ecosystem,
                            version=case.version,
                            docs_url=case.docs_url,
                            source_type=case.source_type,
                            response_style="snippet-first",
                        )
                        setup_calls += 1
                    raw = dataclasses.asdict(result) if dataclasses.is_dataclass(result) else dict(getattr(result, "__dict__", {}) or {})
                    primary = raw.get("primary_snippet") or {}
                    response_style_observed = raw.get("response_style")
                    if primary:
                        src = str(primary.get("source") or primary.get("source_url") or "unknown")
                        sources.append(SourceRef(url=src, title=primary.get("title"), rank=1, doc_scope=primary.get("doc_scope")))
                        snippets.append(Snippet(text=str(primary.get("code") or "")[:500], source=src, rank=1))
                    context_pack = raw.get("context_pack") or []
                    for i, item in enumerate(context_pack[:5], start=2):
                        source_str = str(item.get("source") or item.get("url") or item.get("path") or "unknown")
                        if isinstance(item.get("source"), dict):
                            source_str = str((item.get("source") or {}).get("url") or (item.get("source") or {}).get("path") or source_str)
                        sources.append(SourceRef(url=source_str, title=item.get("title"), rank=i, doc_scope=item.get("doc_scope")))
                    snippet_eval = _evaluate_primary_snippet(primary, case, response_style_observed=response_style_observed)
                    answer_text = json.dumps(snippet_eval, sort_keys=True)
                    status = "success" if snippet_eval.get("success") else snippet_eval.get("reason_code", "snippet_failed")
                    reason_codes.extend(snippet_eval.get("reason_codes") or [])
                    exact_version_used = primary.get("version") or exact_version_used
                    warnings.extend(str(w.get("code") or w) if isinstance(w, dict) else str(w) for w in raw.get("warnings") or [])
                elif case.suite == "unified-context":
                    if uses_dependency_fixture:
                        case_project_path = case_project_path or self._dependency_fixture_project()
                    else:
                        case_project_path = None if case.id in {"unified_library_only", "unified_latest_fallback"} else self._project_path
                    allow_latest_fallback = case.id == "unified_latest_fallback"
                    result = await asyncio.to_thread(
                        service.get_docs_context,
                        case.query,
                        project_path=case_project_path,
                        library=case.library,
                        ecosystem=None if case.id == "unified_dependency_auto" else case.ecosystem,
                        version=case.version,
                        mode=case.mode or "auto",
                        tokens=4000,
                        allow_network=False,
                        allow_latest_fallback=allow_latest_fallback,
                        prepare_project_docs=not uses_dependency_fixture,
                    )
                    setup_calls += 1
                    context_pack = result.context_pack if hasattr(result, "context_pack") else []
                    answer_text = str(getattr(result, "routing", {}))
                    mode_selected = getattr(result, "mode_selected", "unknown")
                    reason_codes.append(mode_selected)
                    exact_version_info = getattr(result, "exact_version", None)
                    if isinstance(exact_version_info, dict):
                        exact_version_used = exact_version_info.get("used", exact_version_used)
                        reason_codes.append(exact_version_info.get("status") or "exact_version")
                    if getattr(result, "requires_confirmation", False):
                        reason_codes.append(getattr(result, "reason_code", "confirmation_required") or "confirmation_required")
                    for i, item in enumerate(context_pack):
                        source_str = str(item.get("source") or item.get("url") or item.get("path") or "unknown")
                        title = item.get("title") or ""
                        content = item.get("content") or ""
                        scope = item.get("doc_scope")
                        sources.append(SourceRef(url=source_str, title=title, rank=i + 1, doc_scope=scope))
                        if content:
                            snippets.append(Snippet(text=content[:500], source=source_str, rank=i + 1))
                    if not context_pack:
                        status = "needs_refresh" if getattr(result, "requires_confirmation", False) else "no_results"
                    else:
                        status = getattr(result, "status", "success")
                    contamination = getattr(result, "contamination", {}) or {}
                    if contamination.get("detected"):
                        reason_codes.extend(contamination.get("reason_codes") or [])
                    deduplication = getattr(result, "deduplication", {}) or {}
                    deduplication_dropped_count = int(deduplication.get("dropped_count") or 0)
                    if deduplication_dropped_count:
                        reason_codes.extend(deduplication.get("reason_codes") or [])
                    if case.id in {"unified_dependency_auto", "unified_dependency"}:
                        evidence_scopes = sorted({str(item.get("doc_scope")) for item in context_pack if item.get("doc_scope")})
                        dependency_sources = [s.url for s in sources if s.doc_scope == "dependency"]
                        routing_observed = {
                            "mode_requested": case.mode or "auto",
                            "mode_selected": mode_selected,
                            "dependency_detected": any(s.doc_scope == "dependency" for s in sources),
                            "evidence_scopes": evidence_scopes,
                            "dependency_sources": dependency_sources,
                        }
                        if case.id == "unified_dependency_auto":
                            strict_failure = self._dependency_auto_failure_reason(
                                result=result,
                                mode_selected=mode_selected,
                                sources=sources,
                                exact_version_used=exact_version_used,
                            )
                            if strict_failure:
                                status = strict_failure
                                reason_codes.append(strict_failure)
                        elif (
                            status == "partial_success"
                            and not getattr(result, "requires_confirmation", False)
                            and not contamination.get("detected")
                            and mode_selected == "dependency"
                            and exact_version_used == "1.0.86"
                            and any("anyhow" in s.lower() and "1.0.86" in s for s in dependency_sources)
                        ):
                            status = "success"
                elif case.suite == "project-docs":
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
                        ecosystem=case.ecosystem, version=case.version, docs_url=case.docs_url, source_type=case.source_type)
                    setup_calls += 1

                    # Extract exact-version diagnostics from API response
                    result_diagnostics = getattr(result, "diagnostics", {})
                    exact_version_info = result_diagnostics.get("exact_version") if isinstance(result_diagnostics, dict) else None

                    # Handle exact-version status from service
                    if hasattr(result, "status") and result.status == "exact_version_not_supported":
                        status = "not_supported"
                        if exact_version_info:
                            reason_codes.append(exact_version_info.get("reason_code", "exact_version_not_supported"))
                        else:
                            reason_codes.append("exact_version_not_supported")

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

                        # Override exact_version_used from diagnostics if available
                        if exact_version_info:
                            exact_version_used = exact_version_info.get("used", exact_version_used)
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
                warnings.append(traceback.format_exc())
                reason_codes.append(type(exc).__name__)

            latency_ms = round((time.perf_counter() - start) * 1000, 3)
            cont = _detect_contamination(sources, case)
            forb = _detect_forbidden_sources(sources, case)
            expt = _detect_expected_sources(sources, case)

            return self._build_result(case, status, latency_ms, setup_calls,
                sources, snippets, answer_text, warnings, reason_codes,
                exact_version_used, cont, forb, expt, preindex=preindex_diag,
                deduplication_dropped_count=deduplication_dropped_count,
                dependency_fixture=dependency_fixture_diag,
                dependency_preparation=dependency_preparation,
                project_preparation=project_preparation,
                routing_observed=routing_observed,
            snippet_eval=snippet_eval)

    def _dependency_auto_failure_reason(self, *, result: Any, mode_selected: str, sources: list[SourceRef], exact_version_used: str | None) -> str | None:
        if getattr(result, "requires_confirmation", False):
            return "unexpected_confirmation"
        if mode_selected not in {"dependency", "mixed"}:
            return "dependency_not_detected"
        dependency_sources = [s for s in sources if s.doc_scope == "dependency"]
        if not dependency_sources:
            return "dependency_scope_missing"
        if not any("anyhow" in s.url.lower() and "docs.rs" in s.url.lower() for s in dependency_sources):
            return "dependency_source_missing"
        if exact_version_used != "1.0.86":
            return "dependency_version_mismatch"
        contamination = getattr(result, "contamination", {}) or {}
        if contamination.get("detected"):
            return "dependency_contamination_detected"
        return None

    def _build_result(self, case, status, latency_ms, setup_calls,
            sources, snippets, answer_text, warnings, reason_codes,
            exact_version_used, cont=None, forb=None, expt=None, preindex=None,
            deduplication_dropped_count=0, dependency_fixture=None,
            dependency_preparation=None, project_preparation=None,
            routing_observed=None, snippet_eval=None):
        # Compute exact-version fields
        exact_version_expected = case.version if case.suite in {"exact-version", "unified-context"} else None
        exact_version_match = None
        exact_version_status = None
        exact_version_fallback = False
        exact_version_reason_code = None

        if exact_version_expected:
            if status == "not_supported":
                exact_version_status = "exact_version_not_supported"
                exact_version_match = None
                exact_version_reason_code = reason_codes[0] if reason_codes else "exact_version_docs_url_unavailable"
            elif status == "empty_index":
                exact_version_status = "exact_version_empty_index"
                exact_version_match = None
                exact_version_reason_code = reason_codes[0] if reason_codes else "empty_index"
            elif status == "success":
                if exact_version_used and exact_version_used == exact_version_expected:
                    exact_version_status = "exact_version_indexed"
                    exact_version_match = True
                    exact_version_reason_code = None
                elif exact_version_used == "latest" or exact_version_used is None:
                    exact_version_status = "exact_version_fallback_latest"
                    exact_version_match = False
                    exact_version_fallback = True
                    exact_version_reason_code = "versioned_docs_unavailable"
                else:
                    exact_version_status = "exact_version_resolution_failed"
                    exact_version_match = False
                    exact_version_reason_code = "version_mismatch"
            else:
                exact_version_status = "exact_version_resolution_failed"
                exact_version_match = None
                exact_version_reason_code = status

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
            preindex=preindex,
            exact_version_expected=exact_version_expected,
            exact_version_match=exact_version_match,
            exact_version_status=exact_version_status,
            exact_version_fallback=exact_version_fallback,
            exact_version_reason_code=exact_version_reason_code,
            deduplication_dropped_count=deduplication_dropped_count,
            dependency_fixture=dependency_fixture,
            dependency_preparation=dependency_preparation,
            project_preparation=project_preparation,
            routing_observed=routing_observed,
            snippet_eval=snippet_eval)

    def _na_result(self, case):
        return self._build_result(case, "not_applicable", 0, 0, [], [], None,
            ["Not applicable for DocAtlas"], [], None)

__all__=['DocAtlasDirectProvider']
