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
