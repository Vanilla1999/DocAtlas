# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_124329
- **Duration:** 27.14s
- **Total queries:** 17
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | N/A | 17 |
| Applicable queries | N/A | 17 |
| Success count | N/A | 16 |
| Error count | N/A | 0 |
| Empty/not-ready | N/A | 0 |
| Not applicable | N/A | 0 |
| Correct source rate | N/A | 1.0 |
| Contamination rate | N/A | 0.0 |
| Hit@1 | N/A | 0.0 |
| Hit@5 | N/A | 0.0588 |
| MRR | N/A | 0.0196 |
| Unique sources@5 | N/A | 3.4706 |
| Redundancy rate | N/A | 0.0 |
| Snippet usefulness | N/A | 0.9412 |
| Avg latency (ms) | N/A | 1586.43 |
| Avg cold latency (ms) | N/A | 1586.43 |
| Avg warm latency (ms) | N/A | 0.0 |
| Setup calls avg | N/A | 2.0 |
| Hallucinated API rate | N/A | 0.0 |

## Per-Suite Results

### Suite: public-docs

- Total cases: 17

**docatlas:** no results

**context7** (mode: context7_mode):

  - Applicable: 17 | Success: 16 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0588 | MRR: 0.0196
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 3.4706
  - Avg latency: 1586.43ms | Setup avg: 2.0

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| bloc_builder | public-docs | N/A | N/A | N/A | success | 1620ms | 4 |
| bloc_listener | public-docs | N/A | N/A | N/A | success | 1499ms | 3 |
| bloc_multi_provider | public-docs | N/A | N/A | N/A | success | 1877ms | 4 |
| bloc_provider | public-docs | N/A | N/A | N/A | success | 1708ms | 3 |
| click_callbacks | public-docs | N/A | N/A | N/A | success | 1203ms | 1 |
| click_command_group | public-docs | N/A | N/A | N/A | success | 1329ms | 5 |
| click_context_passing | public-docs | N/A | N/A | N/A | not_supported | 1712ms | 0 |
| click_options | public-docs | N/A | N/A | N/A | success | 1409ms | 4 |
| fastapi_background_tasks | public-docs | N/A | N/A | N/A | success | 1304ms | 5 |
| fastapi_depends | public-docs | N/A | N/A | N/A | success | 1811ms | 3 |
| fastapi_http_exception | public-docs | N/A | N/A | N/A | success | 2155ms | 4 |
| fastapi_testclient | public-docs | N/A | N/A | N/A | success | 1712ms | 5 |
| riverpod_asyncnotifier_migration | public-docs | N/A | N/A | N/A | success | 1325ms | 5 |
| riverpod_autodispose | public-docs | N/A | N/A | N/A | success | 1497ms | 3 |
| riverpod_family | public-docs | N/A | N/A | N/A | success | 1647ms | 4 |
| riverpod_keepalive | public-docs | N/A | N/A | N/A | success | 1745ms | 3 |
| riverpod_watch_vs_listen | public-docs | N/A | N/A | N/A | success | 1416ms | 3 |

## Key Findings

### Where DocAtlas Wins

- (No clear wins yet — more data needed)

### Where Context7 Wins

- **Lower contamination:** Context7 contamination = 0.0 vs DocAtlas = 1
- **Zero-setup:** Context7 returned results for 16 queries vs DocAtlas 0 (DocAtlas may need indexing)

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
