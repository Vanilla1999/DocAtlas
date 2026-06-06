# 09 — Riverpod Context7 Benchmark Follow-ups

## Context

The first Riverpod RiverEval compared Context7 (`/websites/riverpod_dev`) with Docmancer indexing `https://riverpod.dev` locally.

Artifacts:

- `eval/riverpod_golden.yaml` — 5 Riverpod queries based on `nbo` dependencies (`flutter_riverpod`, `hooks_riverpod`, `riverpod_annotation`, `riverpod_generator`).
- `eval/results/docmancer_riverpod_results.json` — Docmancer retrieval eval output.
- `eval/riverpod_benchmark_report.md` — manual Context7 vs Docmancer comparison.

Baseline:

| Metric | Docmancer | Context7 |
|---|---:|---:|
| Hit@1 | 0.8 | 1.0 manual |
| Hit@5 | 0.8 | 1.0 manual |
| MRR | 0.8 | 1.0 manual |
| p50 latency | ~1101ms | ~2s manual |
| p95 latency | ~1625ms | ~2s manual |

Interpretation:

- Docmancer retrieval is already close on public Riverpod guides.
- The current weakness is not the core local-first model; it is source hygiene, top-K diversity, exact-version dependency ingestion, and benchmark observability.
- Context7 wins on no-setup UX, snippet presentation, deduplication, and clean hosted corpus.
- Docmancer should win when project-owned docs and exact project dependency docs are combined.

## Findings

### 1. Locale/translation pollution

Indexing `https://riverpod.dev` pulled many translated copies:

- `ar`, `bn`, `de`, `es`, `fr`, `it`, `ja`, `ko`, `ru`, `tr`, `zh-Hans`.

Observed corpus shape:

- 135 Riverpod sources;
- 1202 sections;
- only ~32 English `/docs/*` sources plus root;
- many top-K results came from translated pages such as `/ru/docs/whats_new`, `/es/docs/whats_new`, `/zh-Hans/docs/migration/from_state_notifier`.

Impact:

- `rp_ref_watch_listen` missed the expected `https://riverpod.dev/docs/concepts2/refs` page in top 5.
- The query returned translated/latest/migration pages instead of the canonical English refs page.

### 2. Top-K lacks source diversity

Docmancer often returns many sections from the same source:

- `auto_dispose` repeated for `rp_provider_lifecycle`;
- `family` repeated for `rp_family_code_example`;
- `from_state_notifier` repeated for `rp_notifier_vs_asyncnotifier`.

This is sometimes useful evidence, but it wastes context slots and makes answers less broad than Context7 snippets.

### 3. Version exactness was not actually exercised

The `nbo` project uses Riverpod 2.6.x, but this benchmark indexed `riverpod.dev` latest/current guides. Results included Riverpod 3.0 pages such as `What's new in Riverpod 3.0`.

The current benchmark therefore does not yet prove Docmancer's strongest claim against Context7: exact project dependency docs.

### 4. Pub Dartdoc root ingest is fragile

`docmancer add https://pub.dev/documentation/riverpod/2.6.1/` failed on the root/index page and recommended concrete Dartdoc seed URLs.

Docmancer already has richer target support (`seed_urls`, `allowed_domains`, `path_prefixes`, Dartdoc seed discovery), but the simple CLI add path does not expose enough control for this use case.

### 5. Hybrid/sparse degradation is under-reported

The eval was run with `mode=hybrid`, but stderr showed sparse retrieval failures:

```text
Wrong input: Vector with name `sparse` is not configured in this collection, available names: dense
```

The JSON item `failures` stayed empty, so the report did not make the degraded retrieval mode visible.

### 6. Eval scoring is too shallow

The golden file contains `required_facts`, but the runner currently scores only expected source matches. It does not check:

- required facts in returned chunks;
- forbidden versions such as Riverpod 3.0 for a 2.6 query;
- token metrics per query;
- unique sources at K;
- translation/locale contamination;
- whether snippets are usable by a coding agent.

### 7. Context7 comparison is manual

Context7 outputs were assessed manually. The next benchmark should persist Context7 snapshots and grade them with the same rubric as Docmancer.

## PR sequence

### PR 1 — Clean Docusaurus ingest / locale filtering

Goal: prevent translated copies from polluting the default corpus.

Scope:

- Add path/locale filtering for web/Docusaurus ingest.
- Prefer canonical English paths (`/docs/*`) when the seed is an English docs root.
- Add CLI parity for existing target capabilities, for example:
  - `docmancer add https://riverpod.dev --path-prefix /docs/`;
  - `--exclude-path /ar/ --exclude-path /ru/ ...`;
  - or manifest-only support if CLI flags are deferred.
- Keep explicit opt-in for multilingual docs.

Tests:

- Docusaurus fixture with `/docs`, `/ru/docs`, `/zh-Hans/docs`.
- Default ingest excludes locale mirrors.
- Explicit include can ingest non-English locales.

Success metric:

- Riverpod RiverEval `rp_ref_watch_listen` becomes Hit@5 without changing the query.

### PR 2 — Source diversity / MMR top-K policy

Goal: avoid filling top-K with many sections from one page.

Scope:

- Add `max_sections_per_source` to query/pack defaults.
- Add optional MMR-style rerank after retrieval/fusion.
- Preserve adjacent-section expansion when the user explicitly asks for page-level context.

Tests:

- Query over a fixture where one page has many near-duplicates and another page has required evidence.
- Top-5 includes at least N unique sources when possible.

Metrics:

- `unique_sources_at_5`.
- `context_pack_redundancy_rate`.

### PR 3 — Exact Pub Dartdoc package docs for project dependencies

Goal: make Docmancer actually win on project-version exactness.

Scope:

- Use project metadata/lockfiles to prefetch exact Pub package versions.
- For Riverpod-like packages, index concrete Dartdoc library/class pages instead of root pages only.
- Store metadata:

```json
{
  "library": "riverpod",
  "ecosystem": "pub",
  "version": "2.6.1",
  "version_source": "project_lockfile_exact",
  "source_type": "pub_dartdoc"
}
```

Candidate packages from `nbo`:

- `flutter_riverpod` 2.6.1;
- `hooks_riverpod` 2.6.1;
- `riverpod_annotation` 2.6.1;
- `riverpod_generator` 2.6.3;
- core `riverpod` if resolved transitively in `pubspec.lock`.

Initial class/library seed pages:

- `Provider`;
- `FutureProvider`;
- `StreamProvider`;
- `Notifier`;
- `AsyncNotifier`;
- `Ref`;
- `WidgetRef`;
- `ConsumerWidget`;
- `ConsumerStatefulWidget`.

Tests:

- `project-version` resolves from `pubspec.lock`.
- Query for Riverpod 2.6 does not return Riverpod 3.0 docs when exact docs exist.

### PR 4 — Retrieval degradation observability

Goal: do not silently claim hybrid retrieval when sparse/dense components failed.

Scope:

- Include retrieval component failures in eval JSON.
- Mark degraded mode explicitly, e.g. `hybrid/dense_only_degraded`.
- Avoid sparse queries when collection has no sparse vector configured.
- Add `--allow-degraded=false` test coverage for eval.

Tests:

- Qdrant collection with only dense vectors.
- Sparse retrieval failure appears in `failures`.
- Hard failure when degraded mode is not allowed.

### PR 5 — Eval runner upgrades

Goal: make Riverpod/Context7 comparison meaningful and repeatable.

Scope:

- Score `required_facts` against returned chunks.
- Score `forbidden_versions` / forbidden source matches.
- Emit token metrics per item: `docmancer_tokens`, `raw_tokens`, `savings_percent`, `runway_multiplier`.
- Emit source diversity metrics.
- Add optional locale contamination counters for URL docs.
- Persist Context7 snapshots for the same golden queries and grade them with the same rubric.

Tests:

- Required facts pass/fail.
- Forbidden version/source fail.
- Token metrics present for non-empty results.

## Target outcome

After PRs 1–5, rerun `eval/riverpod_golden.yaml` and update `eval/riverpod_benchmark_report.md`.

Target:

- Docmancer Riverpod Hit@5: `0.8 -> 1.0`;
- no translated pages in default top 5;
- no Riverpod 3.0 pages for project-version 2.6 queries when exact docs are indexed;
- eval JSON reports actual degraded retrieval state;
- report compares Docmancer and Context7 from saved artifacts, not manual notes only.
