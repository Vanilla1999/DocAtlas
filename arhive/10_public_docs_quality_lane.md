# 10 — Public Docs Quality Lane

## Problem

Docmancer already has the right product wedge: local, project-aware, version-aware documentation for coding agents. But in public-docs parity tests against Context7, the first user-visible quality gap is simpler:

- top results can include translated mirrors of the same docs;
- top-K can waste slots on repeated sections from one source page;
- basic usage queries can rank advanced pages above canonical tutorials;
- code examples are present, but not surfaced as snippet-first evidence.

This makes Docmancer look worse than it is. The issue is not missing core capability; it is that the final context pack is too noisy for quick public-doc lookup.

## Idea

Build a narrow quality lane before bigger product work:

> Normalize the corpus first, then rerank for diverse, intent-matched, snippet-useful evidence.

The goal is to make the first 5 returned sections feel like a curated answer pack instead of raw search results.

This should be implemented as a deterministic retrieval/packing layer, not as an LLM judge or hosted reranker.

## Why this helps

Context7 currently wins because it gives clean public-doc snippets with low setup friction. Docmancer cannot remove indexing setup completely without changing the product, but it can close the quality gap after indexing.

If top-K is cleaner, Docmancer can credibly say:

- Context7 is better for instant public lookup;
- Docmancer is competitive on public lookup after indexing;
- Docmancer wins when the same query also needs local docs, exact versions, offline use, or token-aware context.

## Scope

### 1. Source Hygiene Gate

Default web ingest should avoid obvious duplicate language mirrors when the seed URL points to an English docs root.

Rules:

- prefer canonical English paths such as `/docs/` for Docusaurus-like sites;
- exclude locale prefixes by default when the source has a clear English canonical path;
- keep multilingual ingest as explicit opt-in;
- store enough metadata to report excluded path counts.

Initial excluded path examples from Riverpod:

- `/ar/`
- `/bn/`
- `/de/`
- `/es/`
- `/fr/`
- `/it/`
- `/ja/`
- `/ko/`
- `/ru/`
- `/tr/`
- `/zh-Hans/`

Verification:

- indexing `https://riverpod.dev` no longer puts translated pages in default top 5;
- source health report shows how many locale pages were skipped;
- explicit multilingual config can still ingest selected locales.

### 2. Top-K Diversity Rerank

After initial retrieval, apply a deterministic diversity pass before packing.

Default policy:

- retrieve a larger candidate pool, for example top 30;
- keep at most 1 or 2 sections per source page in the first 5 results;
- prefer unique canonical URLs when scores are close;
- allow repeated sections only when no other relevant source is available;
- keep page expansion behavior unchanged when the user explicitly asks for expanded context.

Verification:

- Riverpod queries no longer return 3 to 5 sections from the same `auto_dispose`, `family`, or migration page when other relevant pages exist;
- eval reports `unique_sources_at_5`;
- eval reports `context_pack_redundancy_rate`.

### 3. Intent Bias For Basic vs Advanced Queries

Add small deterministic ranking signals based on page path/title/query shape.

For basic usage queries, prefer:

- `/tutorial/`
- `/docs/`
- `/guide/`
- `/concepts/`
- `/reference/`
- pages with titles like `Getting started`, `Dependencies`, `Testing`, `Providers`, `Refs`.

For advanced queries, allow advanced pages to rank higher when the query contains matching terms:

- `yield`
- `lifespan`
- `migration`
- `advanced`
- `generator`
- `annotation`
- `override`
- `lifecycle`

This directly targets the FastAPI finding where `dependencies-with-yield` outranked the canonical basic dependencies tutorial for basic `Depends` queries.

Verification:

- `fastapi_depends_basic` ranks `tutorial/dependencies` before `dependencies-with-yield`;
- `fastapi_http_exception` ranks `reference/exceptions` or `tutorial/handling-errors` before unrelated advanced dependency pages;
- advanced queries still rank advanced pages when the advanced term is explicit.

### 4. Snippet-First Evidence Extraction

During packing, mark code blocks and short API examples as first-class evidence.

Minimal implementation:

- extract fenced code blocks from selected sections;
- attach snippet metadata to the packed result;
- prefer sections with matching code snippets when query asks for example, usage, test, import, signature, or code;
- keep prose context around the snippet for attribution.

Verification:

- FastAPI `TestClient` query returns import/client/assert example prominently;
- Riverpod `family FutureProvider` query returns a usable provider example;
- eval can score `snippet_present` for code-example queries.

## Non-Goals

- Do not add an LLM reranker.
- Do not build a hosted query service.
- Do not rewrite the full retrieval pipeline.
- Do not make multilingual docs impossible.
- Do not solve exact-version Dartdoc ingestion in this lane; that remains a separate product wedge.

## PR Sequence

### PR 1 — Corpus Hygiene Defaults

Implement default locale/path filtering for Docusaurus-like web docs.

Expected result:

- Riverpod default ingest excludes translated mirrors;
- source health exposes skipped locale/path counts;
- explicit config can opt into multilingual docs.

### PR 2 — Diversity-Aware Packing

Add `max_sections_per_source` and unique-source-aware top-K selection.

Expected result:

- top 5 results contain broader evidence;
- repeated sections from the same page are capped unless expansion is requested;
- eval emits `unique_sources_at_5` and redundancy metrics.

### PR 3 — Intent-Sensitive Rerank Signals

Add lightweight path/title/query heuristics for basic vs advanced pages.

Expected result:

- simple tutorial/reference queries rank canonical pages first more often;
- advanced pages still win for advanced queries;
- FastAPI mini-benchmark improves canonical-source Hit@1.

### PR 4 — Snippet Evidence MVP

Expose code blocks as snippet evidence in context packs.

Expected result:

- code-example queries return directly usable examples;
- eval can score snippet presence;
- Context7's snippet presentation advantage becomes smaller.

Current status:

- indexed sections now carry `code_snippets` and `has_code_snippet` metadata for fenced code blocks and conservative code-like flattened examples;
- eval emits per-item `snippet_presence`, per-result `has_code_snippet`, and aggregate `snippet_present_at_5_rate` / `snippet_sections_at_5_avg`;
- FastAPI and Riverpod saved snapshots both report `snippet_present_at_5_rate: 1.0`.

### PR 5 — Public Docs Quality Eval Gate

Create a small repeatable eval suite covering Riverpod and FastAPI.

Expected result:

- saved Docmancer artifacts;
- saved Context7 snapshots where possible;
- metrics for Hit@K, MRR, canonical-source Hit@1, unique sources, locale contamination, snippet presence, and latency;
- soft gate prevents regression on the public-doc quality lane.

## Success Criteria

Riverpod target:

- Hit@5: `0.8 -> 1.0`;
- no translated pages in default top 5;
- `rp_ref_watch_listen` includes the canonical refs page in top 5;
- top 5 has at least 3 unique sources when relevant sources exist.

Current status:

- saved snapshot: `eval/results/docmancer_riverpod_results.json`;
- Hit@1/Hit@5/MRR: `1.0`;
- locale contamination rate: `0.0`;
- snippet present@5 rate: `1.0`;
- `rp_ref_watch_listen` ranks `https://riverpod.dev/docs/concepts2/refs` at rank 1.

FastAPI target:

- fact-level Hit@5 remains `3/3`;
- canonical-source Hit@1 improves from `1/3` to at least `2/3`;
- `fastapi_depends_basic` ranks the basic dependencies tutorial above `dependencies-with-yield`;
- `fastapi_testclient` returns a directly usable `TestClient` snippet.

Current status:

- golden dataset: `eval/fastapi_golden.yaml`;
- saved snapshot: `eval/results/docmancer_fastapi_results.json`;
- Hit@1/Hit@5/MRR: `1.0` on the 3-query FastAPI suite;
- snippet present@5 rate: `1.0`;
- `fastapi_depends_basic`, `fastapi_http_exception`, and `fastapi_testclient` all rank canonical tutorial/error/testing pages first.

Product target:

- Docmancer becomes competitive for warm public-doc lookup;
- Docmancer's stronger local/project/version-aware positioning remains unchanged;
- benchmark reports explain quality gains with deterministic metrics, not manual impressions.

## Open Questions

- Should locale filtering be configured globally, per source, or both?
- Should `max_sections_per_source` default to 1 or 2 for compact packs?
- Should snippet extraction happen at ingest time or pack time?
- Should intent bias be part of retrieval scoring, fusion, or only final rerank?

## First Implementation Slice

The smallest useful slice is PR 1 plus PR 2:

1. Add default locale filtering for `riverpod.dev`-style Docusaurus docs.
2. Add `max_sections_per_source=2` for compact query results.
3. Rerun the Riverpod golden eval.
4. Confirm `rp_ref_watch_listen` reaches Hit@5 and top-K locale contamination becomes zero.

This gives a fast, visible benchmark improvement without touching exact-version ingestion or major architecture.

## Expanded Context7 Gap Closure Plan

This section expands the tactical quality lane into a broader roadmap for closing the observed quality gap with Context7 while preserving Docmancer's local/offline/project-aware positioning.

### Short Summary

Docmancer is a local RAG engine for coding agents, focused on version-aware documentation retrieval. It wraps hybrid search over locally indexed docs:

- lexical search through SQLite FTS5;
- dense and sparse embeddings through FastEmbed/SPLADE-backed vector search;
- result fusion through Reciprocal Rank Fusion;
- compact context packs with source attribution.

Unlike Context7, which serves centrally hosted documentation corpora, Docmancer keeps indexes, embeddings, and source metadata locally. Its output is not just a snippet list; it is a source-grounded context pack that a coding agent can use to answer or modify code with verifiable references.

The first Riverpod and FastAPI comparisons show that Docmancer is close to Context7 on retrieval usefulness, but its public-docs output is noisier. The main gaps are corpus hygiene, duplicate top-K sections, snippet presentation, shallow eval metrics, and not-yet-proven exact-version retrieval from project lockfiles.

The intended outcome is a higher-quality North Star:

- target exact-version/source relevance above 95% for narrow known-version tasks;
- at least 3 unique useful sources in top 5 where multiple relevant sources exist;
- near-zero locale contamination and forbidden-version leakage;
- token savings remain strong, with a floor of at least 35% reduction versus raw docs context;
- all claims are backed by repeatable benchmark suites A–E.

### Gap Analysis Against Context7

#### 1. Corpus Hygiene

Many documentation sites, especially Docusaurus sites, publish translated mirrors such as `/ru/`, `/zh-Hans/`, `/es/`, and similar locale prefixes. Context7 appears to serve a cleaner hosted corpus. Docmancer's default web ingest currently crawls too broadly, which lets non-target-language pages pollute top-K results.

Observed Riverpod issue:

- many translated pages were indexed;
- the `rp_ref_watch_listen` query missed the expected canonical refs page in top 5;
- translated/latest/migration pages consumed valuable result slots.

Required behavior:

- default to canonical/source-language pages when the seed URL is clearly an English docs root;
- support opt-in multilingual indexing;
- report skipped locale/path counts in source health.

#### 2. Canonical URL Handling

Many docs pages are duplicated across paths, query params, host aliases, or language mirrors. The HTML tag `<link rel="canonical" href="...">` identifies the preferred URL for duplicate content.

Required behavior:

- parse canonical links during web ingest;
- normalize source URLs to canonical URLs where safe;
- avoid indexing duplicate non-canonical pages by default;
- keep enough trace metadata to explain canonical redirects/skips.

Canonical handling should run before final locale/path decisions, because a non-canonical URL may point to an allowed canonical page.

#### 3. Top-K Redundancy

Docmancer can return several adjacent sections from the same page, for example repeated Riverpod `auto_dispose`, `family`, or migration sections. This is useful when the user asks for page expansion, but wasteful in compact top-K answers.

Required behavior:

- compact packs should diversify by source page;
- page expansion should remain available when requested;
- eval should measure redundancy directly.

#### 4. Snippet Clarity

Context7 surfaces code examples cleanly. Docmancer currently returns code embedded inside broader sections, which can be harder for coding agents to consume.

Required behavior:

- extract fenced Markdown code blocks and HTML `<pre>`/`<code>` blocks;
- attach snippet metadata to the parent section;
- later consider indexing snippets as independent retrievable units;
- boost snippets for example/code/import/signature/test queries.

#### 5. Evaluation Depth

Current eval is too close to simple Hit@K. It does not fully measure source diversity, locale contamination, forbidden versions, snippet usefulness, or degraded retrieval modes.

Required behavior:

- log per-query retrieval and packing metrics;
- persist Docmancer and Context7 snapshots where possible;
- score required facts and forbidden sources/versions;
- expose quality regressions in CI soft gates.

#### 6. Exact-Version Retrieval

Docmancer's strongest differentiation is project-aware exact-version docs. This is not yet proven by the current Riverpod/FastAPI public-docs comparisons.

Required behavior:

- read exact dependency versions from `pubspec.lock` and `Cargo.lock`;
- generate versioned docs targets, for example pub.dev Dartdoc and docs.rs;
- store version metadata on each source;
- filter or flag forbidden-version results;
- combine project docs and dependency docs in one query flow.

### Prioritized Technical Roadmap

| Phase | Focus | Main tasks | Effort | Main risks |
|---|---|---|---|---|
| Phase 0 | Baseline freeze | Persist current Riverpod/FastAPI snapshots, record existing metrics, define eval schema | Low | Baseline remains partially manual if Context7 snapshots are incomplete |
| Phase 1, 0–2 weeks | Index hygiene | Locale filtering, canonical URLs, path-prefix controls, `max_sections_per_source=2`, simple source penalty | Low/medium | False filtering of useful pages |
| Phase 2, 2–6 weeks | Ranking and snippets | MMR rerank, intent-sensitive boosts, code-block extraction metadata, snippet boosting, RRF weight tuning | Medium | Over-tuning, relevance drops from excessive diversity |
| Phase 3, 6–12 weeks | Exact version and eval | `pubspec.lock`/`Cargo.lock` parsing, pub.dev/docs.rs target generation, forbidden-version detection, expanded eval metrics | High | Registry/doc hosting quirks, network availability, version URL edge cases |
| Phase 4, 3–6 months | Product quality and UX | Cross-index project+library retrieval, MCP explainability, opt-in prefetch, degraded-mode logging, benchmark automation | Medium/high | UX complexity, external dependency instability |

### PR Sequence

| PR | Task | Complexity | Risk |
|---:|---|---|---|
| 1 | Add canonical URL extraction and normalization | Low | Incomplete support for unusual HTML/canonical patterns |
| 2 | Add locale/path-prefix filtering defaults | Low | False negatives on relevant translated or non-standard docs |
| 3 | Add `max_sections_per_source=2` and source repetition penalty | Medium | May hide useful adjacent sections unless expansion is explicit |
| 4 | Add MMR rerank over a larger candidate pool | Medium | Requires tuning candidate count and lambda |
| 5 | Add generic intent-aware rerank signals | Medium | Brittle rules if too package-specific |
| 6 | Add snippet extraction metadata for Markdown/HTML code blocks | Medium/high | Parser edge cases and noisy snippets |
| 7 | Add exact-version target generation from `pubspec.lock` | High | Dartdoc root/index and package-specific page quirks |
| 8 | Add exact-version target generation from `Cargo.lock` | High | docs.rs availability and feature/platform docs differences |
| 9 | Add cross-index RRF for project docs + dependency docs | High | Harder ranking/eval across source classes |
| 10 | Add forbidden-version detection in eval and query traces | Medium | Requires reliable version metadata extraction |
| 11 | Add expanded eval logging: diversity, redundancy, contamination, tokens | Medium | Schema churn and benchmark maintenance |
| 12 | Add MCP/CLI explainability and degraded-mode UX | Medium | Too much output can hurt agent UX |

### Benchmark Suites A–E

| Suite | Goal | Fixtures | Success metrics |
|---|---|---|---|
| Suite A — Public Docs | Public-docs parity with Context7 | Riverpod, FastAPI, React-like public docs | Hit@5 >= 0.95 on target set; canonical-source Hit@1 improves; unique_sources@5 >= 3 where applicable; p50 warm latency tracked |
| Suite B — Exact Version | Retrieve docs for the exact project dependency version | Mini Flutter/Dart and Rust projects with lockfiles | exact-version Hit@5 >= 0.95; forbidden-version rate = 0 for strict queries |
| Suite C — Project + Libraries | Combine local project docs and dependency docs | Repo fixture with README/docs/ADR plus dependencies | at least one project source when project docs answer the query; Hit@K >= 0.90; correct source-class ordering |
| Suite D — Coding Agent | End-to-end agent usefulness | Tasks such as FastAPI auth/test flow or Riverpod provider migration | task success/code correctness improves over baseline; snippet_present@3 high for code tasks |
| Suite E — Operational | Reliability and UX | offline mode, no vectors, degraded embeddings, explain CLI/MCP | no crashes; degraded mode explicitly reported; p95 warm latency stays acceptable |

Metrics to compute for each benchmark item:

- Precision@K, Recall@K, Hit@K, MRR;
- canonical-source Hit@1/Hit@5 where a canonical source is known;
- `unique_sources@K`;
- `redundancy_rate`;
- `locale_contamination_rate`;
- `forbidden_version_rate`;
- `snippet_present@K` for code-example tasks;
- `token_raw`, `token_pack`, and savings percent;
- warm/cold latency;
- selected retrieval mode and degraded-mode state.

### Technical Specifications

#### Locale Filtering

Implement URL/path language detection before indexing final sections.

Signals:

- path prefixes such as `/ru/`, `/ja/`, `/zh-Hans/`;
- query params such as `?lang=...` where common;
- HTML language hints such as `<html lang="...">`;
- Docusaurus i18n path conventions.

Default policy:

- if seed is an English/root docs site, exclude locale mirrors by default;
- allow explicit include/exclude path configuration;
- expose skipped counts in source health.

#### Canonical URL Normalization

For each fetched HTML page:

1. parse `<link rel="canonical" href="...">`;
2. normalize host variants and trailing slashes consistently;
3. use the canonical URL as the source identity where safe;
4. skip duplicate non-canonical pages unless explicitly configured;
5. log canonical mapping decisions for `--explain-json` or source health.

#### `max_sections_per_source`

Compact context packs should default to:

```text
max_sections_per_source = 2
```

Selection policy:

- retrieve a larger candidate pool than the final K;
- select highest-scoring candidates while enforcing source caps;
- allow more sections from the same source when `--expand` or page-level context is requested.

#### MMR Rerank

Apply Maximal Marginal Relevance over the candidate pool after initial retrieval/fusion.

Recommended formula:

```text
score = lambda * normalized_relevance
        - (1 - lambda) * max_similarity_to_selected
```

Initial values:

- start with `lambda = 0.5` for benchmark experiments;
- consider `lambda = 0.65` if relevance drops too much;
- only enable by default after eval shows pack/task improvement, not just prettier diversity.

#### Source Penalty

As a simpler deterministic guard, apply a score penalty for repeated sections from the same canonical source:

```text
score_new = score_old * pow(source_repeat_penalty, repeat_count)
```

Possible default:

```text
source_repeat_penalty = 0.5
```

This can run before or alongside MMR.

#### Intent-Sensitive Ranking

Start with generic intent classes, not package-specific hardcoding.

Candidate classes:

- `code_example`;
- `exact_api`;
- `basic_tutorial`;
- `advanced_lifecycle`;
- `migration`;
- `error_message`;
- `version_specific`.

Example boosts:

- `basic_tutorial`: boost `/tutorial/`, `/guide/`, `/docs/`, `/concepts/`; demote `/advanced/`, `/migration/`, `/internals/` unless explicitly requested;
- `exact_api`: boost `/api/`, `/reference/`, symbol names, signatures, snippets;
- `migration`: boost `migration`, `changelog`, `whats-new`, versioned release pages;
- `code_example`: boost sections/snippets with code blocks and imports.

#### Snippet Extraction

MVP design:

```text
section {
  section_id,
  source_url,
  heading_path,
  text,
  code_blocks: [
    {
      language,
      code,
      surrounding_text,
      detected_symbols
    }
  ]
}
```

Later design:

```text
snippet {
  snippet_id,
  parent_section_id,
  source_url,
  heading_path,
  language,
  code,
  detected_symbols,
  token_count
}
```

MVP should avoid mandatory LLM-generated snippet captions to preserve local/offline defaults.

#### Exact-Version From Lockfiles

Pub/Dart/Flutter:

- parse `pubspec.lock`;
- extract package/version pairs;
- generate versioned Dartdoc targets such as `https://pub.dev/documentation/<package>/<version>/`;
- prefer concrete class/library pages as seed URLs for Dartdoc-style sites, especially for key packages;
- store `ecosystem=pub`, `library`, `version`, and `version_source=project_lockfile_exact`.

Rust/Cargo:

- parse `Cargo.lock`;
- extract crate/version pairs;
- generate docs.rs targets such as `https://docs.rs/<crate>/<version>/`;
- store `ecosystem=cargo`, `library`, `version`, and lockfile metadata.

Important policy:

- auto-detect dependencies freely;
- network prefetch should be opt-in or explicitly user-approved;
- avoid silent network fetching in privacy-sensitive/offline workflows.

#### Cross-Index RRF

For project-aware queries, retrieve from multiple source classes:

- project-owned docs;
- dependency docs;
- registered public docs;
- exact-version package docs.

Then fuse with source-class-aware RRF.

Expected behavior:

- project docs win when they directly answer local conventions;
- library docs fill in API details;
- explain output shows which source class contributed each result.

#### Forbidden-Version Detection

Eval and query traces should identify results from versions that conflict with the requested/project version.

Behavior:

- in strict exact-version benchmark mode, forbidden-version results fail the item;
- in normal query mode, conflicting versions should be demoted or warned about;
- query output should include source version when known.

#### Degraded-Mode Logging

Do not silently claim hybrid retrieval if dense/sparse/vector components failed.

Required fields:

- requested mode;
- actual mode;
- component failures;
- fallback reason;
- timing by component.

Examples:

```text
mode=hybrid/dense_only_degraded
mode=fts5_only_no_vectors
mode=hybrid/sparse_unavailable
```

### Context Pack and Eval Log Schema

#### Context Pack Result Fields

Each returned result should expose or internally track:

- `source_url`;
- `canonical_url`;
- `document_title`;
- `section_heading`;
- `heading_path`;
- `section_text`;
- `token_count`;
- `source_class`;
- `ecosystem`;
- `library`;
- `version`;
- `snippet_blocks` where available;
- `explain` signal contributions where requested.

#### Eval Query Log Fields

Each benchmark item should log:

- `query_id`;
- `query_text`;
- `expected_sources`;
- `required_facts`;
- `forbidden_sources`;
- `forbidden_versions`;
- `returned_urls`;
- `returned_versions`;
- `hit_at_k`;
- `mrr_at_k`;
- `unique_sources_at_k`;
- `redundancy_rate`;
- `locale_contamination_rate`;
- `forbidden_version_rate`;
- `snippet_present_at_k`;
- `token_raw`;
- `token_pack`;
- `savings_percent`;
- `signals_scores` such as lexical/dense/sparse/RRF/MMR;
- `selected_diversity_lambda`;
- `requested_mode`;
- `actual_mode`;
- `degraded_reason`;
- latency by component.

### Tests and Automation

#### Unit and Integration Tests

Required coverage:

- URL locale filtering with representative paths;
- canonical URL extraction and duplicate suppression;
- Docusaurus i18n fixture;
- snippet extraction from Markdown and HTML;
- `max_sections_per_source` selection behavior;
- MMR ranking over a tiny synthetic candidate set;
- source penalty behavior;
- intent classification and boost application;
- `pubspec.lock` parsing and target generation;
- `Cargo.lock` parsing and target generation;
- forbidden-version scoring;
- degraded-mode trace population;
- eval metric formulas.

#### Benchmark Automation

Build scripts that:

1. prepare or reuse fixture docs;
2. run ingest/prefetch;
3. execute golden queries;
4. collect Docmancer JSON artifacts;
5. collect Context7 snapshots where possible;
6. compute metrics;
7. compare against baseline thresholds;
8. emit markdown and machine-readable reports.

Start with soft CI gates, then harden only after baselines stabilize.

### MCP and CLI UX

#### First-Run Smart Suggestions

Project inspection may suggest docs to index based on lockfiles/manifests, but should not silently fetch network docs.

Preferred flow:

```text
inspect_project_docs -> suggests dependency docs
prefetch_project_docs -> requires confirmation or explicit user call
```

#### Prefetch Simulation

The MCP server can estimate likely docs needs and present prefetch recommendations. Background fetching should be opt-in.

Examples:

- “This project uses `fastapi==X`; prefetch FastAPI docs?”
- “This Flutter project uses `flutter_riverpod 2.6.1`; prefetch exact Dartdoc pages?”

#### Explainability

Improve `docmancer query --explain` and MCP explain output with:

- source/version used;
- retrieval mode and degraded state;
- lexical/dense/sparse/RRF/MMR contributions;
- source-class information;
- snippets selected;
- warnings for stale or conflicting versions.

Avoid overly verbose default output. Keep detailed traces behind `--explain-json` or explicit MCP fields.

### Risks and Anti-Goals

#### Risks

- locale/canonical filtering may skip relevant non-English or alternate docs;
- exact-version docs hosts may be unavailable or have inconsistent URL structures;
- MMR/diversity may reduce first-result relevance if over-weighted;
- snippet extraction can create noisy standalone fragments without enough context;
- expanded eval schema can become expensive to maintain;
- automatic network fetching can conflict with privacy/offline expectations.

#### Dependencies

- Qdrant local vector storage;
- SQLite FTS5;
- FastEmbed/SPLADE model availability;
- pub.dev and docs.rs URL/documentation availability;
- MCP client behavior and permission model.

#### Anti-Goals

- do not clone Context7's hosted model;
- do not require external APIs by default;
- do not rewrite the whole retrieval engine before measuring smaller fixes;
- do not make LLM reranking mandatory;
- do not increase token cost enough to erase context-pack savings;
- do not silently fetch network docs in privacy-sensitive flows.

### Current vs Target Metrics

| Metric | Baseline | Current | Target | Status |
|---|---:|---:|---:|---|
| Riverpod Hit@1 | 0.80 | 1.00 | >=0.95 | Met |
| Riverpod Hit@5 | 0.80 | 1.00 | >=0.95 | Met |
| Riverpod MRR | 0.80 | 1.00 | >=0.95 | Met |
| Riverpod locale contamination | observed | 0.00 | 0.00 | Met |
| Riverpod snippet present@5 | not measured | 1.00 | track | Met for current suite |
| FastAPI Hit@1 | 1/3 canonical-source | 1.00 | >=2/3 initially | Met |
| FastAPI Hit@5 | 3/3 fact-level | 1.00 | keep 3/3 | Met |
| FastAPI MRR | not measured | 1.00 | >=0.95 | Met |
| FastAPI snippet present@5 | not measured | 1.00 | track | Met for current suite |
| Forbidden-version rate | not measured | not measured | 0 for strict exact-version suite | Not started |
| Token savings | strong in sample | not regressed by this lane | >=35% floor | Needs gate |
| Warm p50 latency | ~1100ms Riverpod | tracked in artifacts | track first | Needs gate |

Saved artifacts:

- Riverpod: `eval/results/docmancer_riverpod_results.json`;
- FastAPI: `eval/results/docmancer_fastapi_results.json`.

### Completed Implementation Slice

The public-docs quality slice is implemented far enough to close the observed Riverpod and FastAPI gaps for the current benchmark fixtures.

Completed changes:

1. canonical URL extraction resolves relative canonical URLs and uses in-scope canonical URLs as source identity;
2. duplicate canonical pages are skipped during web ingest;
3. compact retrieval defaults to `max_sections_per_source = 2`;
4. compact retrieval overfetches and caps repeated canonical sources;
5. explicit `adjacent` and `page` expansion bypass source caps;
6. eval quality metrics use canonical sources where available;
7. eval reports source diversity, locale contamination, and snippet presence;
8. URL `update` removes the existing URL docset before re-adding, preventing stale vectors/pages from surviving changed filters;
9. dense-only hybrid collections skip unavailable sparse search instead of emitting a Qdrant sparse-vector error;
10. Riverpod API-term intent handling extracts terms such as `ref.watch` and `ref.listen`, appends lexical matches, and reranks matching docs/concepts/reference pages;
11. FastAPI intent handling prefers tutorial/reference/testing pages for basic queries and demotes advanced/yield pages unless explicitly requested;
12. indexed sections carry `code_snippets` and `has_code_snippet` metadata for fenced code blocks and conservative flattened examples;
13. local HTML cleaning preserves `<pre><code>` blocks as fenced Markdown before section indexing.

Verification completed:

- `uv run pytest tests/test_retrieval_features.py`: `17 passed`;
- `uv run pytest tests/test_eval.py tests/test_html_utils.py tests/test_extraction.py`: `54 passed`;
- `uv run pytest tests/test_eval.py tests/test_html_utils.py tests/test_extraction.py tests/test_retrieval_features.py tests/test_cli.py tests/test_config.py tests/test_web_fetcher.py`: `124 passed, 1 warning`;
- full suite: `631 passed, 1 skipped, 9 warnings`.

### Remaining Work

The remaining work is no longer about closing the first public-doc lookup gap. It is about turning the current slice into a durable benchmark and extending Docmancer into its stronger exact-version/project-aware wedge.

Next sequence:

1. add a soft regression gate over saved Docmancer artifacts for Riverpod/FastAPI metrics and snippet fields;
2. persist Context7 outputs as machine-readable snapshots for Suite A instead of relying on manual comparison notes;
3. grade Docmancer and Context7 snapshots with the same schema;
4. add snippet-aware ranking so code-example queries prefer sections with relevant `has_code_snippet` evidence, not just detect snippets after retrieval;
5. start exact-version Pub/Dartdoc benchmark from `pubspec.lock`, using concrete class/API seed pages for key packages;
6. add Cargo/docs.rs exact-version benchmark from `Cargo.lock`;
7. add forbidden-version scoring and query trace warnings;
8. build cross-index retrieval for project docs plus dependency docs;
9. improve MCP/CLI explainability for source class, version, degraded mode, and selected snippets;
10. decide whether to align Qdrant client/server versions or suppress the compatibility warning in controlled local test runs.

Deferred or intentionally not implemented in this lane:

- mandatory LLM reranking;
- hosted query service behavior;
- automatic network prefetch from project inspection without user approval;
- exact-version Dartdoc/docs.rs ingestion;
- full MMR rollout by default.

### Final State

This lane should now be treated as completed for the current Riverpod/FastAPI public-docs quality objective.

The next PR should either:

1. package the completed implementation and docs as a reviewable public-doc quality PR;
2. add the soft regression gate for the saved artifacts;
3. start a separate exact-version benchmark PR.

Do not mix exact-version ingestion work into the same PR unless the public-doc quality changes have already been reviewed.
