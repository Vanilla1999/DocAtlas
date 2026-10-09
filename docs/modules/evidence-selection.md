# Evidence selection module

## Responsibility

Evidence selection turns current eligible candidates into source-bound,
retrieval-only context. It checks catalog membership, project and module scope,
freshness, source identity, and visible support for each explicit query before
returning evidence. A useful partial passage may be returned with missing
coverage; uncertainty must not become a fabricated complete answer.

`ContextSelectionDecision` records selected evidence IDs and covered or missing
query IDs. Original-query coverage and explicit lookup coverage remain separate.
The compatibility `ProjectAnswerRequirementContract` does not compile a
free-form documentation question into inferred proof obligations.

## Contract with question planning

Question planning preserves the original request and explicit lookups. Selection
consumes those requests without inventing subjects, relations, translations, or
expected answers. A lexical match and an exact quote do not establish entailment.

Project-only reads bypass answer certification. The host may use returned
sources to explain supported facts while identifying missing information.
Neither selection nor a `docs_context` flag authorizes an edit.

## Invariants

- a retrieval hit is not proof;
- source eligibility and visible evidence support are checked before coverage is reported;
- original-query credit cannot be borrowed from host lookups;
- selected text, hashes, identity, and source-local coordinates survive projection together;
- a missing fact stays missing even when a related source is retrieved;
- output bytes and tokens are minimized without a fixed response-size acceptance ceiling;
- safety, source-read, candidate-work, and lifecycle bounds remain enforced.

## Verification

Public delivery tests verify source identity, scope, stale rejection, fidelity,
and independent query attribution. Quality evaluators compare final visible
witnesses with reviewed facts from the original questions; their expectations
are not generated from the production selection result.
