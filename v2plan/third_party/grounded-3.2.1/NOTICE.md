# Grounded 3.2.1 research adaptations

Copyright (c) 2025 Andre Rabold. MIT license: see LICENSE.

Upstream: https://github.com/arabold/docs-mcp-server
Pin: `f2938c47bb8937c650f0d5ddb614f867773b29f4` (`v3.2.1`).

- `fts_query.py`: Python port of `src/store/DocumentStore.ts`,
  `escapeFtsQuery`; quote-toggle and ASCII-space semantics preserved.
- `passage_splitter.py`: greedy boundary rules from
  `src/splitter/GreedySplitter.ts`. Uses existing DocAtlas original-span Markdown
  atoms, not upstream HTML-normalized base chunks. Contiguous original gaps are
  preserved, no newline synthesis. UTF-16 lengths preserve upstream size units.
  Oversized atoms are omitted, not returned above hard max. Resource caps remain.
- SQL BM25 weights/tokenizer are pinned; no embedding, RRF, assembly expansion,
  proof/admission or production switch is borrowed.

These are adapted research components, not a native Grounded run. Source files,
Git blob IDs, SHA-256 and local adaptation hashes are recorded in manifest.json.
