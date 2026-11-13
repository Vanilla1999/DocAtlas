# SDK delivery budgets and lexical expansion

`DocmancerClient.get_chunks` and `DocmancerAgent.query` return at most `limit`
whole source windows, with a sum of stored display-token estimates no greater
than `budget`. The stored estimator is versioned in each chunk's metadata
(currently UTF-8 bytes divided by four, rounded up). Neither estimate nor score
is proof of relevance, sufficiency or provider token usage.

`get_context` / `query_context` additionally bound the entire formatted string,
including source paths, titles, XML escaping and separators, by
`ceil(len(formatted_text) / 4) <= budget`. This preserves the formatter's
approximate character-based units, not a guarantee for an embedding or answering
model's tokenizer. External prompt instructions and questions are not included.

## Explicit tightening of the delivery contract

Previously formatting budgets counted only bodies, stripped source whitespace
and permitted an oversized first window. The corrected formatter charges the
rendered string and preserves source whitespace (XML still escapes content).
It omits whole nonfitting windows and continues in input order, without cropping.
Consequently a tight budget may legitimately produce an empty string, even if
`get_chunks` can return a body under its stored estimate. Zero means zero output;
negative caps are rejected. `None` uses SDK configuration defaults.

The SDK accepts `expand="none"`, `"adjacent"` or `"page"`. Agent query defaults
remain `query.default_expand` (currently adjacent). The dispatcher uses only its
explicit expansion argument or `retrieval.expand`, not the Agent default.

Native search windows retain BM25 order. Expansion appends exact indexed windows,
deduplicated by occurrence, within the pinned generation, source and request
filters. Adjacent means immediately preceding/following children within the source.
The existing parent-child page mode means immediate neighbors in the same parent
plus bounded same-atom code/table siblings; it is **not** the entire file or a PDF
page. At most seven neighbors per anchor are added. Public count and budget caps
include expanded windows. No coverage guarantee or automatic semantic rescue exists.

Internal dispatcher acquisition uses `SQLiteStore.acquire_candidates` and remains
independent of the SDK delivery caps. Native hits precede expanded windows under
the fixed acquisition resource ceilings. Expansion windows are source reads,
not extra BM25 hits or answer authority.
