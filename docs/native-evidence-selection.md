# Native evidence selection, separate from page capacity

PR #230 originally fixed transport only. A 3,000-token page was still filled from an acquisition pool of up to 256 rows, even for one-fact questions. This continuation adds a distinct `evidence_selection.py` step BEFORE `native_delivery.py` formats a page. The 3,000-token / 24,000-byte / 900-line ceilings are unchanged. They protect transport and are not the selection objective.

## Compared strategies

- `preserve`: previous control, original acquisition order, fill a page.
- `query-cover-v1`: lexical coverage, cost-aware marginal gains, remove redundant selected witnesses. This aggressive research comparator can lose conditions and is not the default.
- `owner-cover-v1`: same coverage plus all already-acquired rows of a selected Markdown leaf. This avoids cutting a rule away from its qualifiers but can still choose the wrong leaf.
- `guarded-cover-v1`: default candidate. Literal explicit question clauses are handled separately, preserving query identifiers and matching source-namespace hints. Coverage saturation, not a token quota, ends selection. Keep the selected leaf's original rules and query-bearing prerequisite parent. If lexical/native ranking disagrees, coverage is diffuse or competing leaves make selection ambiguous, retain original paging as an explicit conservative fallback.

All modes are heuristic. Exact text and coordinates do not establish semantic sufficiency. Query terms, code identifiers and paths are relevance hints, NOT source access permissions. No scope is broadened, no products/case IDs/gold answers are encoded, no new documents are read and no LLM is called. Unknown terms do not prove corpus-wide absence.

## Delivery

The first page stops when its selected prefix ends. It does NOT top up the rest of the page with unselected rows. The signed continuation covers the remaining unmodified authorized pool and retains existing expiry, question/scope/source-change controls. A zero-witness initial page can issue an authenticated cursor at offset zero; continuation then exposes original evidence without pretending that no answer exists. Existing explicit `lookup_queries` are additional literal focus clauses; they do not change the original question or permission bindings.

A real MiniLM selection receipt is respected; this layer does not silently apply a second lexical veto to that selected set. `DOCATLAS_NATIVE_SELECTION=preserve` restores the previous behavior. Other clients and the legacy wire are unchanged.

## Acceptance

Reuse installed-package/native stdio plus the actual pinned OpenCode 2.1.2 normalizer and ToolOutput. All forty unchanged V40 questions use the same fifteen-document project, with independent original-span oracles opened after delivery. Compare all four native policies; require no new per-fact losses for the guarded candidate versus preserve, exact original text/coordinates, zero client truncations/spills and fewer delivered text tokens. The simple reported one-fact cases must terminate before the unchanged ceiling.

These are development/regression questions, not a blind population estimate. The test does NOT generate strong-model answers, measure provider usage or grade correct unknowns from an empty expected fact list. Full dialogue savings still require the user's matched strong-model/OpenCode run.
