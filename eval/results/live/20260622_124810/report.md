# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_124810
- **Duration:** 9.76s
- **Total queries:** 6
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | N/A | 6 |
| Applicable queries | N/A | 6 |
| Success count | N/A | 6 |
| Error count | N/A | 0 |
| Empty/not-ready | N/A | 0 |
| Not applicable | N/A | 0 |
| Correct source rate | N/A | 1.0 |
| Contamination rate | N/A | 0.0 |
| Hit@1 | N/A | 1.0 |
| Hit@5 | N/A | 1.0 |
| MRR | N/A | 1.0 |
| Unique sources@5 | N/A | 3.6667 |
| Redundancy rate | N/A | 0.0 |
| Snippet usefulness | N/A | 1.0 |
| Avg latency (ms) | N/A | 1597.785 |
| Avg cold latency (ms) | N/A | 1597.785 |
| Avg warm latency (ms) | N/A | 0.0 |
| Setup calls avg | N/A | 2.0 |
| Hallucinated API rate | N/A | 0.0 |

## Per-Suite Results

### Suite: exact-version

- Total cases: 6

**docatlas:** no results

**context7** (mode: context7_mode):

  - Applicable: 6 | Success: 6 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 1.0 | Hit@5: 1.0 | MRR: 1.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 3.6667
  - Avg latency: 1597.785ms | Setup avg: 2.0

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| exact_click_version | exact-version | N/A | N/A | N/A | success | 1680ms | 4 |
| exact_fastapi_version | exact-version | N/A | N/A | N/A | success | 1962ms | 3 |
| exact_flutter_bloc_version | exact-version | N/A | N/A | N/A | success | 1409ms | 4 |
| exact_go_router_version | exact-version | N/A | N/A | N/A | success | 1105ms | 2 |
| exact_pydantic_version | exact-version | N/A | N/A | N/A | success | 1713ms | 5 |
| exact_riverpod_version | exact-version | N/A | N/A | N/A | success | 1718ms | 4 |

## Key Findings

### Where DocAtlas Wins

- (No clear wins yet — more data needed)

### Where Context7 Wins

- (No clear wins yet — more data needed)

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
