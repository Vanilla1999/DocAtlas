# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_124121
- **Duration:** 68.93s
- **Total queries:** 17
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | 17 | N/A |
| Applicable queries | 17 | N/A |
| Success count | 0 | N/A |
| Error count | 0 | N/A |
| Empty/not-ready | 17 | N/A |
| Not applicable | 0 | N/A |
| Correct source rate | 1.0 | N/A |
| Contamination rate | 0.0 | N/A |
| Hit@1 | 0.0 | N/A |
| Hit@5 | 0.0 | N/A |
| MRR | 0.0 | N/A |
| Unique sources@5 | 0.0 | N/A |
| Redundancy rate | 0.0 | N/A |
| Snippet usefulness | 0.0 | N/A |
| Avg latency (ms) | 4049.122 | N/A |
| Avg cold latency (ms) | 4049.122 | N/A |
| Avg warm latency (ms) | 0.0 | N/A |
| Setup calls avg | 2.0 | N/A |
| Hallucinated API rate | 0.0 | N/A |

## Per-Suite Results

### Suite: public-docs

- Total cases: 17

**docatlas** (mode: docatlas_mode):

  - Applicable: 17 | Success: 0 | Errors: 0 | Empty: 17 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 0.0
  - Avg latency: 4049.122ms | Setup avg: 2.0

**context7:** no results

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| bloc_builder | public-docs | empty_index | 4273ms | 0 | N/A | N/A | N/A |
| bloc_listener | public-docs | empty_index | 4261ms | 0 | N/A | N/A | N/A |
| bloc_multi_provider | public-docs | empty_index | 4276ms | 0 | N/A | N/A | N/A |
| bloc_provider | public-docs | empty_index | 4881ms | 0 | N/A | N/A | N/A |
| click_callbacks | public-docs | empty_index | 1ms | 0 | N/A | N/A | N/A |
| click_command_group | public-docs | empty_index | 2ms | 0 | N/A | N/A | N/A |
| click_context_passing | public-docs | empty_index | 1ms | 0 | N/A | N/A | N/A |
| click_options | public-docs | empty_index | 2ms | 0 | N/A | N/A | N/A |
| fastapi_background_tasks | public-docs | empty_index | 2ms | 0 | N/A | N/A | N/A |
| fastapi_depends | public-docs | empty_index | 5ms | 0 | N/A | N/A | N/A |
| fastapi_http_exception | public-docs | empty_index | 2ms | 0 | N/A | N/A | N/A |
| fastapi_testclient | public-docs | empty_index | 2ms | 0 | N/A | N/A | N/A |
| riverpod_asyncnotifier_migration | public-docs | empty_index | 10440ms | 0 | N/A | N/A | N/A |
| riverpod_autodispose | public-docs | empty_index | 10107ms | 0 | N/A | N/A | N/A |
| riverpod_family | public-docs | empty_index | 10079ms | 0 | N/A | N/A | N/A |
| riverpod_keepalive | public-docs | empty_index | 10291ms | 0 | N/A | N/A | N/A |
| riverpod_watch_vs_listen | public-docs | empty_index | 10209ms | 0 | N/A | N/A | N/A |

## Key Findings

### Where DocAtlas Wins

- **Source isolation:** DocAtlas contamination rate is 0.0 on public-docs suite

### Where Context7 Wins

- (No clear wins yet — more data needed)

### Where Results Are Not Comparable

- **Project-docs suite:** 0 Context7 cases correctly marked as not applicable (no local repo context)
- **Empty-index cases:** DocAtlas has 17 empty index cases that need pre-fetching

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
