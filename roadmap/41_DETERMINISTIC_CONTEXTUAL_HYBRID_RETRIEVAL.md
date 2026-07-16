# Task 41 — deterministic contextual hybrid retrieval

## Implementation status (2026-07-16)

The implementation is intentionally split at the measurement boundary. The
provider-free foundation is implemented on
`agent/task41-deterministic-contextual-hybrid-retrieval`; promotion to a new
default remains blocked on the Task 39 quality gate.

Completed foundation:

- deterministic, bounded contextual prefixes with per-field provenance;
- separate verbatim `display_text`, contextual retrieval text, manifests, and
  content/config hashes;
- additive SQLite generation columns and promoted typed filter fields;
- metadata-only invalidation without changing stable child/vector identity;
- embedding/cache identity bound to chunk and context configuration;
- vector collection names/cache identity bound to retrieval configuration, with
  the selected collection recorded and verified on each SQLite generation;
- deterministic query plans with bounded exact terms and concept queries;
- hard filter propagation to lexical, dense, and sparse lanes;
- stable-child RRF identity with a separate mutable hydration key;
- fixed per-lane/fused candidate ceilings and query/fusion trace hashes;
- explicit strict failure or opt-in lexical degraded mode when vector
  capabilities are missing or incompatible.

Still gated, not silently treated as complete:

- Task 39 ablations and the Task 41 acceptance report;
- measured removal/replacement of compatibility intent rules;
- a separate sparse-capable configuration run;
- optional local reranker implementation, which starts only if the measured
  contextual lexical+dense result leaves a justified quality gap;
- immutable vector collection copy/rebuild and atomic activation per corpus
  revision (config-compatible incremental generations currently reuse the
  verified collection so delete-only updates cannot activate an empty copy);
- changing the default retrieval mode from lexical.

No benchmark/model run is required to build or test the foundation. Context is
computed offline from source-owned metadata; it increases only index-time input,
not model-visible evidence. Task 42 remains the sole owner of evidence selection
and the prompt token ceiling.

## Ordered delivery slices

### 41A — contracts and contextual generation

1. Freeze `ContextConfig`, context manifest, query/candidate contracts, schema
   versions, and canonical hash encoding.
2. Build prefixes only from allow-listed source metadata, heading ancestry, and
   symbols extracted from the verbatim child span.
3. Strip URL credentials/query strings and machine-specific absolute roots.
4. Store the prefix, provenance manifest, schema/config/content hashes, and
   embedding-input hash separately from `display_text`.
5. Promote project/library/version/scope/authority fields into typed columns;
   retain JSON metadata for compatibility.
6. Validate byte/token bounds, manifest hashes, promoted-column parity, source
   spans, and FTS parity before generation activation.
7. Prove that a metadata-only edit keeps stable child/vector IDs while changing
   derived retrieval and embedding hashes.

### 41B — deterministic query plan and lexical lane

1. Extract no more than 12 exact terms from quoted strings, flags, config keys,
   error codes, API symbols, and paths.
2. Produce at most three normalized concept queries without an LLM rewriter.
3. Convert caller/host filters into a typed `FilterSpec`; never infer exact
   versions from the word `latest`.
4. Apply the same hard filters before lexical, dense, and sparse candidate
   collection.
5. Use explicit FTS column weights and preserve punctuation-bearing exact terms
   through the exact-term supplemental path.
6. Persist only query-plan/config hashes in normal traces; do not duplicate raw
   evidence or the full raw query.

### 41C — stable hybrid fusion and capability truth

1. Cap each lane at 40 candidates and the deduplicated fused pool at 60.
2. Fuse by `stable_chunk_id`; translate to integer `hydration_id` only after
   ranking.
3. Bind every vector collection to provider/model/dimensions and
   contextual/chunk configuration; record its selected identity on the SQLite
   generation.
4. Reject selected-collection or provider/model/dimension mismatches.
5. Require explicit `allow_degraded` for a requested non-lexical mode to fall
   back to lexical; record failures, selected mode, component counts, query-plan
   hash, and fusion-config hash.
6. Keep model-visible evidence limits unchanged.
7. Before claiming full corpus-revision binding, add backend copy/rebuild into a
   candidate collection, validate point parity, and switch it atomically with
   the SQLite generation. Never create a fresh empty collection for a
   delete-only generation.

### 41D — offline ablation and acceptance report

1. Freeze the Task 39 corpus revision and split before tuning.
2. Run lexical baseline, contextual lexical, dense-only, lexical+dense, and the
   sparse-capable configuration where capability proof exists.
3. Record per-case Recall@5, reciprocal rank, required facts, contamination,
   p50/p95 latency, index size/build time, candidate counts, and
   selected/model-visible tokens.
4. Fail on any protected exact symbol/path/error/version regression or forbidden
   contamination increase.
5. Publish wins/losses and classify the result `PASS`, `FAIL`, or `INCONCLUSIVE`;
   missing lanes or incomplete metrics cannot become `PASS`.
6. Only a `PASS` may propose changing the default retrieval mode.

### 41E — optional local reranker experiment

1. Start only if 41D demonstrates a specific unresolved ranking gap.
2. Keep the dependency outside the base install and verify local/offline
   capability before use.
3. Limit input to 40 candidates, cap query+candidate tokens, enforce a hard
   deadline, and return scores only.
4. Compare it as a separate configuration; record model/version/hash and
   latency.
5. Drop the reranker if it does not clear the same quality, contamination,
   latency, and token gates.

## Priority

P1 quality improvement under a fixed model-visible budget. Start after Task 40 provides stable child identities and a measured chunking baseline.

## Problem

DocAtlas already contains lexical, dense, sparse, RRF, and hierarchical retrieval infrastructure, but the behavior is fragmented:

- the safe default is usually lexical unless a user explicitly configures a vector store;
- vector readiness and sparse support vary by installation;
- generic retrieval is followed by domain/path-specific intent rules;
- small child chunks can lose document, version, and heading meaning;
- component scores and configuration identities are not a complete reproducible ranking proof.

Simply enabling embeddings by default would not solve this. Exact symbols, error codes, paths, configuration keys, and pinned versions often favor lexical matching. Conceptual paraphrases favor dense retrieval. The correct design is a bounded hybrid candidate layer with hard authority/version filters and an explicit degraded mode.

## Goal

Within one public DocAtlas call:

```text
deterministic query analysis
→ hard corpus/version/authority filters
→ exact lexical + semantic candidate retrieval
→ rank fusion
→ optional local bounded rerank
→ stable candidate trace
```

Only Task 42 may decide the final evidence set. Task 41 may inspect more candidates internally, but it may not increase model-visible context.

## Deterministic contextual indexing

Anthropic's Contextual Retrieval results support adding chunk-specific context before BM25/embedding, but DocAtlas should not introduce an online LLM indexing dependency by default. Construct a source-owned deterministic prefix from existing metadata:

```text
document title
canonical path or URL
heading path
library and exact version/family
project module/scope
source class and authority
known symbol/API aliases extracted from the cited span
catalog description when explicitly project-owned
```

Requirements:

- prefix size is bounded and versioned;
- every field has provenance;
- prefix is stored separately from verbatim `display_text`;
- prefix is indexed in FTS and embedded with the child;
- prefix is never returned as a source quote unless it occurs in the source;
- prefix/config hash participates in FTS/vector/cache identity;
- changing only contextual metadata invalidates the relevant derived rows.

Do not generate free-form contextual summaries with a remote model in this task. A later experiment may compare them, but deterministic metadata is cheaper, reproducible, offline, and less likely to invent authority.

## Query plan

Build one deterministic plan with bounded internal subqueries:

1. exact identifiers: dotted API names, symbols, paths, quoted strings, flags, config keys, error codes;
2. normalized natural-language concepts after conservative stopword handling;
3. version/library/project filters derived from resolved metadata;
4. request intent and required target/evidence paths from the host-owned task contract where present.

The plan may issue multiple internal searches, but remains one public retrieval operation. Cap the number of subqueries and candidates. Persist the query-plan hash and component counts.

Do not use hidden evaluator fields, oracle patches, post-run outcomes, or an LLM-generated query.

## Lexical lane

1. Keep FTS5 as the always-available offline baseline.
2. Use explicit column weights for title/heading, exact symbol/path fields, contextual metadata, body, and source identity.
3. Preserve exact phrases and punctuation-bearing API identifiers instead of reducing every query to generic word tokens.
4. Add prefix/trigram support only when a measured class such as partial symbol/error matching benefits.
5. Replace library-specific path rules with named generic features where the offline gate supports the replacement.
6. Keep compatibility rules temporarily when removal would regress a protected case; mark them as debt and report their contribution.

## Dense and sparse lanes

1. Dense retrieval is optional and local-first. Reuse the existing FastEmbed/sqlite-vec or managed vector capability when verified.
2. Sparse retrieval runs only when the collection proves it contains the configured sparse representation.
3. Collection identity binds:
   - embedding provider/model/dimensions;
   - sparse model;
   - contextual-prefix schema;
   - chunking schema;
   - corpus/index revision.
4. Missing, stale, mixed, or empty collections produce explicit capability/degraded diagnostics.
5. No cloud embedding or reranking request is allowed by the default path. Remote providers remain explicit user configuration and are measured separately.

## Fusion and reranking

### Rank fusion

- Fuse stable child IDs, not mutable SQLite IDs.
- Use RRF/weighted RRF only with a frozen configuration hash.
- Tune weights on the development set only.
- Report each component rank and final fusion contribution.
- Apply authority, scope, exact-version, and forbidden-source filters before fusion whenever possible; do not hope reranking will demote unsafe evidence.

### Optional local reranker

Add a capability-gated local reranker only after contextual lexical+dense fusion is measured. It must:

- accept at most a fixed candidate count, initially no more than 40;
- cap query+candidate input per item;
- run locally without provider credentials;
- have a hard deadline and explicit fallback;
- return scores only, never summaries or rewritten evidence;
- record model/version/hash and latency;
- remain outside the base install unless size data justifies inclusion.

Compare “no reranker” and “local reranker” as separate configurations. Do not merge it merely because Anthropic observed gains on different corpora.

## Candidate budgets

Suggested starting bounds, to be tuned only by Task 39 metrics:

- lexical candidates: at most 40;
- dense candidates: at most 40;
- sparse candidates: at most 40;
- deduplicated fused pool: at most 60;
- local reranker input: at most 40;
- output to Task 42 selector: at most 20.

These are internal candidates, not prompt chunks. The model-visible source count and token ceilings remain those of Task 36.

## Evaluation and ablations

Run, in order:

1. corrected lexical baseline;
2. lexical + deterministic context;
3. dense-only diagnostic;
4. lexical + dense RRF;
5. lexical + dense + sparse where supported;
6. best hybrid + local reranker;
7. each configuration with capability failure/degraded fallback.

Report quality, contamination, latency, index build/size, candidate counts, selected/model-visible tokens, and per-query wins/losses. A larger candidate pool is not a success unless Task 42 can select a smaller or more accurate final evidence set.

## Acceptance gate

- Exact symbol/path/error/version protected cases never regress from corrected lexical baseline.
- Conceptual/paraphrase holdout Recall@5 or MRR improves without forbidden contamination.
- Required-fact pass rate does not decrease.
- Every vector/sparse result is bound to a verified collection identity.
- Degraded modes are explicit and reproduce the lexical fallback result.
- No remote model/provider is called in default tests or default runtime.
- Candidate traces contain component ranks/config hashes without raw evidence duplication.
- Task 36 model-visible token ceilings remain unchanged.
- Default p95 retrieval latency stays within the predeclared local limit; optional reranker latency is reported separately.
- Full provider-free suite, index rebuild tests, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not automatically make `hybrid` the default before the acceptance gate.
- Do not add an LLM query rewriter.
- Do not put 20 candidates into the prompt.
- Do not use remote reranking to hide weak local retrieval.
- Do not tune on Task 33 hidden outcomes.
- Do not claim that an embedding index alone reduces provider tokens.

## Handoff to the next task

Task 42 receives a bounded, ranked, provenance-rich candidate pool and selects the minimal sufficient evidence bundle under the existing model-visible token ceilings.
