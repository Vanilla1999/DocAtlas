from __future__ import annotations

import importlib
import json
import logging
import os
import hashlib
import fnmatch
from pathlib import Path
from typing import Any, Callable
from datetime import datetime, timezone



from docmancer.core.config import DocmancerConfig
from docmancer.core.models import Document, RetrievedChunk
from docmancer.core.sqlite_store import SQLiteStore, document_section_count

logger = logging.getLogger(__name__)

_PARSERS = {
    ".txt": "docmancer.connectors.parsers.text:TextLoader",
    ".md": "docmancer.connectors.parsers.markdown:MarkdownLoader",
    ".markdown": "docmancer.connectors.parsers.markdown:MarkdownLoader",
    ".pdf": "docmancer.connectors.parsers.pdf:PDFLoader",
    ".docx": "docmancer.connectors.parsers.docx:DOCXLoader",
    ".rtf": "docmancer.connectors.parsers.rtf:RTFLoader",
    ".html": "docmancer.connectors.parsers.html:HTMLLoader",
    ".htm": "docmancer.connectors.parsers.html:HTMLLoader",
}

SOURCE_DERIVED_METADATA_KEYS = {
    "docset_root",
    "canonical_url",
    "source_url",
    "title",
    "description",
    "section_path",
    "lang",
    "format",
}


def _import_class(dotted_path: str) -> type:
    module_path, class_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class DocmancerAgent:
    """High-level API for local documentation context compression."""

    def __init__(self, config: DocmancerConfig | None = None, _lazy_init: bool = False):
        self.config = config or DocmancerConfig()
        self._store: SQLiteStore | None = None
        self.last_ingest_report_path: Path | None = None
        self.last_ingest_skips: list[dict[str, str]] = []
        self.last_discovery_diagnostics: dict[str, Any] = {}
        if not _lazy_init:
            self._init_components()

    def _init_components(self) -> None:
        if self.config.index.provider != "sqlite":
            raise ValueError(
                f"Unsupported index provider '{self.config.index.provider}'. Supported: sqlite."
            )
        self._store = SQLiteStore(
            self.config.index.db_path,
            extracted_dir=self.config.index.extracted_dir or None,
        )

    @property
    def store(self) -> SQLiteStore:
        if self._store is None:
            self._init_components()
        assert self._store is not None
        return self._store

    def _get_loader(self, suffix: str):
        parser_path = _PARSERS.get(suffix)
        if not parser_path:
            raise ValueError(f"No parser for '{suffix}'. Supported: {list(_PARSERS.keys())}")
        cls = _import_class(parser_path)
        return cls()

    def ingest_documents(
        self,
        documents: list[Document],
        recreate: bool = False,
        *,
        with_vectors: bool = True,
    ) -> int:
        logger.info("Indexing %d document(s) with SQLite FTS5", len(documents))
        result = self.store.add_documents(documents, recreate=recreate)
        logger.info("Stored %d source(s), %d section(s)", result.sources, result.sections)
        if with_vectors:
            try:
                self._sync_vectors_if_enabled()
            except Exception as exc:
                raise RuntimeError(f"vector indexing failed after FTS5 ingest: {exc}") from exc
        return result.sections

    def ingest_records(
        self,
        records,
        *,
        recreate: bool = False,
        batch_size: int = 1000,
        with_vectors: bool = True,
        progress_callback=None,
    ) -> int:
        """Stream-ingest an iterable of ``Document`` records.

        Designed for atomic-record sources (USPTO case files, court filings)
        where the iterator would yield millions of records. The iterable is
        consumed lazily and committed every ``batch_size`` rows.
        """
        result = self.store.add_documents_stream(
            records,
            recreate=recreate,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )
        logger.info(
            "Stream-ingested %d source(s), %d section(s)",
            result.sources,
            result.sections,
        )
        if with_vectors:
            try:
                self._sync_vectors_if_enabled()
            except Exception as exc:
                raise RuntimeError(f"vector indexing failed after FTS5 ingest: {exc}") from exc
        return result.sections

    def _vector_collection_name(self) -> str:
        explicit = self.config.vector_store.collection
        if explicit:
            return explicit
        slug = Path(self.config.index.db_path).stem or "docmancer"
        return f"docmancer_{slug}"

    def _sync_vectors_if_enabled(self) -> None:
        """Embed any new chunks and upsert into the configured vector store.

        Vector retrieval is on by default. Bare ``doc-atlas ingest`` will
        download the pinned Qdrant binary on first run, start it in the
        background with telemetry disabled, embed every section with the
        configured provider (default FastEmbed: local, no API key), and
        upsert into Qdrant.

        Opt-outs (each used by tests and FTS5-only installs):

        - ``DOCMANCER_AUTO_VECTORS=0`` skips the vector path entirely.
        - ``DOCMANCER_QDRANT_URL`` short-circuits the managed lifecycle.
        - Missing cloud-embedding API key for the configured provider:
          logs a warning and falls back to FTS5-only ingest (no vectors).
        - ``[vector]`` extras stripped from the venv: silent no-op.
        """
        import os as _os

        if _os.environ.get("DOCMANCER_AUTO_VECTORS") == "0":
            logger.debug("vector sync disabled by DOCMANCER_AUTO_VECTORS=0")
            return

        try:
            from docmancer.embeddings import get_embeddings_provider
            from docmancer.embeddings.pipeline import sync_vector_store
            from docmancer.runtime.qdrant_manager import QdrantManager, ensure_running
            from docmancer.stores.base import get_vector_store
        except ImportError as exc:
            logger.info("vector indexing disabled: %s", exc)
            return

        # Graceful fallback: cloud embedding providers need an API key. When
        # the configured provider has no key in env, log once and skip the
        # vector path so FTS5 ingest still succeeds.
        emb_provider = (self.config.embeddings.provider or "").lower()
        _provider_keys = {
            "openai": "OPENAI_API_KEY",
            "voyage": "VOYAGE_API_KEY",
            "cohere": "COHERE_API_KEY",
        }
        required_key = _provider_keys.get(emb_provider)
        if required_key and not _os.environ.get(required_key):
            logger.warning(
                "embeddings.provider=%r requires %s; falling back to FTS5-only ingest "
                "(set the env var, or switch to embeddings.provider=fastembed for local "
                "embeddings with no API key).",
                emb_provider,
                required_key,
            )
            return

        vs_config = self.config.vector_store
        if vs_config.provider == "qdrant" and not vs_config.url:
            resolution = ensure_running()
            if resolution.fallback or not resolution.url:
                logger.info(
                    "managed qdrant unavailable (%s); falling back to sqlite-vec",
                    resolution.reason,
                )
                vs_config = vs_config.model_copy(update={"provider": "sqlite-vec"})
            else:
                vs_config = vs_config.model_copy(update={"url": resolution.url})

        try:
            vector_store = get_vector_store(vs_config, embeddings_dim=self.config.embeddings.dimensions)
        except ImportError as exc:
            logger.info("vector indexing disabled (missing extra): %s", exc)
            return

        provider = get_embeddings_provider(self.config.embeddings)
        include_sparse = self.config.retrieval.default_mode in {"sparse", "hybrid"}
        result = sync_vector_store(
            store=self.store,
            config=self.config,
            provider=provider,
            vector_store=vector_store,
            collection=self._vector_collection_name(),
            include_sparse=include_sparse,
        )
        logger.info(
            "vectors: embedded=%d upserted=%d cache_hits=%d unchanged=%d pruned=%d",
            result.embedded,
            result.upserted,
            result.skipped_cache,
            result.skipped_unchanged,
            result.pruned,
        )

    def sync_vectors(self) -> None:
        """Synchronize the committed SQLite index into its production vector collection."""
        self._sync_vectors_if_enabled()

    def ingest(
        self,
        path: str | Path,
        recreate: bool = False,
        *,
        include: tuple[str, ...] = (),
        include_exact: tuple[str, ...] = (),
        extensionless_text_names: tuple[str, ...] = (),
        exclude: tuple[str, ...] = (),
        formats: tuple[str, ...] = (),
        recursive: bool = True,
        skip_known: bool = False,
        with_vectors: bool = True,
        metadata: dict[str, Any] | None = None,
        metadata_for_file: Callable[[Path], dict[str, Any]] | None = None,
    ) -> int:
        path = Path(path)
        extensionless_text_names_lower = {name.lower() for name in extensionless_text_names}
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if path.is_file():
            files = [path]
        else:
            supported = set(_PARSERS.keys())
            selected_formats = {fmt if fmt.startswith(".") else f".{fmt}" for fmt in formats}
            allowed = supported & {fmt.lower() for fmt in selected_formats} if selected_formats else supported
            extensionless_text_allowed = not selected_formats or ".txt" in allowed

            def _allowed_file(candidate: Path) -> bool:
                suffix = candidate.suffix.lower()
                if suffix in allowed:
                    return True
                return (
                    not suffix
                    and extensionless_text_allowed
                    and candidate.name.lower() in extensionless_text_names_lower
                )

            if include_exact:
                root = path.resolve()
                selected_files: list[Path] = []
                seen: set[Path] = set()
                for relative in include_exact:
                    exact_path = Path(relative)
                    candidate = exact_path if exact_path.is_absolute() else path / exact_path
                    try:
                        resolved = candidate.resolve()
                        resolved.relative_to(root)
                    except (OSError, ValueError):
                        continue
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    if candidate.is_file() and _allowed_file(candidate):
                        selected_files.append(candidate)
                files = selected_files
            else:
                iterator = path.rglob("*") if recursive else path.glob("*")
                files = sorted(f for f in iterator if f.is_file() and _allowed_file(f))
                if include:
                    files = [f for f in files if self._matches_any(f.relative_to(path), include)]
            if exclude:
                files = [f for f in files if not self._matches_any(f.relative_to(path), exclude)]
        if not files:
            raise ValueError("No supported documents found.")
        documents = []
        skipped: list[dict[str, str]] = []
        for file_path in files:
            try:
                extensionless_as_text = (
                    not file_path.suffix
                    and file_path.name.lower() in extensionless_text_names_lower
                )
                loader = self._get_loader(".txt" if extensionless_as_text else file_path.suffix.lower())
                document = loader.load(file_path)
                suffix = "txt" if extensionless_as_text else file_path.suffix.lower().lstrip(".")
                format_name = "markdown" if suffix in {"md", "markdown"} else suffix
                document.metadata.setdefault("format", format_name)
                document.metadata.setdefault("chunking_strategy", getattr(loader, "chunking_strategy", "heading"))
                chunk_size, chunk_overlap = self.config.loaders.settings_for(format_name)
                document.metadata.setdefault("chunk_size", chunk_size)
                document.metadata.setdefault("chunk_overlap", chunk_overlap)
                document.metadata.setdefault("docset_root", str(path if path.is_dir() else file_path))
                if path.is_dir():
                    document.metadata.setdefault("source_path", str(file_path.relative_to(path)))
                else:
                    document.metadata.setdefault("source_path", file_path.name)
                document.metadata.setdefault("title", file_path.stem)
                document.metadata.setdefault(
                    "content_hash",
                    hashlib.sha256(document.content.encode("utf-8")).hexdigest(),
                )
                if metadata:
                    document.metadata.update(metadata)
                if metadata_for_file:
                    document.metadata.update(metadata_for_file(file_path))
                content_hash = str(document.metadata.get("content_hash") or "")
                existing_metadata = self.store.source_metadata(document.source) if skip_known and content_hash else None
                if (
                    existing_metadata is not None
                    and existing_metadata.get("content_hash") == content_hash
                    and self._metadata_satisfies_skip_known(existing_metadata, document.metadata)
                ):
                    skipped.append(
                        {
                            "path": str(file_path),
                            "reason": "unchanged content hash",
                            "exception_type": "SkippedKnownFile",
                        }
                    )
                    continue
                documents.append(document)
            except Exception as exc:
                skipped.append(
                    {
                        "path": str(file_path),
                        "reason": str(exc),
                        "exception_type": type(exc).__name__,
                    }
                )
                logger.warning("Skipping %s: %s: %s", file_path, type(exc).__name__, exc)
        self._write_last_ingest_report(path, skipped)
        if not documents:
            raise ValueError(f"No documents could be loaded. See {self.last_ingest_report_path}")
        return self.ingest_documents(documents, recreate=recreate, with_vectors=with_vectors)

    @staticmethod
    def _matches_any(relative_path: Path, patterns: tuple[str, ...]) -> bool:
        value = relative_path.as_posix()
        return any(fnmatch.fnmatch(value, pattern) or relative_path.match(pattern) for pattern in patterns)

    @staticmethod
    def _metadata_satisfies_skip_known(existing_metadata: dict[str, Any], expected_metadata: dict[str, Any]) -> bool:
        return all(existing_metadata.get(key) == value for key, value in expected_metadata.items())

    def _write_last_ingest_report(self, root: Path, skipped: list[dict[str, str]]) -> None:
        home = Path(os.environ.get("DOCMANCER_HOME") or Path(self.config.index.db_path).expanduser().parent)
        home.mkdir(parents=True, exist_ok=True)
        report_path = home / "last-ingest-report.json"
        spill_path = home / "last-ingest-report.skipped.jsonl"
        max_inline = 10_000
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "root": str(root),
            "skipped_count": len(skipped),
            "skipped": skipped[:max_inline],
            "spillover_path": str(spill_path) if len(skipped) > max_inline else None,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if len(skipped) > max_inline:
            spill_path.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in skipped[max_inline:]) + "\n",
                encoding="utf-8",
            )
        elif spill_path.exists():
            spill_path.unlink()
        self.last_ingest_report_path = report_path
        self.last_ingest_skips = skipped

    def add(self, path_or_url: str, recreate: bool = False, **kwargs) -> int:
        if path_or_url.startswith(("http://", "https://")):
            return self.ingest_url(path_or_url, recreate=recreate, **kwargs)
        return self.ingest(path_or_url, recreate=recreate)

    def _get_fetcher(
        self,
        provider: str | None,
        fetcher=None,
        max_pages: int = 500,
        strategy: str | None = None,
        browser: bool = False,
        url: str | None = None,
        doc_format: str | None = None,
        seed_urls: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        path_prefixes: list[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        cancellation_callback: Callable[[], bool] | None = None,
    ):
        if fetcher is not None:
            return fetcher
        from docmancer.connectors.fetchers.factory import build_fetcher

        if provider is None and url:
            provider = self._auto_detect_provider(url)

        return build_fetcher(
            url or "",
            provider=provider,
            timeout=getattr(self.config.web_fetch, "read_timeout_seconds", 30.0),
            max_pages=max_pages,
            strategy=strategy,
            browser=browser,
            workers=self.config.web_fetch.workers,
            doc_format=doc_format,
            seed_urls=seed_urls,
            allowed_domains=allowed_domains,
            path_prefixes=path_prefixes,
            max_redirects=getattr(self.config.web_fetch, "max_redirects", 5),
            connect_timeout=self.config.web_fetch.connect_timeout_seconds,
            max_total_seconds=self.config.web_fetch.max_total_seconds,
            use_env_proxy=getattr(self.config.web_fetch, "use_env_proxy", False),
            proxy_url=getattr(self.config.web_fetch, "proxy_url", None),
            max_response_bytes=getattr(self.config.web_fetch, "max_response_bytes", 8 * 1024 * 1024),
            max_decoded_text_bytes=getattr(
                self.config.web_fetch, "max_decoded_text_bytes", 16 * 1024 * 1024
            ),
            progress_callback=progress_callback,
            cancellation_callback=cancellation_callback,
        )

    def _auto_detect_provider(self, url: str) -> str:
        logger.info("Using secure web fetcher; platform detection happens inside its network boundary")
        return "web"

    def ingest_url(
        self,
        url: str,
        recreate: bool = False,
        fetcher=None,
        provider: str | None = None,
        max_pages: int = 500,
        strategy: str | None = None,
        browser: bool = False,
        doc_format: str | None = None,
        seed_urls: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        path_prefixes: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        cancellation_callback: Callable[[], bool] | None = None,
        with_vectors: bool = True,
    ) -> int:
        f = self._get_fetcher(
            provider,
            fetcher,
            max_pages=max_pages,
            strategy=strategy,
            browser=browser,
            url=url,
            doc_format=doc_format,
            seed_urls=seed_urls,
            allowed_domains=allowed_domains,
            path_prefixes=path_prefixes,
            progress_callback=progress_callback,
            cancellation_callback=cancellation_callback,
        )
        documents = f.fetch(url)
        self.last_fetch_failure = getattr(f, "last_fetch_failure", None)
        if cancellation_callback and cancellation_callback():
            raise RuntimeError("Documentation ingestion cancelled before indexing.")
        section_counts = {document.source: document_section_count(document) for document in documents}
        ledger = list(getattr(f, "last_page_ledger", []) or [])
        for page in ledger:
            if page.get("outcome") != "usable":
                continue
            page["chunks"] = int(
                section_counts.get(str(page.get("canonical_url")))
                or section_counts.get(str(page.get("discovered_url")))
                or 0
            )
        diagnostics = dict(getattr(f, "last_discovery_diagnostics", {}) or {})
        if ledger:
            diagnostics["page_ledger"] = ledger
        self.last_discovery_diagnostics = diagnostics
        if metadata:
            for document in documents:
                source_metadata = dict(document.metadata or {})
                document.metadata.update(metadata)
                for key in SOURCE_DERIVED_METADATA_KEYS:
                    if key in source_metadata:
                        document.metadata[key] = source_metadata[key]
        logger.info("Fetched %d document(s); starting index", len(documents))
        if progress_callback:
            progress_callback(
                {
                    "phase": "indexing",
                    "message": f"Indexing {len(documents)} documents",
                    "indexed_pages": 0,
                    "total_pages": len(documents),
                }
            )
        indexed = self.ingest_documents(documents, recreate=recreate, with_vectors=with_vectors)
        if progress_callback:
            progress_callback(
                {
                    "phase": "indexing",
                    "message": f"Indexed {indexed} documents",
                    "indexed_pages": indexed,
                    "total_pages": len(documents),
                }
            )
        return indexed

    def fetch_documents(
        self,
        url: str,
        fetcher=None,
        provider: str | None = None,
        max_pages: int = 500,
        strategy: str | None = None,
        browser: bool = False,
        doc_format: str | None = None,
        seed_urls: list[str] | None = None,
        allowed_domains: list[str] | None = None,
        path_prefixes: list[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[Document]:
        f = self._get_fetcher(
            provider,
            fetcher,
            max_pages=max_pages,
            strategy=strategy,
            browser=browser,
            url=url,
            doc_format=doc_format,
            seed_urls=seed_urls,
            allowed_domains=allowed_domains,
            path_prefixes=path_prefixes,
            progress_callback=progress_callback,
        )
        return f.fetch(url)

    def query(
        self,
        text: str,
        limit: int | None = None,
        budget: int | None = None,
        expand: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        return self.store.query(
            text,
            limit=limit or self.config.query.default_limit,
            budget=budget or self.config.query.default_budget,
            expand=expand if expand is not None else self.config.query.default_expand,
            filters=filters,
        )

    def query_context(
        self,
        text: str,
        *,
        style: str = "markdown",
        include_sources: bool = True,
        limit: int | None = None,
        budget: int | None = None,
        expand: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Query the index and return a formatted context string.

        Combines :meth:`query` and :func:`~docmancer.context.format_context`
        into a single call for convenience.
        """
        chunks = self.query(text, limit=limit, budget=budget, expand=expand, filters=filters)
        from docmancer.context import format_context

        return format_context(chunks, style=style, include_sources=include_sources)

    def collection_stats(self) -> dict:
        return self.store.collection_stats()

    def get_collection_info(self) -> dict:
        return self.store.collection_stats()

    def list_sources(self) -> list[str]:
        return self.store.list_sources()

    def get_document(self, source: str) -> str | None:
        return self.store.get_document_content(source)

    def remove_source(self, source: str) -> tuple[bool, str]:
        if self.store.delete_docset(source):
            return True, "docset"
        if self.store.delete_source(source):
            return True, "source"
        return False, "missing"

    def remove_all_sources(self) -> bool:
        return self.store.delete_all()

    def list_sources_with_dates(self) -> list[dict]:
        return self.store.list_sources_with_dates()

    def list_grouped_sources_with_dates(self) -> list[dict]:
        return self.store.list_grouped_sources_with_dates()
