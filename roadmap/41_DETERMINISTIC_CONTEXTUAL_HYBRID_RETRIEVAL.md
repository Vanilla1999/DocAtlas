# Task 41 — deterministic contextual hybrid retrieval

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
