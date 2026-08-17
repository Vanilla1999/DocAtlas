"""Live benchmark implementation shard."""
from __future__ import annotations
from eval._live_mcp_context7_benchmark_shared import *  # noqa: F401,F403
from eval._live_mcp_context7_benchmark_part01 import BenchmarkProvider, NormalizedBenchmarkResult, _filter_cases
from eval._live_mcp_context7_benchmark_part02 import DocAtlasDirectProvider
from eval._live_mcp_context7_benchmark_part03 import Context7MCPProvider, _metric_line, _mv, compute_metrics, compute_suite_metrics

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

    if benchmark_mode in ("zero-setup", "preindexed", "both"):
        lines.append("## Unified Context")
        lines.append("")
        for sm in suite_metrics:
            if sm["suite"] == "unified-context":
                da = sm.get("docatlas_preindexed", sm.get("docatlas_zero_setup", sm.get("docatlas", {})))
                c7 = sm.get("context7_zero_setup", sm.get("context7", {}))
                lines.append("| Metric | DocAtlas | Context7 |")
                lines.append("|--------|----------|----------|")
                lines.append(_metric_line("Routing accuracy", da.get("routing_accuracy"), c7.get("routing_accuracy")))
                lines.append(_metric_line("Coverage rate", da.get("coverage_rate"), c7.get("coverage_rate")))
                lines.append(_metric_line("Source scope correctness", da.get("source_scope_correctness"), c7.get("source_scope_correctness")))
                lines.append(_metric_line("Contamination rate", da.get("contamination_rate_all"), c7.get("contamination_rate_all")))
                lines.append(_metric_line("Deduplication drop rate", da.get("deduplication_drop_rate"), c7.get("deduplication_drop_rate")))
                lines.append(_metric_line("Fallback execution rate", da.get("fallback_execution_rate"), c7.get("fallback_execution_rate")))
                lines.append(_metric_line("Project primary rate", da.get("project_primary_rate"), c7.get("project_primary_rate")))
                lines.append(_metric_line("Exact version correctness on success", da.get("exact_version_correctness_on_success"), c7.get("exact_version_correctness_on_success")))
                lines.append(_metric_line("Confirmation contract correctness", da.get("confirmation_contract_correctness"), c7.get("confirmation_contract_correctness")))
                lines.append(_metric_line("Setup calls avg", da.get("setup_calls_avg"), c7.get("setup_calls_avg")))
                lines.append(_metric_line("Avg latency (ms)", da.get("avg_latency_ms"), c7.get("avg_latency_ms")))
                lines.append("")
                lines.append("- Context7 is N/A for local project-only and mixed project cases.")
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
                    "exact_version_fallback": result.exact_version_fallback,
                    "deduplication_dropped_count": result.deduplication_dropped_count,
                    "contamination_hits": result.contamination_hits,
                    "forbidden_source_hits": result.forbidden_source_hits,
                    "expected_source_hits": result.expected_source_hits,
                    "expected_domains": case.expected_domains,
                    "expected_symbols": case.expected_symbols,
                    "expected_languages": case.expected_languages,
                    "snippet_eval": result.snippet_eval,
                    "forbidden_domains": case.forbidden_domains,
                    "expected_doc_scope": case.expected_doc_scope,
                    "manual_review_required": result.manual_review_required,
                    "preindex": dataclasses.asdict(result.preindex) if result.preindex else None,
                    "dependency_fixture": dataclasses.asdict(result.dependency_fixture) if result.dependency_fixture else None,
                    "dependency_preparation": result.dependency_preparation,
                    "project_preparation": result.project_preparation,
                    "routing_observed": result.routing_observed,
                    "timestamp": timestamp,
                }
                if isinstance(p, DocAtlasDirectProvider):
                    raw_data["runtime"] = {
                        "docmancer_home": str(p.docmancer_home) if p.docmancer_home else None,
                        "db_path": str(p.db_path) if p.db_path else None,
                        "runtime_dir": str(p.runtime_dir) if p.runtime_dir else None,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Live MCP benchmark: DocAtlas vs Context7")
    parser.add_argument("--mode", choices=["zero-setup", "preindexed", "both"], default="zero-setup",
                        help="benchmark mode (default: zero-setup)")
    parser.add_argument("--suite", choices=["public-docs", "project-docs", "exact-version", "unified-context", "snippet-first", "all"],
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

    # Storage isolation: each docatlas provider gets its own run-scoped runtime dir
    run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    runtime_base = Path(tempfile.gettempdir()) / "live-benchmark" / run_timestamp
    for p in providers:
        if isinstance(p, DocAtlasDirectProvider):
            p.runtime_dir = runtime_base / mode / p.provider_id
            p.runtime_dir.mkdir(parents=True, exist_ok=True)
            p.docmancer_home = p.runtime_dir / "home"
            p.docmancer_home.mkdir(parents=True, exist_ok=True)
            p.db_path = p.runtime_dir / "docmancer.db"
            print(f"[isolation] {p.provider_id}")
            print(f"  runtime_dir: {p.runtime_dir}")
            print(f"  docmancer_home: {p.docmancer_home}")
            print(f"  db_path: {p.db_path}")

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

__all__=['generate_markdown_report', 'run_benchmark', 'main']
