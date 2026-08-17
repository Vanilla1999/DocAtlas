"""Live benchmark implementation shard."""
from __future__ import annotations
from eval._live_mcp_context7_benchmark_shared import *  # noqa: F401,F403

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
class DependencyFixtureDiagnostics:
    project_path: str | None = None
    manifest: str | None = None
    lockfile: str | None = None
    dependency: str = "anyhow"
    ecosystem: str | None = None
    requested_version: str = "1.0.86"
    locked_version: str | None = None
    exact: bool = False
    valid: bool = False
    reason_code: str | None = None
    warnings: list[str] = field(default_factory=list)


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
    # Exact-version fields
    exact_version_expected: str | None = None
    exact_version_match: bool | None = None
    exact_version_status: str | None = None
    exact_version_fallback: bool = False
    exact_version_reason_code: str | None = None
    deduplication_dropped_count: int = 0
    dependency_fixture: DependencyFixtureDiagnostics | None = None
    dependency_preparation: dict[str, Any] | None = None
    project_preparation: dict[str, Any] | None = None
    routing_observed: dict[str, Any] | None = None
    snippet_eval: dict[str, Any] | None = None

    def is_not_applicable(self) -> bool:
        return self.status in ("not_applicable",)

    def is_error(self) -> bool:
        return self.status in ("error", "timeout", "failed_ingest", "preindex_failed")

    def is_empty(self) -> bool:
        return self.status in ("empty_index", "needs_refresh", "no_results", "quota_exceeded")

    def is_success(self) -> bool:
        return self.status == "success"


def _all_cases() -> list[BenchmarkCase]:
    return PUBLIC_DOCS_CASES + PROJECT_DOCS_CASES + EXACT_VERSION_CASES + UNIFIED_CONTEXT_CASES + SNIPPET_FIRST_CASES


def _filter_cases(suites: list[str] | None, quick: bool) -> list[BenchmarkCase]:
    all_c = _all_cases()
    if suites:
        all_c = [c for c in all_c if c.suite in suites]
    if quick:
        quick_set = set(QUICK_CASES)
        return [c for c in all_c if c.id in quick_set]
    return all_c


class BenchmarkProvider:
    name: str
    provider_id: str
    provider_mode: str
    benchmark_mode: str

    async def setup(self) -> None:
        pass

    async def query(self, case: BenchmarkCase) -> NormalizedBenchmarkResult:
        raise NotImplementedError

__all__=['SourceRef', 'Snippet', 'PreindexDiagnostics', 'DependencyFixtureDiagnostics', 'NormalizedBenchmarkResult', '_all_cases', '_filter_cases', 'BenchmarkProvider']
