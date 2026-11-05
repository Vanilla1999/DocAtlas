# Evidence selection module

## Responsibility

Evidence selection turns current eligible candidates into source-bound,
retrieval-only context. It checks catalog membership, project and module scope,
freshness, source identity, and visible support for each explicit query before
returning evidence. A useful partial passage may be returned with missing
coverage; uncertainty must not become a fabricated complete answer.

`ContextSelectionDecision` records selected evidence IDs and covered or missing
query IDs. Original-query coverage and explicit lookup coverage remain separate.
The compatibility `ProjectAnswerContract` does not compile a
free-form documentation question into inferred proof obligations.

## Contract with question planning

Question planning preserves the original request and explicit lookups. Selection
consumes those requests without inventing subjects, relations, translations, or
expected answers. A lexical match and an exact quote do not establish entailment.

Project-only reads bypass answer certification. The host may use returned
sources to explain supported facts while identifying missing information.
Selection and `docs_context` flags cannot authorize an edit.

## Native multilingual selection

After source validation, the native route selects from the combined original
question and explicit lookup/translation candidates. Content matches determine
relevance; technical source labels do not stand in for an answer. Selection
accounts for coverage across the explicit queries and keeps whole source-bound
passages rather than taking an arbitrary prefix of the retrieval order.
Query relevance stays fixed for complementary sections; source-text similarity
discounts redundant sections once. Word frequencies are
measured on the checked pool, so common words have less influence than rare
terms. These are ranking signals, not a learned answer-sufficiency threshold.

Budget checks price the actual delivery representation with source references
and provenance. Attribution is recomputed for the selected text, omitted
candidates remain visible as omissions, and coverage stays unverified. A lexical
ranking signal is not a semantic proof or a certificate that no answer exists.
Research flags, off by default, vary native selection without a dictionary:
`DOCATLAS_EXPERIMENT_JOINT_TERMS=char4` (character 4-gram query matches, word
redundancy), `DOCATLAS_EXPERIMENT_JOINT_PRIORITY=gain` (greedy order by marginal
gain instead of gain per square root of row bytes) and
`DOCATLAS_EXPERIMENT_JOINT_FUSION=max_shared_scale` (the best explicit query on
one pool-wide scale instead of the mean of per-query scales). Results and the
blind gate outcome are in `eval/blind_project_context/STEP3_DICTIONARY_FREE_RU.md`.
`DOCATLAS_EXPERIMENT_POOL_PRUNE` first narrows the checked pool to whole
source sections that dictionary-free views keep, each view cut by Otsu's split
of its own scores. Native selection uses `body` when the variable is unset
(accepted by the blind gate, `eval/blind_project_context/STEP7_CONTEXT7_PATH_RU.md`);
`off` restores the whole pool. Native pruning only settles competition for the
delivery budget: a checked pool whose rows all fit the delivery and reference
limits is delivered whole in every mode. `body` keeps sections that both the retrieval
BM25 score and the character 4-gram body match keep; `vote` keeps a section
that at least two of three views keep, the third being the heading-path match;
`heading` and `heading_or_body` exist for comparison; `own_heading_or_body`
is `heading_or_body` with the heading view reading only a section's own
heading, not the parent titles its sibling sections share. Word rarity stays a
statistic of the whole checked pool. Results and the blind gate outcome are in
`eval/blind_project_context/STEP4_POOL_PRUNING_RU.md`. The same filter can run in
front of the optional MiniLM section policy (there it stays off unless the
variable is set), so the model scores only the kept sections; its receipt is
`retrieval_diagnostics.pool_pruning`
(`eval/blind_project_context/STEP5_PRE_SELECTION_FILTER_RU.md`).
Two more research flags, off by default, are measured in
`eval/blind_project_context/STEP7_CONTEXT7_PATH_RU.md`:
`DOCATLAS_EXPERIMENT_JOINT_CUT=otsu_mean|otsu_union` keeps only the upper Otsu
class of sections by relevance before the greedy loop, and
`DOCATLAS_EXPERIMENT_JOINT_RELEVANCE=dense|dense_hybrid` ranks rows by a local
multilingual-E5 embedding (`DOCATLAS_EXPERIMENT_DENSE_PATH`) alone or averaged
with the lexical lane, like `mini|hybrid` do with the cross-encoder.
The optional MiniLM section policy remains separate from native selection.
Its integration audit compares delivered rows with the full checked input of
the same call and independently verifies the frozen source corpus and facts.
The native response is itself selected and is used only as a delivery-cost
comparison, not as the complete candidate pool for the MiniLM audit.

## Invariants

- a retrieval hit is not proof;
- source eligibility and visible evidence support are checked before coverage is reported;
- original-query credit cannot be borrowed from host lookups;
- selected text, hashes, identity, and source-local coordinates survive projection together;
- a missing fact stays missing even when a related source is retrieved;
- complete output bytes and tokens fit the delivery envelope without clipping selected passages;
- safety, source-read, candidate-work, and lifecycle bounds remain enforced.

## Verification

Public delivery tests verify source identity, scope, stale rejection, fidelity,
and independent query attribution. Quality evaluators compare final visible
witnesses with reviewed facts from the original questions; their expectations
are not generated from the production selection result.
