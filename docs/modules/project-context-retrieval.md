# Project context retrieval module

## Responsibility

Project context retrieval turns a free-form project question into attributed
`docs_context`. It retrieves current, explicitly admitted repository documentation;
the host writes the final answer. Retrieval does not certify an answer or an edit.

## Public boundary

The MCP boundary is `get_docs_context(question, project_path, search_question?, lookup_queries?, module_path?, scope?)`.
The original question is authoritative and preserved unchanged. Optional host
lookups are explicit same-question requests; they cannot become original-query
coverage, inferred answer obligations, translations, or generated subquestions.

`scope="project"` reads repo-level docs; `scope="module"` requires one exact
module path; `scope="all"` includes repo and module docs from the same repository.
Scope never widens because a question happens to mention another module.

## Domain vocabulary

- `DocumentationQueryPlan` is an immutable plan of the original and explicit host lookups.
- `DocumentationLookup` records each query's exact text, ID, origin, and relation.
- Query lineage keeps original-query and host-lookup credit separate.
- Evidence qualification checks the final visible evidence for each query.
- `ContextSelectionDecision` records selected evidence and retrieval coverage.

## Application orchestration

`ProjectContextService` builds one query plan and passes it to project retrieval.
Candidate allocation gives one opportunity to each explicit query lane before
consuming second candidates. No inferred intents or aliases enter this schedule.
For compound reads, selection accounts for distinct user-visible queries and
requalifies coverage against the final visible source fields. A found passage
may be useful without covering the entire original question.

Current file and catalog-entry hashes must match the indexed member. Changed,
deleted, or no-longer-admitted documents cannot supply current retrieval evidence.
Read-only requests never reconcile or mutate the member store.

## Infrastructure port

The retrieval gateway provides filtered project chunks, field-level lexical
match provenance, and exact-source indexed sections. Application code owns
orchestration and allocation. Domain policies own lineage, source-role
eligibility, and visible evidence qualification. SQLite owns persistence and
candidate generation; metadata-only matching may discover a candidate but
cannot qualify public evidence. Neither infrastructure nor the MCP adapter
decides answer support.

Lexical retrieval treats the original document text and headings as content.
Catalog descriptions are separate routing information; scope labels, source
class labels, and absolute storage paths are not content matches. Existing
indexes remain readable without an implicit rebuild or preparation operation.
Identifiers keep their literal word boundaries: `action` does not match
`next_action`, and a metadata occurrence of `source_of_truth` cannot turn an
unrelated `of` in the body into a content match. The original quoted FTS query
grouping is retained; the stricter source-field check runs before acquisition
limits are applied.
The original question and explicit translations/lookups share a final selection
step after their candidates have been combined and source-checked.

## MCP adapter and fidelity

The adapter exposes source-attributed `docs_context` for project reads. It keeps
source identity, content hashes, contiguous text, and coordinates together.
The native selection route chooses whole checked passages using all explicit
query lanes and the delivery budget. It measures the complete representation,
including public source references, rather than estimating source text alone.
Selected passages are not clipped to make them fit. Omitted candidates and
unverified coverage remain explicit; a delivered packet is not a completeness
claim. Input, source-read, candidate-work, and lifecycle safety bounds remain
distinct controls. An explicitly provisioned MiniLM section selector retains
its own selection policy.

Source continuation cursors are issued only for the selected batch, within the
reader's existing capacity. Retaining a previously issued selected cursor does
not refresh its expiry or read budget. The final packet is priced again after
binding; the source reader still checks current scope, membership and hashes.

## Invariants

- project reads do not produce server-certified `docs_answer`;
- parser uncertainty does not by itself block safe source retrieval;
- lookups never authorize an answer or edit and never transfer coverage to the original;
- no generated query IDs enter public coverage;
- coverage is recomputed from final visible evidence;
- cross-project, stale, unowned, and unsafe sources remain invisible;
- missing coverage is explicit; partial context is not a completeness claim.

## Failure policy

Qualified current sources produce `docs_context` with honest partial coverage.
No safe source produces `status="insufficient_evidence"` with `kind="docs_context"`.
Preparation requires an explicit returned lifecycle action or an explicit user
request, followed by the current confirmation and source-binding contract.
