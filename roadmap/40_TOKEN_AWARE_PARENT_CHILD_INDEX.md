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

A child identity must not depend only on an auto-increment SQLite row ID. Derive it from versioned canonical material such as:

```text
index schema
canonical source identity
source content hash
parent heading path
child ordinal/span
display-text hash
```

SQLite row IDs may remain internal hydration keys, but vector/cache/audit identity must use the stable ID.

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

## Handoff to the next task

Task 41 consumes the stable parent/child index and adds deterministic contextual lexical/dense retrieval. It must compare against both the original Task 39 baseline and the selected Task 40 chunking baseline.
