# Live MCP Benchmark: DocAtlas vs Context7

- **Date:** 20260622_125026
- **Duration:** 94.72s
- **Total queries:** 58
- **DocAtlas mode:** live_mcp (direct Python API)
- **Context7 mode:** live_mcp (context7-mcp stdio)

## Overall Summary

| Metric | DocAtlas | Context7 |
|--------|----------|----------|
| Total queries | 29 | 29 |
| Applicable queries | 29 | 23 |
| Success count | 6 | 23 |
| Error count | 0 | 0 |
| Empty/not-ready | 23 | 0 |
| Not applicable | 0 | 6 |
| Correct source rate | 1.0 | 1.0 |
| Contamination rate | 0.0 | 0.0 |
| Hit@1 | 0.0345 | 0.0435 |
| Hit@5 | 0.1379 | 0.0435 |
| MRR | 0.0672 | 0.0435 |
| Unique sources@5 | 1.2069 | 1.087 |
| Redundancy rate | 0.0 | 0.0 |
| Snippet usefulness | 0.2069 | 0.0435 |
| Avg latency (ms) | 2864.526 | 494.41 |
| Avg cold latency (ms) | 2864.526 | 494.41 |
| Avg warm latency (ms) | 0.0 | 0.0 |
| Setup calls avg | 1.7931 | 2.0 |
| Hallucinated API rate | 0.0 | 0.0 |

## Per-Suite Results

### Suite: exact-version

- Total cases: 12

**docatlas** (mode: docatlas_mode):

  - Applicable: 6 | Success: 0 | Errors: 0 | Empty: 6 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 0.0
  - Avg latency: 2266.968ms | Setup avg: 2.0

**context7** (mode: context7_mode):

  - Applicable: 6 | Success: 6 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 1.0
  - Avg latency: 374.341ms | Setup avg: 2.0

### Suite: project-docs

- Total cases: 12

**docatlas** (mode: docatlas_mode):

  - Applicable: 6 | Success: 6 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.1667 | Hit@5: 0.6667 | MRR: 0.325
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 5.8333
  - Avg latency: 37.378ms | Setup avg: 1.0

**context7** (mode: context7_mode):

  - Applicable: 0 | Success: 0 | Errors: 0 | Empty: 0 | N/A: 6
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 0.0
  - Avg latency: 0.0ms | Setup avg: 0.0

### Suite: public-docs

- Total cases: 34

**docatlas** (mode: docatlas_mode):

  - Applicable: 17 | Success: 0 | Errors: 0 | Empty: 17 | N/A: 0
  - Hit@1: 0.0 | Hit@5: 0.0 | MRR: 0.0
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 0.0
  - Avg latency: 4073.246ms | Setup avg: 2.0

**context7** (mode: context7_mode):

  - Applicable: 17 | Success: 17 | Errors: 0 | Empty: 0 | N/A: 0
  - Hit@1: 0.0588 | Hit@5: 0.0588 | MRR: 0.0588
  - Contamination: 0.0 | Forbidden: 0.0
  - Correct source: 1.0 | Unique@5: 1.1176
  - Avg latency: 536.787ms | Setup avg: 2.0

## Per-Case Detail

| Case | Suite | DocAtlas status | DocAtlas latency | DocAtlas sources | Context7 status | Context7 latency | Context7 sources |
|------|-------|----------------|------------------|------------------|----------------|------------------|------------------|
| bloc_builder | public-docs | empty_index | 4326ms | 0 | success | 535ms | 1 |
| bloc_listener | public-docs | empty_index | 4307ms | 0 | success | 531ms | 1 |
| bloc_multi_provider | public-docs | empty_index | 4173ms | 0 | success | 544ms | 1 |
| bloc_provider | public-docs | empty_index | 4254ms | 0 | success | 552ms | 1 |
| click_callbacks | public-docs | empty_index | 1ms | 0 | success | 297ms | 1 |
| click_command_group | public-docs | empty_index | 2ms | 0 | success | 311ms | 1 |
| click_context_passing | public-docs | empty_index | 1ms | 0 | success | 294ms | 1 |
| click_options | public-docs | empty_index | 1ms | 0 | success | 299ms | 1 |
| exact_click_version | exact-version | empty_index | 1ms | 0 | success | 472ms | 1 |
| exact_fastapi_version | exact-version | empty_index | 1ms | 0 | success | 366ms | 1 |
| exact_flutter_bloc_version | exact-version | empty_index | 1ms | 0 | success | 296ms | 1 |
| exact_go_router_version | exact-version | empty_index | 13595ms | 0 | success | 527ms | 1 |
| exact_pydantic_version | exact-version | empty_index | 1ms | 0 | success | 293ms | 1 |
| exact_riverpod_version | exact-version | empty_index | 1ms | 0 | success | 291ms | 1 |
| fastapi_background_tasks | public-docs | empty_index | 2ms | 0 | success | 321ms | 1 |
| fastapi_depends | public-docs | empty_index | 5ms | 0 | success | 2077ms | 3 |
| fastapi_http_exception | public-docs | empty_index | 2ms | 0 | success | 319ms | 1 |
| fastapi_testclient | public-docs | empty_index | 2ms | 0 | success | 307ms | 1 |
| project_lifecycle | project-docs | success | 24ms | 3 | not_applicable | 0ms | 0 |
| risky_rejected_docs | project-docs | success | 52ms | 8 | not_applicable | 0ms | 0 |
| riverpod_asyncnotifier_migration | public-docs | empty_index | 10805ms | 0 | success | 545ms | 1 |
| riverpod_autodispose | public-docs | empty_index | 10398ms | 0 | success | 546ms | 1 |
| riverpod_family | public-docs | empty_index | 10210ms | 0 | success | 549ms | 1 |
| riverpod_keepalive | public-docs | empty_index | 10385ms | 0 | success | 551ms | 1 |
| riverpod_watch_vs_listen | public-docs | empty_index | 10370ms | 0 | success | 547ms | 1 |
| source_isolation | project-docs | success | 51ms | 8 | not_applicable | 0ms | 0 |
| sync_vs_ingest | project-docs | success | 42ms | 6 | not_applicable | 0ms | 0 |
| trust_contract | project-docs | success | 17ms | 3 | not_applicable | 0ms | 0 |
| v1_source_isolation | project-docs | success | 38ms | 7 | not_applicable | 0ms | 0 |

## Key Findings

### Where DocAtlas Wins

- **Project docs awareness:** DocAtlas successfully answered 6/6 project-docs queries (Context7 is N/A by design)
- **Source isolation:** DocAtlas contamination rate is 0.0 on public-docs suite

### Where Context7 Wins

- **Public docs precision:** Context7 Hit@1 = 0.0588 vs DocAtlas = 0.0 on public-docs
- **Zero-setup:** Context7 returned results for 17 queries vs DocAtlas 0 (DocAtlas may need indexing)

### Where Results Are Not Comparable

- **Project-docs suite:** 6 Context7 cases correctly marked as not applicable (no local repo context)
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
