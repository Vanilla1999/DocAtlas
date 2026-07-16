# DocAtlas MCP vs Context7 — comparison report

Status: initial comparison plus first retrieval-quality fixes, based on the Riverpod benchmark, a FastAPI mini-benchmark, and the benchmark plan in `eval/context7_benchmark_plan.md`.

## Executive summary

The first comparison shows a clear split:

- **Context7 is better for zero-setup public documentation lookup.** It returned relevant Riverpod content for all 5 benchmark queries, presented code snippets cleanly, and avoided translation/duplicate noise.
- **DocAtlas MCP is better positioned for local, repeated, project-aware work.** After indexing, it was faster per query, can work offline, reports token efficiency, and can combine public docs with repo-owned docs and exact project dependency metadata.
- **DocAtlas's initial public-docs retrieval gap was source hygiene and deterministic ranking, not the core product direction.** The Riverpod miss was caused by translated pages and repeated sections diluting top-K results; the first fix pass now ranks all 5 Riverpod golden queries at rank 1 with zero locale contamination.
- **The FastAPI mini-benchmark showed a ranking gap, not a recall gap.** DocAtlas returned the needed facts for 3/3 FastAPI queries; after intent-sensitive reranking, all 3 FastAPI golden queries now rank the canonical source first.
- **The strongest DocAtlas claims still need a dedicated benchmark.** The current Riverpod run used latest `riverpod.dev` docs for both tools, so it did not fully test exact-version Dartdoc ingestion or project-owned docs retrieval.

Recommended positioning from this run:

- Use **Context7** for quick one-off public API questions.
- Use **DocAtlas MCP** when the agent needs local docs, offline docs, exact dependency versions, source metadata, token-aware context packs, or project-owned README/docs/ADR context.

DocAtlas now exposes trusted code examples as first-class snippet-first context while preserving project context, source attribution, and exact-version diagnostics. This closes a presentation gap with Context7 for coding queries, but it does not mean every documentation page contains executable code or that DocAtlas wins every public-doc lookup.

## Test scope

This report uses the available Riverpod comparison artifacts:

- `eval/riverpod_benchmark_report.md`
- `eval/results/docmancer_riverpod_results.json`
- `eval/results/docmancer_fastapi_results.json`
- `eval/fastapi_golden.yaml`
- `roadmap/arhive/09_riverpod_context7_benchmark_followups.md`
- benchmark plan: `eval/context7_benchmark_plan.md`

It also includes a small FastAPI public-docs mini-benchmark run directly through Context7 and DocAtlas MCP tools.

The benchmark compared:

| Dimension | Context7 | DocAtlas MCP |
|---|---|---|
| Source | `/websites/riverpod_dev` hosted corpus | `https://riverpod.dev` indexed locally |
| Version | latest Riverpod docs | latest Riverpod docs |
| Corpus size | 402 snippets | 135 pages, 1202 sections |
| Setup time | 0s | ~2 min for `doc-atlas add` + indexing |
| Offline after setup | No | Yes |

Important limitation: this was a public-docs parity test, not a full exact-version/project-aware test. The benchmark did not yet prove DocAtlas's strongest advantage: resolving and querying the exact dependency documentation from a project lockfile.

## Retrieval results

### Aggregate metrics

| Metric | DocAtlas MCP | Context7 | Notes |
|---|---:|---:|---|
| Hit@1 | 0.8 | 1.0 manual | Context7 assessment was manual, not yet snapshot-graded. |
| Hit@3 | 0.8 | not separately measured | Context7 returned relevant content at rank 1 for all 5 queries. |
| Hit@5 | 0.8 | 1.0 manual | DocAtlas missed 1 of 5 queries. |
| MRR | 0.8 | 1.0 manual | Same limitation: Context7 needs persisted snapshots. |
| p50 latency | ~1101ms | ~2s manual | DocAtlas faster after indexing. |
| p95 latency | ~1625ms | ~2s manual | DocAtlas faster after indexing. |
| Setup/cold-start | ~2 min | ~0s | Context7 wins first-use UX. |
| Offline readiness | Yes after index | No | DocAtlas wins offline/repeated loop. |
| Token savings | measured on one query: 45.5% | not reported | Need token metrics for all queries. |

After the first source-hygiene, source-diversity, and intent-ranking fixes, the saved Riverpod eval snapshot reports:

| Metric | DocAtlas MCP after fixes | Notes |
|---|---:|---|
| Hit@1 | 1.0 | 5-query `eval/riverpod_golden.yaml` suite. |
| Hit@5 | 1.0 | `rp_ref_watch_listen` now ranks `https://riverpod.dev/docs/concepts2/refs` at rank 1. |
| MRR | 1.0 | Saved in `eval/results/docmancer_riverpod_results.json`. |
| Locale contamination | 0.0 | Translated mirror pages no longer appear in default top-K. |
| Snippet present@5 | 1.0 | Code-like snippets are detected in every Riverpod golden query's top 5. |

### Per-query outcome

| Query | DocAtlas MCP | Context7 | Main observation |
|---|---|---|---|
| `rp_provider_lifecycle` — `autoDispose` + `keepAlive` | Hit, rank 1 | Hit | DocAtlas returned relevant content but repeated `auto_dispose` sections. |
| `rp_family_code_example` — `family` + `FutureProvider` | Hit, rank 1 | Hit | DocAtlas returned several sections from the same `family` page. |
| `rp_notifier_vs_asyncnotifier` — migration from `StateNotifier` | Hit, rank 1 | Hit | DocAtlas content was relevant but less diverse than Context7 snippets. |
| `rp_ref_watch_listen` — `ref.watch` vs `ref.listen` lifecycle | Initial miss; rank 1 after fixes | Hit | The expected `refs` page now ranks first after URL replace-update and API-term intent rerank. |
| `rp_autodispose_generator` — `@riverpod` annotation | Hit, rank 1 | Hit | Both tools found relevant content. |

## FastAPI mini-benchmark

This follow-up run tested a small public-docs suite for FastAPI. It is not a full benchmark run because outputs were assessed directly from tool responses and not yet persisted as machine-graded snapshots.

Setup:

| Dimension | Context7 | DocAtlas MCP |
|---|---|---|
| Library | `/websites/fastapi_tiangolo` | `FastAPI`, `ecosystem=python`, `source_type=web` |
| Docs source | hosted Context7 corpus | `https://fastapi.tiangolo.com/` |
| Query count | 3 | 3 |
| Version | latest/default | latest/default |
| First DocAtlas call | not applicable | refreshed stale registered source at `2026-06-06T08:20:26+00:00` |

Queries:

- `fastapi_depends_basic`: dependency function with `Depends` in a path operation.
- `fastapi_http_exception`: raise `HTTPException` with `status_code` and `detail`.
- `fastapi_testclient`: test an app with `fastapi.testclient.TestClient`.

### FastAPI retrieval outcome

| Query | Context7 result | DocAtlas MCP result | Assessment |
|---|---|---|---|
| `fastapi_depends_basic` | Rank 1: `https://fastapi.tiangolo.com/tutorial/dependencies` with direct `common_parameters` example. | Initial rank 1: `dependencies-with-yield`; after fixes rank 1: `tutorial/dependencies`. | Both returned required facts and usable `Depends` examples; DocAtlas now ranks the canonical tutorial first. |
| `fastapi_http_exception` | Rank 1: `reference/exceptions` with constructor, parameters, and minimal 404 example; also `tutorial/handling-errors`. | Initial rank 1: `dependencies-with-yield`; after fixes rank 1: `tutorial/handling-errors`. | Both returned correct `HTTPException` facts; DocAtlas now avoids advanced dependency-yield pages as the first result for this basic error query. |
| `fastapi_testclient` | Rank 1: `tutorial/testing` with `from fastapi.testclient import TestClient`, `client = TestClient(app)`, and pytest-style assertions. | After fixes rank 1: `tutorial/testing`; includes same import/client/assert pattern. | Both hit the canonical testing tutorial at rank 1. |

### FastAPI aggregate assessment

| Metric | DocAtlas MCP | Context7 | Notes |
|---|---:|---:|---|
| Fact-level Hit@5 | 3/3 | 3/3 | Both providers returned enough facts to answer correctly. |
| Canonical-source Hit@1 | Initial 1/3; after fixes 3/3 | 3/3 | Saved after-fix snapshot: `eval/results/docmancer_fastapi_results.json`. |
| Canonical-source Hit@5 | 3/3 | 3/3 | DocAtlas included expected sources within top-K for all three queries. |
| Snippet present@5 | 3/3 | high | DocAtlas now records snippet presence in eval metrics; Context7 still presents snippets more cleanly. |
| Source diversity | medium | high | DocAtlas mixed relevant pages but sometimes over-weighted advanced sections. |
| Version exactness | not tested | not tested | Both used latest/default docs. |
| Latency | not measured from MCP tool output | not measured from Context7 tool output | Riverpod latency findings remain the only measured latency data in this document. |

### FastAPI findings

1. Context7 still wins zero-setup UX for public docs lookup.
2. DocAtlas MCP returned enough information to answer all 3 queries, so this was not a recall failure.
3. DocAtlas's initial ranking issue was subtler than Riverpod: no locale pollution was observed, but advanced pages such as `dependencies-with-yield` outranked simpler tutorial/reference pages for basic questions.
4. The first intent-ranking fix now prefers introductory/tutorial pages for basic usage and testing queries, while preserving advanced pages as secondary context.
5. The snippet evidence MVP now records `code_snippets`, `has_code_snippet`, `snippet_present_at_5_rate`, and `snippet_sections_at_5_avg` so code-example quality is measured instead of only manually inspected.
5. The FastAPI run supports the same product conclusion as Riverpod: Context7 is excellent for quick public-doc snippets; DocAtlas remains more differentiated when local/project/version-aware context is needed.

## Qualitative findings

### Where Context7 wins

1. **Zero setup.** The flow is resolve library ID → query. There is no local indexing step.
2. **Clean hosted corpus.** The Riverpod results did not show translated-page pollution or repeated adjacent sections.
3. **Snippet presentation.** Context7 extracts code examples as clear snippets, which is convenient for coding agents.
4. **Public-docs hit rate in this run.** All 5 Riverpod queries returned relevant content at rank 1 by manual assessment.

### Where DocAtlas MCP wins

1. **Warm query latency.** After indexing, DocAtlas returned results around ~1s versus Context7's observed ~2s.
2. **Offline readiness.** Once indexed, the docs are local and can be queried without network access.
3. **Token-aware context packs.** DocAtlas reports raw-token equivalent, compact context tokens, savings percent, and agentic runway. Context7 does not expose equivalent token metrics in this comparison.
4. **Source and section attribution.** DocAtlas returns URL/title plus local section metadata, and project docs can include `source_class`, file path, heading path, and stale state.
5. **Project-aware wedge.** DocAtlas can inspect repo docs and dependency metadata through MCP. This is the major product distinction from Context7, but it still needs a dedicated benchmark run.

## Root causes of DocAtlas misses

### 1. Locale/translation pollution

Indexing `https://riverpod.dev` pulled translated copies such as:

- `ar`
- `bn`
- `de`
- `es`
- `fr`
- `it`
- `ja`
- `ko`
- `ru`
- `tr`
- `zh-Hans`

This polluted the corpus and contributed to the `rp_ref_watch_listen` miss. The expected `https://riverpod.dev/docs/concepts2/refs` page did not rank in top 5.

### 2. Low source diversity in top-K

DocAtlas often returned multiple sections from the same source page:

- `auto_dispose` repeated for provider lifecycle;
- `family` repeated for family/FutureProvider;
- `from_state_notifier` repeated for migration.

This is sometimes useful, but it wastes top-K slots when a coding agent needs breadth across concepts.

### 3. Code examples are embedded, not snippet-first

DocAtlas included examples inside sections, while Context7 presented snippets more directly. For agent coding tasks, snippet usability should be scored explicitly.

### 4. Hybrid degradation was under-reported

The Riverpod eval used `mode=hybrid`, but stderr showed sparse retrieval failures:

```text
Wrong input: Vector with name `sparse` is not configured in this collection, available names: dense
```

The eval JSON did not make this degradation visible enough. Future reports should mark degraded mode explicitly, for example `hybrid/dense_only_degraded`.

## Hypothesis assessment

| Hypothesis | Current result | Assessment |
|---|---|---|
| H1 — Public docs / quick lookup | Context7 5/5, DocAtlas 4/5 | Context7 currently wins. DocAtlas is close but needs source hygiene and top-K diversity. |
| H2 — Project-aware exact versions | Not tested | Needs dedicated Dartdoc/lockfile suite. |
| H3 — Project-owned docs + library docs | Not tested in this Riverpod run | Product capability exists, but comparison needs a fixture where local docs are required. |
| H4 — Offline / repeated loop | DocAtlas indexed locally and was faster warm | DocAtlas wins warm/offline scenario. |
| H5 — Context efficiency | DocAtlas reported 45.5% token savings on one query | Promising, but must measure every query. |

## Product interpretation

### Context7's best lane

Context7 is strongest when the user asks:

> “I need a quick answer from public docs for a popular library.”

It is particularly good when:

- no project metadata is needed;
- latest docs are acceptable;
- snippet presentation matters more than local ownership;
- the user wants no setup and no indexing.

### DocAtlas MCP's best lane

DocAtlas is strongest when the user asks:

> “Answer from the docs this project actually uses.”

It is particularly valuable when:

- the repository has README/docs/ADR/wiki that should guide the answer;
- dependency versions matter;
- private/local docs are involved;
- the agent will ask many related docs questions during a coding task;
- offline/reproducible docs context matters;
- token budget needs to be managed explicitly.

## Next benchmark work

### 1. Make the Riverpod comparison reproducible

Current Context7 scoring is manual. The next run should:

- persist Context7 raw outputs as snapshots;
- normalize Context7 and DocAtlas results into the same schema;
- grade both providers with the same evaluator;
- measure token counts for every query;
- add `unique_sources@5`, redundancy rate, and locale contamination rate;
- mark degraded retrieval mode in the result JSON.

### 2. Re-run Riverpod after DocAtlas source hygiene fixes

Target improvements:

- exclude locale mirrors by default for English Docusaurus docs;
- support path-prefix filtering such as `/docs/`;
- add `max_sections_per_source` or MMR-style top-K diversity;
- ensure `rp_ref_watch_listen` becomes Hit@5.

Target outcome:

| Metric | Current DocAtlas | Target DocAtlas |
|---|---:|---:|
| Riverpod Hit@5 | 0.8 | 1.0 |
| Locale contamination | high | 0 in default top 5 |
| Repeated sections | frequent | capped/diversified |
| Degraded mode visibility | weak | explicit in JSON/report |

### 3. Add exact-version Dartdoc benchmark

This is the most important next suite because it tests DocAtlas's differentiation.

Use a Flutter/Riverpod fixture with `pubspec.lock`, then index concrete Dartdoc pages, not only root pages. Candidate seed pages:

- `Provider`
- `FutureProvider`
- `StreamProvider`
- `Notifier`
- `AsyncNotifier`
- `Ref`
- `WidgetRef`
- `ConsumerWidget`
- `ConsumerStatefulWidget`

Scoring must penalize:

- Riverpod 3.0 docs for a Riverpod 2.6.x project;
- missing `requested_version` / `resolved_version` / `exact` metadata;
- answers that rely on latest docs when exact docs are available.

### 4. Add project-owned docs benchmark

Create a fixture where the correct answer requires both:

- project docs such as `README.md`, `docs/architecture.md`, ADRs, roadmap;
- external library docs.

Success criteria:

- DocAtlas result includes at least one project-owned source and one library source;
- Context7 cannot pass by using only public docs unless project context is manually injected;
- answer includes project-specific constraints, not just generic library advice.

### 5. Add coding-agent task benchmark

Retrieval quality should be connected to task completion. Run the same model and same coding tasks with only one provider enabled at a time.

Candidate tasks:

- add a Riverpod provider with correct `autoDispose` / `keepAlive` lifecycle;
- implement a FastAPI endpoint with dependency injection and error response;
- add pytest fixture parametrization;
- migrate a deprecated API while respecting the project's pinned dependency version.

Measure:

- tests passed;
- hallucinated API rate;
- number of tool calls;
- wall-clock time;
- docs tokens consumed;
- correction loops.

## Roadmap actions for DocAtlas

Priority fixes from this comparison:

1. **Clean web/Docusaurus ingest.** Default to canonical docs paths and exclude translation mirrors unless explicitly requested.
2. **Improve top-K diversity.** Add `max_sections_per_source` and/or MMR reranking.
3. **Improve snippet extraction.** Make code examples first-class in context packs.
4. **Expose eval degradation.** Persist sparse/dense/hybrid component failures in eval JSON.
5. **Upgrade eval scoring.** Score required facts, forbidden versions, token metrics, source diversity, and locale contamination.
6. **Ship exact-version Dartdoc benchmarks.** Use concrete class pages as seeds for key Pub packages.
7. **Ship project-docs benchmarks.** Prove the local project docs wedge against Context7.

## Final conclusion

The current result is not “Context7 wins” or “DocAtlas wins” globally. The result is:

- **Context7 wins the current public-docs quick lookup benchmark.** It is cleaner and requires no setup.
- **DocAtlas wins the local/repeated/offline/token-aware direction.** It already shows faster warm queries and richer context metadata.
- **DocAtlas's decisive comparison still needs exact-version and project-owned-docs suites.** Those are the scenarios where Context7 is least able to substitute DocAtlas's local MCP workflow.

The next report should therefore not only re-run Riverpod. It should add exact-version Dartdoc and project-docs tasks, because those test the actual product wedge: docs context from the project and dependency versions the agent is really working with.
