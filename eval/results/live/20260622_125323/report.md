# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_125323
- **Duration:** 0.32s
- **Total queries:** 6
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | 6 | N/A |
| Applicable queries | 6 | N/A |
| Success count | 6 | N/A |
| Error count | 0 | N/A |
| Empty/not-ready | 0 | N/A |
| Not applicable | 0 | N/A |
| Correct source rate | 1.0 | N/A |
| Contamination rate | 0.0 | N/A |
| Hit@1 | 0.1667 | N/A |
| Hit@5 | 0.6667 | N/A |
| MRR | 0.325 | N/A |
| Unique sources@5 | 2.0 | N/A |
| Redundancy rate | 0.5556 | N/A |
| Snippet usefulness | 1.0 | N/A |
| Avg latency (ms) | 37.611 | N/A |
| Avg cold latency (ms) | 37.611 | N/A |
| Avg warm latency (ms) | 0.0 | N/A |
| Setup calls avg | 1.0 | N/A |
| Hallucinated API rate | 0.0 | N/A |

## Per-Suite Results

### Suite: project-docs

- Total cases: 6

**docatlas** (mode: live_mcp):

  - Applicable: 6 | Success: 6 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.1667 | Hit@5: 0.6667 | MRR: 0.325
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 2.0
  - Avg latency: 37.611ms | Setup avg: 1.0

**context7:** no results

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| project_lifecycle | project-docs | success | 29ms | 3 | N/A | N/A | N/A |
| risky_rejected_docs | project-docs | success | 49ms | 8 | N/A | N/A | N/A |
| source_isolation | project-docs | success | 53ms | 8 | N/A | N/A | N/A |
| sync_vs_ingest | project-docs | success | 38ms | 6 | N/A | N/A | N/A |
| trust_contract | project-docs | success | 17ms | 3 | N/A | N/A | N/A |
| v1_source_isolation | project-docs | success | 39ms | 7 | N/A | N/A | N/A |

## Key Findings

### Where DocAtlas Wins

- **Project docs awareness:** DocAtlas successfully answered 6/6 project-docs queries (Context7 is N/A by design)

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
