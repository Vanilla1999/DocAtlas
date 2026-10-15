# Question planning module

## Responsibility

Question planning preserves request identity for retrieval. The current
`compile_question_plan()` facade retains the original Unicode text within its
existing input bound and marks natural-language semantics unresolved. It does
not infer subjects, relations, expected answers, proof facets, translations, or
aliases from a free-form question.

The compatibility `ProjectAnswerContract` does not compile a free-form
documentation question into inferred proof obligations. It binds the complete
original question hash, including an unknown tail, and records input-limit
diagnostics without inventing retrieval probes. Its answer-authorization
predicate returns false. Explicit immutable planning DTOs remain compatibility
types; constructing one does not grant answer or mutation authority.

## Implementation ownership

The literal compatibility facade lives in
`docmancer/docs/domain/question_plan.py`. DTO validation remains in
`question_plan_core.py`. `project_answer_contract.py` and its owned adapter
preserve the request hash and the absence of answer authorization.

The active retrieval plan lives in
`docmancer/docs/domain/documentation_query_plan.py`. It creates one required
`query-original` from the unchanged request and separate `host_lookup` entries
only for explicit host-supplied `lookup_queries`. An exact selected path remains
scope metadata, not another executable query. Host lookups have no public
parent and do not receive original-question coverage credit.

Model-visible projection belongs to the application layer. Its source checks
and delivery decisions do not reconstruct question semantics. Documentation of
an implementation path does not authorize Docs MCP to inspect Python source;
use repository code search for that task.

## Relationship to evidence-selection

Question planning preserves the original request and explicit lookups.
Evidence selection checks eligible current sources and the actual text visible
for each query. It must not replace the request or generate new obligations
from a source, lexical match, or quotation. A useful fact may be returned while
other requested information remains missing.

Project-only reads return retrieval-only `docs_context`. The host explains
supported source facts and identifies missing information; a context flag is
not an answer-proof verdict and cannot authorize an edit. Explicit patch
requests use their separate contract described in
`patch-request-planning.md`; this read path does not grant mutation permission.

## Invariants

- original Unicode, whitespace, quotation spans, and unknown tails retain their identity;
- untyped question semantics remain unresolved instead of claiming complete scope;
- original-query credit cannot be borrowed from host lookups;
- literal source paths and body identities remain separate;
- source text and metadata cannot inject a query, proof obligation, or action;
- selected text, hashes, identity, and source-local coordinates survive projection together;
- a missing fact stays missing even when related context is available;
- input, source-read, work, and lifecycle bounds remain enforced.

## Verification

The span and compiler contract families retain all historical inputs for an
explicit diagnostic run. Their ordinary compact selection is compared with
the historical selection using production mutations in the existing critical
mutation gate. `scripts/run_question_surface_gate.py` checks the frozen
question identities and unresolved state. Public MCP and self-host quality
checks independently require useful source facts and accurate provenance.
