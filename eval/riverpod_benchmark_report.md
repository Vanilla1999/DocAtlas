# Riverpod RiverEval — Context7 vs Docmancer

## Setup

| | Context7 | Docmancer |
|---|---|---|
| **Source** | `/websites/riverpod_dev` (hosted) | `https://riverpod.dev` (locally indexed) |
| **Riverpod version** | latest (riverpod.dev) | latest (riverpod.dev) |
| **Contents** | 402 snippets | 135 pages, 1202 sections |
| **Setup time** | 0s | ~2 min (docmancer add + indexing) |
| **Offline ready** | No | Yes |

## Retrieval Quality Metrics

### Docmancer eval results (formal)

```
Mode:      hybrid
Hit@1:     0.8   (4/5)
Hit@3:     0.8
Hit@5:     0.8
MRR:       0.8
p50:       1101ms
p95:       1625ms
```

### Context7 eval results (manual assessment)

```
All 5 queries returned relevant content at rank 1.
```

## Per-Query Comparison

### 1. rp_provider_lifecycle — autodispose + keepAlive

| | Context7 | Docmancer |
|---|---|---|
| **Hit@5** | ✅ hit | ✅ hit (rank 1) |
| **Relevant chunks** | 3 (auto_dispose, about_code_generation, motivation) | 4 (all from auto_dispose) |
| **Code examples** | 3 snippets | included in sections |
| **Latency** | ~2s | 1625ms |

### 2. rp_family_code_example — family + FutureProvider

| | Context7 | Docmancer |
|---|---|---|
| **Hit@5** | ✅ hit | ✅ hit (rank 1) |
| **Relevant chunks** | 3 (family, about_code_generation) | 4 (all from family) |
| **Code examples** | 3 snippets | included in sections |
| **Latency** | ~2s | 1302ms |

### 3. rp_notifier_vs_asyncnotifier — migration from StateNotifier

| | Context7 | Docmancer |
|---|---|---|
| **Hit@5** | ✅ hit | ✅ hit (rank 1) |
| **Relevant chunks** | 5 (from_state_notifier, from_change_notifier) | 7 (all from from_state_notifier) |
| **Code examples** | 5+ snippets | included in sections |
| **Latency** | ~2s | 1101ms |

### 4. rp_ref_watch_listen — ref.watch vs ref.listen lifecycle

| | Context7 | Docmancer |
|---|---|---|
| **Hit@5** | ✅ hit | ❌ miss |
| **Relevant chunks** | 3 (refs, provider_vs_riverpod) | 0 in top 5 (refs page buried by translation noise) |
| **Code examples** | 2 snippets | not found in top 5 |
| **Latency** | ~2s | 1034ms |

### 5. rp_autodispose_generator — @riverpod annotation with autodispose

| | Context7 | Docmancer |
|---|---|---|
| **Hit@5** | ✅ hit | ✅ hit (rank 1) |
| **Relevant chunks** | 3 (about_code_generation, auto_dispose, getting_started) | 3 (about_code_generation) |
| **Code examples** | 3 snippets | included in sections |
| **Latency** | ~2s | 966ms |

## Token Efficiency (Docmancer native metric)

Docmancer reports token savings per query:

| Query | docmancer tokens | raw tokens | savings % |
|---|---|---|---|
| rp_provider_lifecycle | not measured | not measured | not measured |
| rp_family_code_example | not measured | not measured | not measured |
| rp_notifier_vs_asyncnotifier | not measured | not measured | not measured |
| rp_ref_watch_listen | 1661 | 3049 | **45.5%** |
| rp_autodispose_generator | not measured | not measured | not measured |

(Context7 does not report token metrics)

## Qualitative Assessment

| Aspect | Context7 | Docmancer |
|---|---|---|
| **First-query speed** | ✅ ~2s (no setup) | ❌ ~2min setup + ~1s query |
| **Repeated-query speed** | ✅ ~2s per query | ✅ ~1s per query |
| **Translation noise** | ✅ None (deduplicated) | ❌ zh-Hans, ar, bn, ru, etc. dilute results |
| **Duplicate sections** | ✅ None (deduplicated) | ⚠️ Same page sections repeated (auto_dispose × 4) |
| **Source attribution** | ✅ URL + title | ✅ URL + title + section_id |
| **Code examples** | ✅ Presented clearly | ⚠️ Embedded in text sections |
| **Token efficiency** | ❌ Not reported | ✅ Native metric |
| **Offline capability** | ❌ Requires network | ✅ Full offline after index |

## Key Findings

### Where Context7 wins

1. **No setup** — resolve library ID → query, done. Docmancer needs `docmancer add` + indexing.
2. **Better deduplication** — no translation pages, no repeated sections in results.
3. **Code example clarity** — Context7 extracts code snippets into clearly separated blocks.
4. **Consistent hit rate** — 5/5 queries returned relevant content at rank 1.

### Where Docmancer wins

1. **Lower query latency** — ~1s vs ~2s after indexing.
2. **Token efficiency** — native metric helps agents understand context cost.
3. **Offline readiness** — after initial index, no network needed.
4. **Project-aware** — can read exact version from `pubspec.lock` (not tested here since latest matches).

### Gaps exposed for Docmancer

1. **Translation pollution** — 135 pages indexed but ~60+ are translations (ar, bn, de, es, fr, it, ja, ko, ru, tr, zh-Hans). These add noise and slow down queries.
2. **Section deduplication** — same page repeated with different section_ids inflates result count.
3. **Code example extraction** — Context7's snippets are more readable than raw doc text.
4. **One miss** — rp_ref_watch_listen failed because refs page content didn't rank high enough (translation noise contributed).

## Conclusion for nbo Project

For the `nbo` project (Riverpod 2.6.1):

- **Use Context7** for quick one-off Riverpod API questions — no setup, better examples.
- **Use Docmancer** when you need to combine Riverpod docs with project-owned `ARCHITECTURE.md`, `docs/`, ADRs — this is where Docmancer's project-aware edge over Context7 becomes real.
- **If Docmancer deduplicates translations** (exclude `/*/` paths), the retrieval quality would likely match Context7 while keeping offline + token-efficiency advantages.

## Raw Data

Docmancer eval JSON: `eval/results/docmancer_riverpod_results.json`
