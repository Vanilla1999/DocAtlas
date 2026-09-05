# Project context retrieval module

## Responsibility

Project context retrieval turns a free-form project question into bounded,
attributed `docs_context`. It retrieves current repository-owned documentation;
it does not write the final answer and does not certify an edit.

## Public boundary

The MCP boundary is `get_docs_context(question, project_path, lookup_queries?,
module_path?, scope?)`. The original question is authoritative. Optional host
lookups contain one concept each and improve recall only.

## Domain vocabulary

- `DocumentationQueryPlan` is an immutable retrieval plan.
- `DocumentationLookup` is an original, exact-anchor, host, or generated query.
- `Query Lineage` distinguishes direct matching, audited rewrites, host lookups,
  and exact anchors without exposing generated query IDs.
- `Evidence Qualification` decides whether model-visible fields support a query.
- `Context Budget` fixes the product boundary at three sources and 800 tokens.
- `Typed Context` and `Broad Context` describe retrieval disposition.
- `Exact Technical Anchor` preserves a filename, path, command, symbol, or env var.
- `ContextSelectionDecision` records selected evidence and query coverage only.

## Application orchestration

`ProjectContextService` builds one query plan and passes it to project retrieval.
Candidate allocation gives one opportunity to exact-anchor, original-question,
and host-query lanes before consuming second candidates. Generated aliases use
the remaining capacity. Audited domain-owned aliases may attribute derived
retrieval coverage to their public parent query, but never authorize an answer.
Explicit documents may hydrate bounded indexed sections,
but only sections matching user-visible technical terms enter context.
For compound reads, selection maximizes distinct user-visible query coverage
before expanding snippets. It first admits compact witnesses, then spends any
remaining token budget on deterministic snippet expansion. Generated canonical
queries may make a source eligible and populate facet diagnostics, but they do
not become public coverage IDs.

## Infrastructure port

The retrieval gateway provides filtered project chunks, field-level lexical
match provenance, and exact-source indexed sections. Application code owns
orchestration and allocation. Domain policies own lineage, source-role
eligibility, and visible evidence qualification. SQLite owns persistence and
candidate generation; metadata-only matching may discover a candidate but
cannot qualify public evidence. Neither infrastructure nor the MCP adapter
decides answer support.

## MCP adapter

The adapter selects delivery from the resolved evidence lane. Project reads use
`docs_context`; library, dependency, and mixed reads retain evidence
certification; explicit mutations use `patch_context`.

## Invariants

- project reads never produce `docs_answer`;
- parser uncertainty does not block safe retrieval;
- exact anchors precede generic aliases;
- lookup queries and aliases never authorize an answer or edit;
- distinct host lookup IDs are tracked independently rather than by one global
  lookup-present flag;
- generated canonical query IDs never appear in `covered_query_ids` or
  `missing_query_ids`;
- only audited rewrites may provide derived coverage for their public parent;
- coverage is recomputed from the final visible path, section, and snippet;
- forbidden catalog roles or evidence terms cannot qualify that facet;
- cross-project, stale, unowned, and unsafe sources remain invisible;
- visible output remains bounded to 800 tokens and three sources.

## Failure policy

Qualified current sources produce `docs_context` with honest partial coverage.
Five lookup queries do not guarantee five sources: at most three selected
sources are returned, and directions that do not fit remain in
`missing_query_ids`.
No safe source produces `insufficient_evidence` with `kind=docs_context`. Stale
or absent indexes recommend `prepare_docs(action="sync_project_docs")`.

## Tests

The boundary is protected by `tests/docs/test_context7_style_project_chat.py`,
`tests/docs/test_model_visible_projection.py`, `tests/test_docs_service_part02.py`,
`tests/test_docs_service_part03.py`, and
`tests/test_named_document_context_integration.py`.
