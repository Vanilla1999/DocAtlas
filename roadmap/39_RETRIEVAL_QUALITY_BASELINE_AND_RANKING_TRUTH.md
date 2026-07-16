# Task 39 — retrieval-quality baseline and ranking truth

## Priority

P0 quality precondition. Start only after Tasks 34–38 are reviewed and merged. This task must finish before changing chunking, embeddings, fusion weights, or model-visible token ceilings.

## Why this comes next

Tasks 34–38 establish a compact and measurable delivery boundary. They do not prove that the best evidence is selected. Further compression without a retrieval-quality gate can make a small answer confidently wrong; adding a larger index without the same gate can increase cost while hiding ranking regressions.

The next optimization target is therefore not “fewer tokens at any cost”. It is the Pareto objective:

> return the smallest evidence set that preserves or improves source accuracy, required-fact coverage, version correctness, and downstream usefulness.

This is consistent with Andrej Karpathy's framing of context engineering: construct the context window with the information needed for the next step, including retrieval, tools, state, history, and compaction, rather than treating a longer prompt as inherently better. It is not a recommendation to use embeddings everywhere. For DocAtlas, it means measuring evidence selection before changing the index.

## Current code audit

The following are observations from the current branch and must be converted into tests before being treated as fixed facts.

### 1. FTS5 rerank arithmetic appears reversed

`docmancer/core/sqlite_store.py` retrieves `bm25(sections_fts)` and sorts ascending. SQLite documents that better FTS5 matches receive numerically smaller values. The current rerank then:

- subtracts from the rank to “penalize” long or boilerplate sections;
- adds to the rank to “boost” title, phrase, and action-title matches.

With an ascending lower-is-better score, those operations have the opposite effect. This can reward legal/long sections and demote exact title matches.

Do not patch the signs without a frozen characterization test. First record raw BM25 order, feature contributions, and final order for fixtures containing:

- an exact title match;
- an exact identifier in body text;
- a long generic section;
- a legal/boilerplate distractor;
- a short but irrelevant section;
- equal-score deterministic ties.

Then replace in-place rank mutation with an explicit score model. Prefer one convention throughout, for example:

```text
bm25_cost: lower is better
feature_utility: higher is better
final_utility = normalized_bm25_utility + feature_utility
sort: final_utility descending, stable_id ascending
```

The implementation must never call a lower-is-better value `score` and then mix it with higher-is-better boosts without normalization.

### 2. Existing success evidence is too small and easy to overfit

The checked-in Riverpod and FastAPI reports are useful, but five Riverpod and three FastAPI queries cannot protect a general retriever. `docmancer/retrieval/dispatch.py` contains source-path and topic-specific rules for FastAPI pages. Those rules may be valid compatibility behavior, but they can also make the visible golden set green while unrelated libraries regress.

Task 39 must freeze a provider-free development set and a separate holdout set before changing ranking. The holdout must not be inspected to tune individual rules.

### 3. Current metrics do not fully connect ranking to delivered context

`docmancer/eval/runner.py` already records Hit@K, MRR, required facts, forbidden sources/versions, source diversity, snippet presence, and token metrics. Extend it so one run can trace:

```text
query
→ lexical/dense/sparse candidate IDs and component ranks
→ fusion result
→ deterministic rerank features
→ selected evidence IDs
→ canonical model-visible projection
```

Raw source text must not be copied into the aggregate report. Store hashes, stable IDs, bounded excerpts in per-case artifacts, and scalar metrics in the summary.

## Required work

### A. Freeze an offline baseline

1. Add one command that runs every checked-in retrieval golden set against deterministic local fixture indexes.
2. Run lexical mode for every corpus. Run hybrid/sparse/dense only where the required local capability is present; missing capability must be explicit, not silently counted as lexical success.
3. Persist:
   - dataset digest;
   - corpus/index revision;
   - retrieval-config hash;
   - index-schema version;
   - code revision;
   - per-case result;
   - aggregate metrics.
4. Record candidate and projection token estimates separately.
5. Do not call an LLM, embedding API, Context7, GitHub Models, or a paid provider.

### B. Make ranking direction and features explicit

1. Add an immutable `RankingCandidate`/equivalent internal value containing raw component ranks and named feature contributions.
2. Correct the FTS5 direction bug with adversarial unit tests.
3. Make ties deterministic using a stable evidence/chunk identity, never SQLite insertion order alone.
4. Record why a result moved up or down without exposing raw document content.
5. Preserve the public `RetrievedChunk` shape until a separate compatibility task approves a change.

### C. Expand the provider-free dataset

Add independently useful cases across at least these classes:

- exact API identifier/signature;
- file path, symbol, configuration key, and CLI flag;
- error message or error code;
- conceptual guide expressed with synonyms;
- code example;
- migration/version-specific question;
- exact dependency version versus wrong-version distractor;
- project-owned rule versus external generic documentation;
- multi-document/cross-module requirement;
- locale mirror and generated/changelog/legal distractors;
- Russian and English paraphrases where the corpus supports them;
- queries with no sufficient evidence.

Each case must declare expected sources or sections, required facts, forbidden sources/versions, and whether a code snippet is required. Add paraphrase groups so a fix cannot depend on one exact query string.

Split the dataset before implementation:

- development: visible for feature work;
- holdout: digest frozen, evaluated only by the gate;
- adversarial: deliberately misleading titles, duplicated text, stale versions, and authority conflicts.

Do not use Task 33 hidden tests or oracle patches as retrieval-tuning data.

### D. Add quality-per-token metrics

At minimum report:

- Recall@1/3/5/20 and MRR;
- nDCG where graded relevance is present;
- required-fact pass rate;
- forbidden-source and forbidden-version violation rate;
- unknown-version rate;
- authoritative-source-at-1 rate;
- exact-identifier-at-1 rate;
- snippet-required pass rate;
- source diversity and duplicate/near-duplicate rate;
- raw candidate tokens;
- selected evidence tokens;
- canonical model-visible tokens;
- required facts per 1,000 model-visible tokens;
- p50/p95 retrieval latency;
- explicit degraded-mode rate.

Do not invent a single “quality score” that can hide a correctness loss behind token savings. Keep correctness, contamination, tokens, and latency separately visible.

## Acceptance gate

Task 39 is complete only when:

- the FTS5 direction behavior is covered by executable adversarial tests;
- one frozen offline command produces deterministic baseline and candidate-trace artifacts;
- development, holdout, and adversarial dataset digests are stored;
- every result is bound to index/config/code revisions;
- required-fact pass rate does not decrease on any protected existing case;
- forbidden source/version violations remain zero on protected cases;
- holdout Recall@5 and MRR do not regress from the frozen baseline;
- model-visible token ceilings from Task 36 remain unchanged;
- the full provider-free suite, `compileall`, and `git diff --check` pass.

No claim about real-model token savings or answer quality is permitted from this task alone.

## Non-goals

- Do not add a new embedding model.
- Do not change chunk boundaries or rebuild the production schema.
- Do not add remote reranking or an LLM indexing step.
- Do not increase top-K or model-visible budgets to make recall green.
- Do not resume the credentialed Context7 or Task 33 benchmark.
- Do not tune the holdout after reading its failures.

## Research basis

- [Andrej Karpathy on context engineering](https://x.com/karpathy/status/1937902205765607626) — the design target is the right information for the next step, not maximum context volume.
- [SQLite FTS5 BM25 documentation](https://sqlite.org/fts5.html#the_bm25_function) — better matches are numerically lower, which makes score direction an explicit correctness requirement.
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) — long context does not guarantee robust use of relevant evidence and can introduce positional failure.
- [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) — hybrid exact/semantic retrieval, contextualized chunks, reranking, and domain-specific evals are promising, but must be tested on the product's own corpus and budget.

## Handoff to the next task

Task 40 may start only from Task 39's frozen baseline. Every proposed chunking/index variant must be evaluated against the same digests and must report both quality and model-visible token impact.

## Implementation evidence

Implemented on `agent/task39-retrieval-ranking-truth` with these provider-free boundaries:

- `python -m eval.retrieval_quality_baseline --output-dir <dir>` builds a temporary local SQLite fixture index and writes one scalar summary plus bounded per-case candidate traces;
- `--baseline eval/retrieval_quality/baseline_v1/summary.json` fails on Recall@5, MRR, required-fact, or forbidden-source/version regressions in any split;
- the frozen deterministic result digest is `7339967d86d77dfd3a1a30b56cc2190ced5b69171ff67a2f34073925575a286b`;
- development, holdout, and adversarial Recall@5, MRR, and required-fact pass rate are all `1.0` in the frozen run;
- development and holdout forbidden-source/version violation rates are zero;
- adversarial candidate traces deliberately retain selected-context contamination as a separate visible metric. Task 39 proves candidate ordering; Task 42 must remove ineligible supporting evidence before model projection.
- the gate compares every protected case independently, so an aggregate improvement cannot hide a case-level Recall@5, reciprocal-rank, required-fact, contamination, or visible-budget regression;
- source revision binding uses a digest of the ranking, projection, and runner source files, rather than an unresolvable intermediate local Git commit;
- legacy external-corpus goldens are digest-inventoried as snapshot-only and are not falsely reported as locally executed;
- the checked-in holdout is the frozen baseline for Task 40 and later variants. It is not a blind pre-change control and therefore does not prove that Task 39 itself improved product quality;
- focused ranking/baseline validation passes with `28 passed`; the full provider-free suite passes with `2208 passed, 10 skipped`; `compileall` and `git diff --check` pass.

This evidence does not claim real-model token savings or answer correctness.
