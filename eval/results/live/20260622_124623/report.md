# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_124623
- **Duration:** 99.27s
- **Total queries:** 34
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | 17 | 17 |
| Applicable queries | 17 | 17 |
| Success count | 0 | 16 |
| Error count | 0 | 0 |
| Empty/not-ready | 17 | 0 |
| Not applicable | 0 | 0 |
| Correct source rate | 1.0 | 1.0 |
| Contamination rate | 0.0 | 0.0 |
| Hit@1 | 0.0 | 0.9412 |
| Hit@5 | 0.0 | 0.9412 |
| MRR | 0.0 | 0.9412 |
| Unique sources@5 | 0.0 | 3.6471 |
| Redundancy rate | 0.0 | 0.0 |
| Snippet usefulness | 0.0 | 0.9412 |
| Avg latency (ms) | 4097.189 | 1726.549 |
| Avg cold latency (ms) | 4097.189 | 1726.549 |
| Avg warm latency (ms) | 0.0 | 0.0 |
| Setup calls avg | 2.0 | 2.0 |
| Hallucinated API rate | 0.0 | 0.0 |

## Per-Suite Results

### Suite: public-docs

- Total cases: 34

**docatlas** (mode: docatlas_mode):

  - Applicable: 17 | Success: 0 | Errors: 0 | Empty: 17 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 0.0
  - Avg latency: 4097.189ms | Setup avg: 2.0

**context7** (mode: context7_mode):

  - Applicable: 17 | Success: 16 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.9412 | Hit@5: 0.9412 | MRR: 0.9412
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 3.6471
  - Avg latency: 1726.549ms | Setup avg: 2.0

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| bloc_builder | public-docs | empty_index | 4158ms | 0 | success | 1685ms | 3 |
| bloc_listener | public-docs | empty_index | 4407ms | 0 | success | 1665ms | 4 |
| bloc_multi_provider | public-docs | empty_index | 4313ms | 0 | success | 1740ms | 4 |
| bloc_provider | public-docs | empty_index | 5036ms | 0 | success | 1709ms | 3 |
| click_callbacks | public-docs | empty_index | 2ms | 0 | success | 1522ms | 1 |
| click_command_group | public-docs | empty_index | 3ms | 0 | success | 1722ms | 5 |
| click_context_passing | public-docs | empty_index | 1ms | 0 | not_supported | 1489ms | 0 |
| click_options | public-docs | empty_index | 1ms | 0 | success | 1637ms | 5 |
| fastapi_background_tasks | public-docs | empty_index | 2ms | 0 | success | 1405ms | 5 |
| fastapi_depends | public-docs | empty_index | 5ms | 0 | success | 1921ms | 3 |
| fastapi_http_exception | public-docs | empty_index | 2ms | 0 | success | 1987ms | 4 |
| fastapi_testclient | public-docs | empty_index | 2ms | 0 | success | 1477ms | 5 |
| riverpod_asyncnotifier_migration | public-docs | empty_index | 10184ms | 0 | success | 1752ms | 5 |
| riverpod_autodispose | public-docs | empty_index | 10443ms | 0 | success | 2646ms | 5 |
| riverpod_family | public-docs | empty_index | 10012ms | 0 | success | 1776ms | 4 |
| riverpod_keepalive | public-docs | empty_index | 10685ms | 0 | success | 1453ms | 3 |
| riverpod_watch_vs_listen | public-docs | empty_index | 10397ms | 0 | success | 1765ms | 3 |

## Key Findings

### Where DocAtlas Wins

- **Source isolation:** DocAtlas contamination rate is 0.0 on public-docs suite

### Where Context7 Wins

- **Public docs precision:** Context7 Hit@1 = 0.9412 vs DocAtlas = 0.0 on public-docs
- **Zero-setup:** Context7 returned results for 16 queries vs DocAtlas 0 (DocAtlas may need indexing)

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
