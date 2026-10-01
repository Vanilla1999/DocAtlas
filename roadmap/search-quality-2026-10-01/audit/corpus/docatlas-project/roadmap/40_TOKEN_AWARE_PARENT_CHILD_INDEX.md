# Task 40 — token-aware parent/child documentation index

## Priority

P1 retrieval precision and context-efficiency. Start only after Task 39 freezes the offline quality baseline and fixes ranking direction.

## Problem

The production Markdown ingest path stores heading-sized sections. A heading may be one sentence or several thousand tokens, and the configured character chunk size does not split the normal heading strategy. Meanwhile, `docmancer/core/chunking.py` contains a structure-aware Markdown chunker that is exercised by tests but is not the canonical SQLite ingest path.

This produces two opposing failures:

- an oversized heading matches broadly and consumes most of the evidence budget;
- a small fixed window loses the document/heading context needed to rank it correctly.

The index needs small retrieval units with stable links back to authoritative parent sections. The model should still receive exact source text and citations, not synthetic retrieval metadata.

## Goal

Introduce a versioned parent/child index:

```text
source document
→ authoritative heading-scoped parent section
→ token-aware retrieval children
→ bounded parent/sibling expansion only after a child wins
```

Small child chunks improve precision. Parent identity and bounded neighbor expansion preserve meaning. Retrieval-only context must never be confused with quoted source evidence.

## Required data model

Use an additive, migratable schema. Exact names may follow existing conventions, but the model must represent:

- stable source identity;
- document content hash;
- parent section identity;
- child chunk stable identity;
- heading path and level;
- child ordinal;
- exact byte and line span in the source snapshot where available;
- verbatim `display_text` used for citation/model delivery;
- separate `retrieval_text` used only by FTS/embeddings;
- token estimate and tokenizer/estimator version;
- format, language, library/version, source class, authority, and trust metadata;
- chunking schema/config hash;
- index revision.

A child identity must not depend only on an auto-increment SQLite row ID. Keep
snapshot binding separate from logical identity: including the hash of the whole
source in every child ID would invalidate unaffected children after a local edit.
Derive identities from versioned canonical material as follows:

```text
source snapshot binding = canonical source identity + source content hash
parent logical ID = index schema + canonical source identity + heading path/levels + repeated-heading occurrence
parent revision ID = parent logical ID + parent display-text hash
child stable ID = parent logical ID + chunking config hash + child display-text hash + duplicate occurrence
```

Exact spans and ordinals are stored and audited but are not part of stable child
identity: inserting text before an otherwise unchanged child must not change its
ID. SQLite hydration uses a deterministic non-zero 63-bit projection of the
child stable ID, while the vector point ID is a deterministic UUID. Collisions
fail the transaction instead of silently aliasing chunks. Vector/cache/audit
records retain the full stable ID.

## Delivery sequence

1. Add the deterministic span-aware chunker and adversarial unit corpus.
2. Add the parent/child schema additively while retaining the v1 reader.
3. Build explicitly marked Markdown ingest as an immutable candidate generation.
   Validate child/FTS parity, parent/source links, exact Unicode spans, duplicate
   identities and the retrieval hard ceiling before switching the active pointer.
4. Make lexical and dense retrieval index `retrieval_text` while hydration and
   citations return only `display_text`.
5. Bound adjacent/page expansion to the winning parent and preserve byte-span
   deduplication before model delivery.
6. Run the 160/256/384/512 grid against the frozen Task 39 corpus, then select a
   default only if all quality gates pass and token efficiency improves.
7. Prepare the config-bound vector collection using stable UUID point IDs before
   activation; switch SQLite and vector ownership together, then prune stale IDs.
8. Publish migration, rollback, index-health, incremental-vector, focused
   retrieval, provider-free suite, compile and whitespace evidence.

## Structured chunking rules

### 1. Work in tokens, not only characters

Do not select one magic chunk size from intuition. Evaluate a bounded grid locally, for example child targets around 160, 256, 384, and 512 estimated tokens with small or zero overlap. Select defaults by the Task 39 quality-per-token gate.

The engineering estimator may remain deterministic bytes/4 for public budget gates, but the chunker must record the estimator version and must not label it provider-token usage.

### 2. Preserve semantic and syntactic atoms

- prefer heading, paragraph, sentence, list-item, table-row, and code-block boundaries;
- keep a code block or table atomic when it fits;
- split oversized code/table blocks only at line/row boundaries and retain valid wrappers;
- never split inside a UTF-8 sequence;
- retain heading ancestry on every child;
- retain exact line/byte spans after normalization decisions;
- never merge content from different authority or version scopes.

### 3. Do not make overlap visible twice

Overlap may help retrieval, but duplicated overlap must be removed by stable span/content identity before model delivery. The canonical projection must never include the same source characters twice merely because two retrieval children overlap.

### 4. Separate retrieval context from evidence

`retrieval_text` may prepend deterministic labels such as document title and heading path. `display_text` remains the verbatim cited span. Snapshot hashes and evidence IDs bind to authoritative source material, not to a retrieval-only prefix.

### 5. Expand only after selection

When a child wins, expansion may retrieve:

- the parent heading title;
- at most one preceding/following child when needed;
- the complete code/table atom intersecting the hit;
- a bounded parent excerpt.

Expansion must obey the Task 37 stage byte ceiling and Task 36 projection ceiling. It must not turn one match into an entire page dump.

## Migration and compatibility

1. Add an explicit index schema version and migration plan.
2. Rebuild derived FTS/vector rows from repository/source snapshots; never rewrite source documents.
3. Keep the old reader available only for a documented transition window or perform an atomic rebuild before activation.
4. A failed rebuild leaves the previous active index usable.
5. Vector synchronization must prune obsolete stable chunk IDs and upsert only changed children.
6. Cache identity includes chunking schema/config and embedding identity.
7. Index health reports mixed schema versions, missing parents, invalid spans, duplicate stable IDs, and vector drift.

## Evaluation matrix

For every chunking variant record:

- chunks per source and parent;
- p50/p95 child token size;
- oversized/tiny child rate;
- overlap duplication rate before and after delivery dedupe;
- index bytes and build latency;
- incremental rebuild changed/upserted/pruned counts;
- Recall@K, MRR, required facts, forbidden contamination;
- selected evidence and model-visible tokens;
- relevant facts per 1,000 visible tokens;
- retrieval p50/p95.

Include adversarial documents with:

- a very long heading;
- a headingless file;
- nested headings;
- repeated headings;
- one oversized fenced code block;
- a Markdown table split across the target size;
- list-heavy policy rules;
- duplicate paragraphs in two versions;
- Unicode/Russian text;
- content before the first heading.

## Acceptance gate

- Every indexed child has a stable parent/source/span identity.
- Reindexing unchanged content produces identical stable IDs and zero vector upserts.
- Editing one section changes only the affected parent/children plus explicit neighbors.
- No canonical response contains overlap-only duplicate source text.
- Protected required-fact and forbidden-version/source gates do not regress.
- Holdout Recall@5 and MRR do not regress beyond Task 39's predeclared tolerance.
- Median selected evidence tokens decrease, or quality improves at the same selected-token budget.
- Task 36 model-visible ceilings remain unchanged.
- Schema migration, rollback, index-health, focused retrieval, full provider-free suite, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not add an LLM-generated summary per chunk.
- Do not change the public MCP response shape.
- Do not expose retrieval prefixes as cited facts.
- Do not force vector dependencies into the base install.
- Do not expand every hit to the full parent document.
- Do not claim provider-token savings from smaller stored chunks alone.

## Implemented result

Task 40 is implemented on `agent/task40-token-aware-parent-child-index`.

- Production Markdown ingestion explicitly selects `parent-child-v1`; existing
  `sections` remain the readable `sqlite-sections-v1` compatibility layer.
- `index_generations` and the singleton active pointer separate candidate,
  active and superseded index state. `generation_sources` stores immutable
  content/metadata/token snapshots, so a failed candidate cannot invalidate the
  old active generation by changing the mutable source catalog.
- `retrieval_parents` stores logical and revision identities.
  `retrieval_children` stores stable child IDs, deterministic UUID vector IDs,
  stable hydration IDs, atom identity/type, exact char/UTF-8-byte/line spans,
  display/retrieval text and hashes, estimator/config/schema versions.
- FTS and dense embeddings consume retrieval-only heading context. Public query
  hydration and citations consume verbatim display slices only. Split code and
  table fragments receive retrieval-only wrappers and are re-split when wrapper
  overhead would exceed the hard retrieval ceiling; source spans are never
  rewritten.
- Candidate validation checks child/FTS parity, parent and immutable-source
  links, exact character/byte reconstruction, stable-ID uniqueness and the hard
  retrieval-token ceiling before the active pointer can move.
- Vector collections include the chunk config hash. A candidate is upserted by
  deterministic UUID without pruning the active collection, SQLite activation
  follows successful preparation, and stale points are pruned afterward.
  Unchanged records are rebound to the new generation without re-embedding.
- Additive legacy sections remain both vector-indexable and hydratable while a
  parent/child generation is active; switching v2 on does not silently remove
  non-Markdown/vector evidence.
- `adjacent` and `page` expansion are bounded to the winning parent for v2.
  Zero overlap is the selected v1 policy, so canonical delivery has no
  overlap-only duplication.
- Source deletion publishes a validated generation without that source instead
  of mutating active retrieval rows. `index_health()` audits active status,
  mixed versions, missing parents/source snapshots, invalid spans, duplicate
  stable IDs, FTS parity and stale bookkeeping.

### Grid decision

The provider-free runner `eval/parent_child_index_grid.py` binds to the frozen
Task 39 corpus/dataset digests and evaluates 160/256/384/512. Every variant
passes the per-case and aggregate Task 39 gates and has zero oversized/visible
overlap rate in the fixture. Incremental counts now come from the production
`sync_vector_store` path with a deterministic in-memory vector backend: every
variant records zero upserts and zero prunes for an unchanged rebuild, while the
local edit records actual changed upserts and stale UUID prunes.

The separate eight-case structure stress corpus covers long/headingless/nested/repeated
sections, oversized code/table/list atoms, duplicate versions, Russian text and
a preamble. Its legacy heading-sized median is 1,006.5 estimated evidence tokens.
The selected 160 target records mean 53.9, median 69 and max 95; selection first
requires all quality/incremental gates, then minimizes stress mean, max and
target in that order. These are deterministic UTF-8 bytes/4 engineering
estimates, not model-provider token usage.

### Validation evidence

- focused Task 40/chunker/vector/grid/compatibility checks: `27 passed`;
- provider-free grid: PASS, selected target 160;
- full suite: `2228 passed, 10 skipped`, plus one asynchronous job-status
  polling timeout under full-suite load; that test passed on immediate isolated
  retry (`1 passed`);
- `compileall`: PASS;
- `git diff --check`: PASS.

These are executable local engineering checks, not a model or provider-token
benchmark.

## Handoff to the next task

Task 41 consumes the stable parent/child index and adds deterministic contextual lexical/dense retrieval. It must compare against both the original Task 39 baseline and the selected Task 40 chunking baseline.
