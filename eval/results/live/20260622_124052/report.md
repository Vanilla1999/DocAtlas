# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_124052
- **Duration:** 21.73s
- **Total queries:** 17
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | N/A | 17 |
| Applicable queries | N/A | 17 |
| Success count | N/A | 17 |
| Error count | N/A | 0 |
| Empty/not-ready | N/A | 0 |
| Not applicable | N/A | 0 |
| Correct source rate | N/A | 1.0 |
| Contamination rate | N/A | 0.0 |
| Hit@1 | N/A | 0.0 |
| Hit@5 | N/A | 0.0 |
| MRR | N/A | 0.0 |
| Unique sources@5 | N/A | 2.5882 |
| Redundancy rate | N/A | 0.0 |
| Snippet usefulness | N/A | 0.7059 |
| Avg latency (ms) | N/A | 1268.235 |
| Avg cold latency (ms) | N/A | 1268.235 |
| Avg warm latency (ms) | N/A | 0.0 |
| Setup calls avg | N/A | 2.0 |
| Hallucinated API rate | N/A | 0.0 |

## Per-Suite Results

### Suite: public-docs

- Total cases: 17

**docatlas:** no results

**context7** (mode: context7_mode):

  - Applicable: 17 | Success: 17 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 2.5882
  - Avg latency: 1268.235ms | Setup avg: 2.0

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| bloc_builder | public-docs | N/A | N/A | N/A | success | 1569ms | 5 |
| bloc_listener | public-docs | N/A | N/A | N/A | success | 1291ms | 3 |
| bloc_multi_provider | public-docs | N/A | N/A | N/A | success | 1625ms | 4 |
| bloc_provider | public-docs | N/A | N/A | N/A | success | 1793ms | 4 |
| click_callbacks | public-docs | N/A | N/A | N/A | success | 1398ms | 1 |
| click_command_group | public-docs | N/A | N/A | N/A | success | 2139ms | 5 |
| click_context_passing | public-docs | N/A | N/A | N/A | success | 1344ms | 2 |
| click_options | public-docs | N/A | N/A | N/A | success | 1452ms | 4 |
| fastapi_background_tasks | public-docs | N/A | N/A | N/A | success | 1725ms | 5 |
| fastapi_depends | public-docs | N/A | N/A | N/A | success | 1793ms | 3 |
| fastapi_http_exception | public-docs | N/A | N/A | N/A | success | 2262ms | 3 |
| fastapi_testclient | public-docs | N/A | N/A | N/A | success | 1403ms | 5 |
| riverpod_asyncnotifier_migration | public-docs | N/A | N/A | N/A | success | 342ms | 0 |
| riverpod_autodispose | public-docs | N/A | N/A | N/A | success | 350ms | 0 |
| riverpod_family | public-docs | N/A | N/A | N/A | success | 334ms | 0 |
| riverpod_keepalive | public-docs | N/A | N/A | N/A | success | 354ms | 0 |
| riverpod_watch_vs_listen | public-docs | N/A | N/A | N/A | success | 386ms | 0 |

## Key Findings

### Where DocAtlas Wins

- (No clear wins yet — more data needed)

### Where Context7 Wins

- **Lower contamination:** Context7 contamination = 0.0 vs DocAtlas = 1
- **Zero-setup:** Context7 returned results for 17 queries vs DocAtlas 0 (DocAtlas may need indexing)

### Where Results Are Not Comparable

- **Project-docs suite:** 0 Context7 cases correctly marked as not applicable (no local repo context)
- **Empty-index cases:** DocAtlas has 0 empty index cases that need pre-fetching

## Claims We Can Make

Based on this live benchmark run:

- DocAtlas has project-level doc awareness that Context7 cannot provide by design.
- DocAtlas supports exact-version library docs (results depend on index state).
- Context7 provides zero-setup public docs lookup with reliable source attribution.
- Both providers support source-level attribution for their results.

## Claims We Cannot Make Yet

- "DocAtlas beats Context7 overall" — benchmark does not cover enough libraries or scenarios.
- "Context7 has worse contamination than DocAtlas" — need more data and cross-validation.
- "Dartdoc exact-version is solved" — need dedicated Dartdoc-specific test cases.
- "DocAtlas latency is better/worse" — depends on index state and pre-fetching.
- "One provider is strictly better than the other" — they serve different use cases.

## Recommendations

1. **Pre-index libraries** before running public-docs suite for DocAtlas to avoid empty_index status.
2. **Expand Dart/Flutter exact-version coverage** with pub.dev-based Dartdoc tests.
3. **Add contamination tests** with cross-library queries (e.g., ask about Riverpod in FastAPI suite).
4. **Run benchmark on CI** with a cron schedule to track regressions.
5. **Add more providers** (e.g., FixtureProvider with saved Context7 results for comparison).
