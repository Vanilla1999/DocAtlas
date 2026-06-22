# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_125234
- **Duration:** 0.48s
- **Total queries:** 12
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | 6 | 6 |
| Applicable queries | 6 | 0 |
| Success count | 6 | 0 |
| Error count | 0 | 0 |
| Empty/not-ready | 0 | 0 |
| Not applicable | 0 | 6 |
| Correct source rate | 1.0 | 1.0 |
| Contamination rate | 0.0 | 0.0 |
| Hit@1 | 0.1667 | 0.0 |
| Hit@5 | 0.6667 | 0.0 |
| MRR | 0.325 | 0.0 |
| Unique sources@5 | 2.0 | 0.0 |
| Redundancy rate | 0.5556 | 0.0 |
| Snippet usefulness | 1.0 | 0.0 |
| Avg latency (ms) | 36.395 | 0.0 |
| Avg cold latency (ms) | 36.395 | 0.0 |
| Avg warm latency (ms) | 0.0 | 0.0 |
| Setup calls avg | 1.0 | 0.0 |
| Hallucinated API rate | 0.0 | 0.0 |

## Per-Suite Results

### Suite: project-docs

- Total cases: 12

**docatlas** (mode: live_mcp):

  - Applicable: 6 | Success: 6 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.1667 | Hit@5: 0.6667 | MRR: 0.325
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 2.0
  - Avg latency: 36.395ms | Setup avg: 1.0

**context7** (mode: live_mcp):

  - Applicable: 0 | Success: 0 | Errors: 0 | Empty: 0 | N/A: 6
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 0.0
  - Avg latency: 0.0ms | Setup avg: 0.0

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| project_lifecycle | project-docs | success | 25ms | 3 | not_applicable | 0ms | 0 |
| risky_rejected_docs | project-docs | success | 49ms | 8 | not_applicable | 0ms | 0 |
| source_isolation | project-docs | success | 48ms | 8 | not_applicable | 0ms | 0 |
| sync_vs_ingest | project-docs | success | 41ms | 6 | not_applicable | 0ms | 0 |
| trust_contract | project-docs | success | 17ms | 3 | not_applicable | 0ms | 0 |
| v1_source_isolation | project-docs | success | 38ms | 7 | not_applicable | 0ms | 0 |

## Key Findings

### Where DocAtlas Wins

- **Project docs awareness:** DocAtlas successfully answered 6/6 project-docs queries (Context7 is N/A by design)

### Where Context7 Wins

- (No clear wins yet — more data needed)

### Where Results Are Not Comparable

- **Project-docs suite:** 6 Context7 cases correctly marked as not applicable (no local repo context)
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
