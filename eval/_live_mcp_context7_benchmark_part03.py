"""Live benchmark implementation shard."""
from __future__ import annotations
from eval._live_mcp_context7_benchmark_shared import *  # noqa: F401,F403
from eval._live_mcp_context7_benchmark_part01 import BenchmarkProvider, NormalizedBenchmarkResult, Snippet, SourceRef

class Context7MCPProvider(BenchmarkProvider):
    def __init__(self):
        self.name = "context7"
        self.provider_id = "context7_zero_setup"
        self.provider_mode = "live_mcp_stdio"
        self.benchmark_mode = "zero-setup"
        self._session: Any = None
        self._lib_cache: dict[str, str] = {}
        self._stdio_ctx: Any = None
        self._session_ctx: Any = None
        self._read: Any = None
        self._write: Any = None

    async def _ensure_session(self) -> Any:
        if self._session is None:
            # The provider-backed benchmark is optional.  Keep the MCP SDK
            # import on the live execution path so provider-free metrics and
            # regression tests remain importable from a minimal sdist.
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

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


def _evaluate_primary_snippet(primary: dict[str, Any], case: BenchmarkCase, *, response_style_observed: str | None) -> dict[str, Any]:
    code = str(primary.get("code") or "") if isinstance(primary, dict) else ""
    language = str(primary.get("language") or "").lower() if isinstance(primary, dict) else ""
    source = str(primary.get("source") or primary.get("source_url") or "") if isinstance(primary, dict) else ""
    source_lower = source.lower()
    symbol_match = True if not case.expected_symbols else any(symbol.lower() in code.lower() for symbol in case.expected_symbols)
    language_match = True if not case.expected_languages else language in {item.lower() for item in case.expected_languages}
    source_correct = True
    if case.expected_domains:
        try:
            domain = urlparse(source).netloc.lower()
        except Exception:
            domain = ""
        source_correct = any(domain == expected.lower() or domain.endswith("." + expected.lower()) for expected in case.expected_domains)
    elif case.expected_source_patterns:
        source_correct = any(pattern.lower() in source_lower for pattern in case.expected_source_patterns)
    scope_correct = True
    if case.expected_doc_scope:
        scope_correct = primary.get("doc_scope") == case.expected_doc_scope
    exact_ok = True
    if case.id == "anyhow_context_snippet":
        exact_ok = primary.get("version") == "1.0.86" or primary.get("requested_version") == "1.0.86"
    present = bool(code.strip())
    snippet_first = response_style_observed == "snippet-first"
    truncated = bool(primary.get("truncated"))
    noisy = _snippet_noise(code)
    reason_codes = []
    for ok, code_name in (
        (present, "snippet_missing"),
        (snippet_first, "snippet_first_not_applied"),
        (symbol_match, "snippet_symbol_missing"),
        (language_match, "snippet_language_mismatch"),
        (source_correct, "snippet_source_mismatch"),
        (scope_correct, "snippet_scope_mismatch"),
        (exact_ok, "snippet_exact_version_mismatch"),
    ):
        if not ok:
            reason_codes.append(code_name)
    if noisy:
        reason_codes.append("snippet_noise")
    return {
        "success": present and snippet_first and symbol_match and language_match and source_correct and scope_correct and exact_ok and not noisy,
        "reason_code": reason_codes[0] if reason_codes else None,
        "reason_codes": reason_codes or ["snippet_success"],
        "snippet_present_at_1": present,
        "primary_snippet_symbol_match": symbol_match,
        "primary_snippet_language_match": language_match,
        "primary_snippet_source_correct": source_correct,
        "primary_snippet_exact_version_match": exact_ok,
        "snippet_first_applied": snippet_first,
        "snippet_noise": noisy,
        "snippet_truncated": truncated,
        "primary_language": language or None,
        "primary_source": source or None,
    }


def _snippet_noise(code: str) -> bool:
    stripped = (code or "").strip().lower()
    if not stripped:
        return True
    return stripped in {"copy", "download", "open in new tab"}


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

    ev_cases = [r for r in applicable if r.suite == "exact-version"]
    ev_total = len(ev_cases)
    ev_success = sum(1 for r in ev_cases if r.is_success())
    ev_empty = sum(1 for r in ev_cases if r.is_empty())
    ev_not_supported = sum(1 for r in ev_cases if r.status == "not_supported")
    ev_match = sum(1 for r in ev_cases if r.exact_version_match is True)
    ev_fallback = sum(1 for r in ev_cases if r.exact_version_fallback is True)
    ev_indexed = sum(1 for r in ev_cases if r.exact_version_status == "exact_version_indexed")
    dedup_drops = sum(r.deduplication_dropped_count for r in applicable)

    # Exact-version correctness: only count true exact matches
    ev_correct = sum(1 for r in ev_cases if r.is_success() and r.exact_version_match is True and r.expected_source_hits)
    snippet_cases = [r for r in applicable if r.suite == "snippet-first"]
    snippet_evals = [r.snippet_eval or {} for r in snippet_cases]

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
        "exact_version_total_count": ev_total,
        "exact_version_success_count": ev_success,
        "exact_version_empty_count": ev_empty,
        "exact_version_not_supported_count": ev_not_supported,
        "exact_version_match_count": ev_match,
        "exact_version_fallback_count": ev_fallback,
        "exact_version_indexed_count": ev_indexed,
        "exact_version_coverage_rate": round(ev_success / max(ev_total, 1), 4) if ev_total > 0 else 0.0,
        "exact_version_match_rate": round(ev_match / max(ev_total, 1), 4) if ev_total > 0 else 0.0,
        "exact_version_not_supported_rate": round(ev_not_supported / max(ev_total, 1), 4) if ev_total > 0 else 0.0,
        "exact_version_fallback_rate": round(ev_fallback / max(ev_total, 1), 4) if ev_total > 0 else 0.0,
        "exact_version_correctness_on_success": round(ev_correct / max(ev_success, 1), 4) if ev_success > 0 else None,
        "deduplication_drop_rate": round(dedup_drops / max(n_app, 1), 4),
        "deduplication_dropped_count": dedup_drops,
        "snippet_present_at_1": round(sum(1 for e in snippet_evals if e.get("snippet_present_at_1")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
        "primary_snippet_source_correct": round(sum(1 for e in snippet_evals if e.get("primary_snippet_source_correct")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
        "primary_snippet_language_match": round(sum(1 for e in snippet_evals if e.get("primary_snippet_language_match")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
        "primary_snippet_symbol_match": round(sum(1 for e in snippet_evals if e.get("primary_snippet_symbol_match")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
        "snippet_noise_rate": round(sum(1 for e in snippet_evals if e.get("snippet_noise")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
        "snippet_truncation_rate": round(sum(1 for e in snippet_evals if e.get("snippet_truncated")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
        "snippet_first_application_rate": round(sum(1 for e in snippet_evals if e.get("snippet_first_applied")) / max(len(snippet_evals), 1), 4) if snippet_cases else None,
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
        if suite == "unified-context":
            applicable = [r for r in rlist if not r.is_not_applicable()]
            routing_ok = [r for r in applicable if {"project", "library", "mixed", "dependency"}.intersection(r.reason_codes)]
            project_primary = [r for r in applicable if r.case_id in {"unified_project_auto", "unified_mixed_partial_confirmation"}]
            pm["routing_accuracy"] = round(len(routing_ok) / len(applicable), 4) if applicable else None
            pm["source_scope_correctness"] = pm.get("correct_source_rate_on_success")
            pm["project_primary_rate"] = round(sum(1 for r in project_primary if r.sources and r.sources[0].doc_scope == "project") / len(project_primary), 4) if project_primary else None
            confirmation_codes = {"confirmation_required", "library_docs_network_fetch_required", "dependency_docs_prefetch_required", "dependency_docs_prefetch_confirmation_required", "latest_fallback_network_fetch_required"}
            pm["confirmation_contract_correctness"] = round(sum(1 for r in applicable if not (r.status == "needs_refresh" and not confirmation_codes.intersection(r.reason_codes))) / len(applicable), 4) if applicable else None
            fallback_cases = [r for r in applicable if r.case_id == "unified_latest_fallback"]
            pm["fallback_execution_rate"] = round(sum(1 for r in fallback_cases if r.exact_version_fallback and r.sources) / len(fallback_cases), 4) if fallback_cases else None
        m[pid] = pm
    return m


def _metric_line(label: str, da_val: Any, c7_val: Any) -> str:
    return f"| {label} | {_mv(da_val)} | {_mv(c7_val)} |"


def _mv(v: Any) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)

__all__=['Context7MCPProvider', '_evaluate_primary_snippet', '_snippet_noise', '_detect_contamination', '_detect_forbidden_sources', '_detect_expected_sources', '_extract_sources_and_snippets', 'compute_metrics', 'compute_suite_metrics', '_metric_line', '_mv']
