from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from docmancer.core.product_identity import docatlas_home


def default_user_db_path() -> str:
    root = docatlas_home()
    return str(root / "docmancer.db")


class IndexConfig(BaseSettings):
    provider: str = "sqlite"
    db_path: str = Field(default_factory=default_user_db_path)
    extracted_dir: str = ""
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_INDEX_", extra="ignore")


class QueryConfig(BaseSettings):
    default_budget: int = Field(default=2400, ge=100)
    default_limit: int = Field(default=8, ge=1)
    default_expand: str = "adjacent"
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_QUERY_", extra="ignore")


class WebFetchConfig(BaseSettings):
    workers: int = Field(default=8, ge=1)
    default_page_cap: int = Field(default=500, ge=1)
    library_job_timeout_seconds: float = Field(default=120.0, gt=0)
    browser_fallback: bool = False
    max_redirects: int = Field(default=5, ge=0)
    connect_timeout_seconds: float = Field(default=10.0, gt=0)
    read_timeout_seconds: float = Field(default=30.0, gt=0)
    max_total_seconds: float = Field(default=120.0, gt=0)
    max_response_bytes: int = Field(default=8 * 1024 * 1024, ge=1)
    max_decoded_text_bytes: int = Field(default=16 * 1024 * 1024, ge=1)
    use_env_proxy: bool = False
    proxy_url: str | None = None
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_WEB_FETCH_", extra="ignore")


class DocsJobsConfig(BaseSettings):
    max_terminal_jobs: int = Field(default=1000, ge=1)
    retention_days: int = Field(default=30, ge=1)
    max_events: int = Field(default=50, ge=1)
    library_max_running: int = Field(default=2, ge=1)
    library_max_queued: int = Field(default=8, ge=0)
    terminalization_grace_seconds: float = Field(default=2.0, gt=0, le=2.0)
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_DOCS_JOBS_", extra="ignore")


class ProjectSourceBoundaryConfig(BaseModel):
    source_roots: list[str] = Field(default_factory=list)
    documentation_roots: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    generated_paths: list[str] = Field(default_factory=list)
    include_extensions: list[str] = Field(default_factory=list)
    respect_gitignore: bool = True
    max_scanned_files: int = Field(default=5000, ge=1)
    max_scanned_bytes: int = Field(default=32 * 1024 * 1024, ge=1)
    max_file_bytes: int = Field(default=256_000, ge=1)
    scan_deadline_seconds: float = Field(default=5.0, gt=0)
    max_directory_depth: int = Field(default=20, ge=1)


class ProjectConfig(ProjectSourceBoundaryConfig):
    def source_boundary(self) -> ProjectSourceBoundaryConfig:
        return ProjectSourceBoundaryConfig.model_validate(self.model_dump())


class LoaderFormatConfig(BaseModel):
    chunk_size: int | None = Field(default=None, ge=100)
    chunk_overlap: int | None = Field(default=None, ge=0)


class LoadersConfig(BaseModel):
    default_chunk_size: int = Field(default=800, ge=100)
    default_chunk_overlap: int = Field(default=100, ge=0)
    formats: dict[str, LoaderFormatConfig] = Field(default_factory=dict)

    def settings_for(self, format_name: str) -> tuple[int, int]:
        override = self.formats.get(format_name.lower())
        chunk_size = override.chunk_size if override and override.chunk_size is not None else self.default_chunk_size
        chunk_overlap = (
            override.chunk_overlap
            if override and override.chunk_overlap is not None
            else self.default_chunk_overlap
        )
        if chunk_overlap >= chunk_size:
            raise ValueError("loader chunk_overlap must be smaller than chunk_size")
        return chunk_size, chunk_overlap


class VectorStoreConfig(BaseSettings):
    provider: str = "qdrant"
    url: str | None = None
    api_key_env: str | None = None
    collection: str | None = None
    options: dict = Field(default_factory=dict)
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_VECTOR_STORE_", extra="forbid")


class EmbeddingsConfig(BaseSettings):
    provider: str = "fastembed"
    model: str = "BAAI/bge-base-en-v1.5"
    dimensions: int = 768
    sparse_model: str | None = None
    cache: str = Field(default_factory=lambda: str(
        docatlas_home() / "embeddings-cache"
    ))
    batch_size: int = 64
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_EMBEDDINGS_", extra="ignore")


class FusionConfig(BaseModel):
    method: str = "rrf"
    rrf_k: int = 60
    weights: dict[str, float] = Field(default_factory=dict)


class HierarchicalConfig(BaseModel):
    """Two-stage hierarchical retrieval: pick top documents, then top sections inside them.

    By default the dispatcher decides per-index: ``auto=True`` turns the
    two-stage pass on when the index contains at least
    ``auto_min_documents`` distinct ``document_title_hash`` values, and
    leaves it off on smaller / flatter corpora where the extra round-trip
    just costs latency. Set ``enabled=True`` to force it on regardless of
    corpus size; set ``auto=False`` to force it off unless ``enabled``
    is also true.
    """

    enabled: bool = False
    auto: bool = True
    auto_min_documents: int = Field(default=10, ge=1)
    documents_limit: int = Field(default=5, ge=1)
    candidate_pool: int = Field(default=200, ge=10)
    sections_per_document: int = Field(default=10, ge=1)


class QueryRouter(BaseModel):
    """A regex-matched query router.

    When ``match`` matches the query (case-insensitive), the router's
    ``filters`` are merged into the dispatcher filters for that call.
    The first matching router wins; routers do not stack.
    """

    match: str
    filters: dict = Field(default_factory=dict)
    description: str | None = None


class RetrievalConfig(BaseSettings):
    default_mode: str = "lexical"
    fusion: FusionConfig = Field(default_factory=FusionConfig)
    hierarchical: HierarchicalConfig = Field(default_factory=HierarchicalConfig)
    routers: list[QueryRouter] = Field(default_factory=list)
    expand: str | None = None
    budget: int | None = None
    limit: int | None = None
    max_sections_per_source: int | None = Field(default=2, ge=1)
    model_config = SettingsConfigDict(env_prefix="DOCATLAS_RETRIEVAL_", extra="ignore")


class DocmancerConfig(BaseModel):
    index: IndexConfig = Field(default_factory=IndexConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)
    web_fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)
    docs_jobs: DocsJobsConfig = Field(default_factory=DocsJobsConfig)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    loaders: LoadersConfig = Field(default_factory=LoadersConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    model_config = {"extra": "forbid"}

    @classmethod
    def from_yaml(cls, path: Path | str) -> DocmancerConfig:
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        config = cls(**data)
        db_path = Path(config.index.db_path)
        if not db_path.is_absolute():
            config.index.db_path = str((path.parent / db_path).resolve())

        extracted_dir = config.index.extracted_dir
        if extracted_dir:
            extracted_path = Path(extracted_dir)
            if not extracted_path.is_absolute():
                config.index.extracted_dir = str((path.parent / extracted_path).resolve())

        return config

    @classmethod
    def from_env(cls) -> DocmancerConfig:
        return cls()
