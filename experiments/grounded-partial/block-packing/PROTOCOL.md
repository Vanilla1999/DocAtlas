# Whole source blocks instead of mandatory character windows

Base: PR #189, experiment/contextual-late-sufficiency, a6cb4b716ce3b4066b83b337eeea99eb15d124cb. This experiment implements the user's request to remove mandatory short snippets without changing retrieval or adding another model.

## Fixed comparison

Two lanes on the unchanged 67 English questions from frozen80 (35 positive, 32 controls). Control: the previously measured combined source-bound/catalog/spelling qualification and existing character windows; archived English sufficient29/35. Treatment: same candidate inputs/order, qualifier, project/version/source checks, query-ID/requirement selector, evaluator, <=800 admission tokens for the complete DTO and <=3 sources; replace only source-fragment alternatives and final expansion with whole source-structural blocks. This is projector replay, not a live MCP/answer-model benchmark. Historical bilingual results remain untouched; do not open holdout20.

## Treatment fixed before results

Offer source-verifiable paragraphs, complete list items and lists, fenced code and tables, and contiguous combinations of complete blocks in the same section/candidate. No 160/320/520/640 character ceiling and no arbitrary sentence-prefix fallback. Read Markdown structure from already pinned corpus files; offer only original literal spans contained in an already retrieved candidate. No cross-candidate/file reads, no joining disconnected text, no source text/metadata invented by a model. Source hashes, candidate offsets, and every actually visible span are validated. Incomplete structural fragments must not be labelled complete. Parser support and any unsupported forms are explicitly documented.

Keep the existing selection ranking and novelty rules. Variants preserve the existing attribution/component/assignment priorities; structural ties prefer shorter complete alternatives, with original source order deterministic. Final expansion considers containing source-block alternatives (largest first that retains selected text and attribution and fits the complete serialized DTO). It must not use character truncation. If a necessary block does not fit, omit it instead of silently clipping. Record omitted/oversize blocks in diagnostics; existing retrieval-only flags and recovery contract remain unchanged. No claim that structural completeness proves arbitrary answer sufficiency. Work bounds are explicit errors/diagnostics, never silently treated as lack of evidence.

## Tests before replay

A full list remains available even behind a longer introduction; a complete block longer than640 and near3000 characters is not excluded by character count; a truly over-budget block is not truncated; lists, nested items, code fences and tables retain boundaries; spans cannot cross candidate/source/project/version boundaries; unsafe/stale/foreign evidence stays rejected; existing exact-identity and qualification rules are not weakened; expansion does not erase the previous selected quote; monkey patches restore on exceptions. No API/case-specific rules.

## Measurements and decision

Reproduce every archived control DTO/assessment/token count on English67 before attributing changes to treatment. Report per-question wins/losses, unchanged frozen sufficient score, control changes, lost prior supported facts and literal quotes, all source/snapshot/range/budget audits, full-payload mean/max tokens, availability of >640-character spans and their selection, and explicit budget omissions. Inspect all changed outputs, with uv-05 definitions reported separately from its longer unchanged frozen witness (which also requires the following warning). Do not alter gold to create a score improvement.

This is a single mechanistic ablation, not automatic promotion. Even positive aggregate results require reviewing regressions and native integration before production. A negative result is not a reason to tune parser/ranking thresholds against the same questions within this run. Publish source code, tests, inputs/fingerprints, outputs, diagnostics and result. Production files, index and prior artifacts stay unchanged. No automatic merge.
