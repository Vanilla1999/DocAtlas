# Natural-Language Library Retrieval Implementation Plan

> **For Hermes:** Use the `subagent-driven-development` skill to implement this plan task-by-task, with spec and code-quality review after each phase.

**Goal:** Make library-mode `get_docs_context` return evidence that supports a natural-language API question, or honestly return `insufficient_evidence` when the indexed corpus cannot support it.

**Architecture:** Repair the pipeline in dependency order: resolve an immutable bounded manifest, atomically replace the manifest-owned corpus, extend the existing `evidence_selection.py` contract as the single owner of answer sufficiency, then route record-scoped lexical retrieval through the existing dispatcher. Retrieval execution status remains separate from answer support. Keep lexical/provider-free behavior as the control; evaluate multilingual/hybrid retrieval separately and defer any model reranker until measured holdout evidence justifies it.

**Tech Stack:** Python 3, pytest, SQLite FTS5, existing Docmancer `RetrievalDispatcher`, optional existing Qdrant/FastEmbed lanes, MCP `get_docs_context`.

**Status:** In implementation
**Created:** 2026-07-20  
**Owner:** Docmancer retrieval  
**Scope:** library-mode `get_docs_context`

---

## Execution status (updated 2026-07-22)

### Review completed

Read-only architecture review completed: `.hermes/reviews/2026-07-21-natural-language-library-retrieval-review.md`.

- Result: merge remains blocked by production `BLOCKER-1..4` and `HIGH-1..4`; earlier plan claims of complete Phase 1.2/1.3/2 were not accepted as closure evidence.
- Independent design reviews were also completed for lifecycle/manifest health, canonical support/code requirements/index witness, and Phase 3.2/5 evaluation/canary. Their findings are incorporated in the ordered gates below; they made no repository edits.

| Phase / task | Status | Verified work / remaining gate |
| --- | --- | --- |
| Phase 0 | done (characterization) | Existing paired Kotlin/non-Kotlin corpora, record-scoped gateway controls, raw-topic/compatibility RED contracts, and thin evaluation adapter remain the baseline. |
| Phase 1.1 | done (prior implementation) | Schema-v2 resolver/fetch validation, bounded official blob scope, deterministic handoff, cancellation/deadline/page-ledger hardening, and approved-directory prefetch wiring are present. This was not reopened by the review. |
| Phase 1.2 — rollback and candidate publication | complete for current lifecycle blockers | Implemented retained-active behavior for failed manifest candidate, no-chunk candidate, and vector-failed candidate. Added staging pre-publication gates for exact manifest source-set identity and vector sync. Vector sync uses the isolated staging agent before filesystem/registry publication; failed initial candidates are discarded, while failed replacements preserve the active index, status, `target_spec`, and `last_refreshed_at`. Combined focused command: `pytest -q tests/test_docs_service.py -k 'manifest or vector_sync_failure or staged_prefetch_syncs_vectors or cancelled_staged_prefetch_never_syncs_vectors' --tb=short` → `23 passed, 196 deselected` (2026-07-22). |
| Phase 1.3 — manifest identity health | partial, in progress | `LibraryRegistryOps.manifest_coverage()` now uses SQLite source identities, not counts: canonical blob URL, resolved commit, Git blob SHA, SHA-256 recomputed from stored source content, and at least one section. Same-count `{A, stale C}` versus manifest `{A, B}` is covered as `corpus_incomplete` with one missing and one stale orphan. Failed no-chunk, source-set-mismatch, and vector candidates now retain the previous active URL, status, refresh timestamp, manifest metadata, and deterministic attempt diagnostic. Latest focused command: `pytest -q tests/test_docs_service.py -k 'manifest' --tb=short` → `22 passed, 200 deselected` (2026-07-22). Remaining: expose the full requested manifest/generation inspection fields. |
| Phase 2 — canonical support and requirements | partial, not yet reopened | Existing selector/projection work exists, but review found the normal unified path still derives availability from nonempty context; code groups are Kotlin-specific projection post-processing; planner and selection do not share one requirement set; and no bounded index witness exists. Next ordered work: requirement-driven code groups, common requirements → planner/dispatcher/selector, witness probe, then one `UnifiedContextService` support producer. |
| Phase 3.2 — dispatcher evaluation | not started | Existing baseline ranks prefilled candidates and does not exercise `RetrievalDispatcher`. Implement provider-free record-scoped lexical-vs-hybrid A/B runner with frozen corpus digests, separated multilingual lane, and holdout rollout criteria. |
| Phase 5 — readiness and live canary | not started | Strengthen Kotlin async/await evidence predicate; add manual-only isolated Kotlin/go_router/unsupported canary artifact and readiness gates. Do not add live network execution to offline PR CI. |
| Final verification/review update | pending | After each phase gate, run focused tests, then broad affected suites; update `.hermes/reviews/2026-07-21-natural-language-library-retrieval-review.md` only with verified closure evidence. |

**Verification note:** Run tests through the project virtual environment (`export PATH="$PWD/.venv/bin:$PATH"; pytest ...`); the system Python lacks project dependencies and must not be used as verification evidence.

---

## Target behavior

Natural-language library questions such as:

> When should I use async instead of launch in Kotlin coroutines, and how do I obtain its result?

return evidence that actually supports the requested API concepts, or return `insufficient_evidence` when the indexed corpus cannot support the answer.

The fix must remain provider-free by default, preserve exact-version and source-isolation guarantees, and generalize beyond Kotlin.

## Observed failure

Live isolated evidence from `kotlin:kotlinx-coroutines@1.8.1:api`:

- registered source: pinned GitHub blob `docs/topics/coroutines-basics.md`;
- indexed coverage: 1 page, 8 chunks;
- active library retrieval mode: `lexical`;
- query latency: about 33 ms;
- returned status: `success`;
- returned evidence: launch-only snippets;
- absent from every returned result: `async`, `await`, `Deferred`;
- the required official guide is a different page, `composing-suspending-functions.md`.

A stricter query containing only `async await Deferred` still returned launch-only sections. This proves that the immediate failure is not merely primary-snippet ordering: the required page is absent from the corpus.

For comparison, the public Context7 page for the same library reported 83,020 tokens and 977 snippets on 2026-07-20. This is not a direct quality benchmark, but it demonstrates the coverage gap between a repository-wide corpus and the current one-page Docmancer target.

A read-only feasibility probe against GitHub's official Contents API for `Kotlin/kotlinx.coroutines`, directory `docs/topics`, ref `1.8.1`, returned 16 directory entries and 15 Markdown files, including `composing-suspending-functions.md`. This proves that a bounded pinned directory manifest can cover the missing guide without repository-wide crawling.

## Root cause

### 1. Corpus recall is impossible

`docmancer/connectors/fetchers/web.py:235-253` returns immediately for a GitHub blob or direct Markdown URL. It fetches one page and ignores the wider repository documentation directory. The pinned `coroutines-basics.md@1.8.1` file contains zero `async`, `await`, or `Deferred` occurrences and does **not** link to `composing-suspending-functions.md`, so Markdown-link crawling alone cannot repair this corpus.

No ranker can retrieve `async`/`await` evidence that was never indexed.

### 2. Library mode bypasses existing retrieval orchestration

`docmancer/docs/application/library_docs_service.py:1438-1439` calls `DocmancerAgent.query()`.

`docmancer/agent.py:723-737` calls `SQLiteStore.query()` directly.

The existing `RetrievalDispatcher` in `docmancer/retrieval/dispatch.py` is not used by this library path. Consequently, library mode does not receive the dispatcher's exact-term supplement, intent reranking, retrieval traces, RRF, or optional dense/sparse lanes.

### 3. Relevance is partial-overlap tolerant

`docmancer/docs/application/library_docs_service.py:1700-1749`:

- treats nearly every word in the question as an equal query term;
- includes natural-language filler in the denominator;
- adds lexical and code overlap without defining required API evidence.

`docmancer/docs/domain/snippets.py:248-273`:

- rewards any overlap;
- gives source/version/completeness credit even when the requested API is absent;
- reports “matches query symbols in code” for a partial match;
- does not recognize ordinary lowercase API names such as `async`, `launch`, and `await` as symbols unless another heuristic catches them.

### 4. Non-empty context is treated as an answer

`docmancer/docs/application/unified_context_service.py:342-357` sets:

```text
answer_available = bool(context_pack)
```

There is no distinction between:

- context was retrieved;
- context covers the required API entities;
- context is sufficient to answer the question.

This converts a retrieval miss into an overconfident `success`.

## External evidence

### Context7

Official `queryDocs` documentation says that `query` is the user's question or task, scoped to one concept, and explicitly gives natural-language examples. It also says the query is used to rank documentation by relevance.

Conclusion: the observed formulation is a valid documentation query. We must not require users to reduce it to test-shaped keywords.

Sources:

- https://context7.com/docs/agentic-tools/ai-sdk/tools/query-docs
- https://github.com/upstash/context7/blob/master/docs/agentic-tools/ai-sdk/tools/query-docs.mdx
- https://context7.com/kotlin/kotlinx.coroutines

The public sources do not document Context7's internal ranking algorithm. Do not claim that Context7 uses a particular hybrid or reranking implementation without evidence.

### Andrej Karpathy

Karpathy describes context engineering as filling the context window with “just the right information for the next step.” He explicitly includes RAG, related data, tools, state, history, compacting, verification, guardrails, evals, and prefetching. He warns that too little or incorrectly shaped context prevents optimal performance, while too much irrelevant context can increase cost and reduce performance.

Applied here: returning a trusted but launch-only snippet for an async/await question is still a context-engineering failure. Source correctness is necessary but not sufficient.

Source:

- https://x.com/karpathy/status/1937902205765607626

### Anthropic Contextual Retrieval

Anthropic's official article identifies two complementary failure modes:

- embeddings can miss crucial exact technical terms;
- lexical matching can miss semantic relationships.

It recommends combining embeddings with BM25 and then reranking. Their reported experiments reduced failed retrievals by 49% with contextual embeddings/BM25 and by 67% when combined with reranking. These numbers are evidence for their evaluated corpora, not guaranteed Docmancer gains.

Source:

- https://www.anthropic.com/engineering/contextual-retrieval

### GitHub repository contents API

GitHub's official Contents API can list files in one repository directory at an explicit `ref`; public repositories can be read without authentication. The endpoint is bounded to 1,000 files per directory, and its `download_url` values are temporary.

Applied here: use the API only to build a bounded, pinned source manifest. Do not trust temporary download URLs; reconstruct and validate canonical blob/raw pairs from owner, repository, exact ref, and returned path.

Source:

- https://docs.github.com/en/rest/repos/contents#get-repository-content

## Design principles

1. Coverage before ranking: absent documents cannot be reranked.
2. Candidate recall before presentation: primary-snippet tuning cannot repair a missing candidate.
3. Exact API terms and natural-language semantics are complementary signals.
4. Trust/version correctness and semantic support are separate gates.
5. Fail closed on unsupported answers, not on useful retrieval diagnostics.
6. Keep the default path provider-free and auditable.
7. Measure unseen paraphrases and adversarial partial matches, not only development prompts.
8. Do not weaken GitHub/raw source isolation.
9. `evidence_selection.py` is the sole owner of evidence eligibility and answer support; retrieval and presentation may consume its contract but must not reimplement it.
10. A directory manifest is the source of truth for one corpus generation: publish the complete exact source set atomically or retain the previous generation.
11. Operational retrieval status and model answer support are independent contracts.

## Non-goals

- Do not add `raw.githubusercontent.com` as a generally trusted docset root.
- Do not crawl arbitrary repository roots or use an unbounded GitHub API walk. Directory-manifest discovery must be pinned to the owner/repository/ref/path derived from an approved source.
- Do not hardcode Kotlin API names into the general ranker.
- Do not add an LLM query rewriter or reranker in the first implementation.
- Do not enable hybrid retrieval globally before an A/B quality and latency gate.
- Do not treat Context7 as a correctness oracle; official pinned documentation remains the oracle.
- Do not migrate old indexes in place. Reindexing is acceptable after the index contract changes.
- Do not create a second required-evidence selector in `snippets.py`, unified context, or MCP serialization.
- Do not create a second metric/serialization framework; library evaluation must adapt to `eval/retrieval_quality_baseline.py` and `eval/evidence_selection_quality.py`.

## Phase 0 — Freeze the defect and existing contracts

### Task 0.1: Add paired provider-free corpus fixtures

Files:

- create `tests/fixtures/library_docs/kotlinx_coroutines/`
- create `tests/fixtures/library_docs/python_asyncio/`
- create `tests/test_library_natural_language_retrieval.py`
- update `tests/diagnostic_labels.json`

Kotlin inputs:

- `coroutines-basics.md`: launch examples and no link to the composing guide;
- `composing-suspending-functions.md`: comparison evidence plus `async`, `Deferred`, and `await` witnesses;
- `launch-distractor.md`: trusted partial-overlap evidence that cannot explain result access;
- fake GitHub ref/commit/Contents/blob responses with valid files plus a subdirectory, symlink/submodule, non-doc file, path escape, wrong ref, wrong repository, malformed blob SHA, and oversized/deep-tree variants.

Build two variants from the same source identities:

- `corpus_gap`: launch/distractor pages only, with the composing page absent or recorded as a failed manifest member;
- `corpus_complete`: the same corpus plus the authoritative composing page.

The same async-result query must abstain on `corpus_gap` and answer on `corpus_complete`; a launch-only control remains answerable on both. For code-requesting cases, `async { ... }` and `.await()` must occur in the same cited code block from one allowed pinned source. Prose echoes or unrelated snippets cannot jointly satisfy that code-group requirement.

Add a non-Kotlin `python_asyncio` holdout with lowercase APIs, a comparison facet, a result-access facet, and a partial-overlap distractor. For example, compare `create_task()` with `gather()` and ask how the scheduled task's result is obtained; the distractor may describe task cancellation but not result access. This fixture proves the extractor is not a Kotlin `async`/`launch` rule.

RED assertions:

1. `corpus_gap` returns operational `status="success"`, `context_available=true`, `answer_supported=false`, `support_status="insufficient_evidence"`.
2. `corpus_complete` supports the English explicit and unbackticked conceptual queries with complete visible mandatory-facet coverage.
3. A partial-overlap candidate cannot authorize an answer.
4. Exact source/version contamination remains zero.
5. Failure artifacts contain bounded candidate identities and missing requirement IDs, not full rejected documents.

Run: `pytest tests/test_library_natural_language_retrieval.py -q`
Expected before implementation: FAIL on corpus coverage, support consistency, and raw-topic assertions for the documented reasons; no network or provider calls.

### Task 0.2: Freeze raw-topic and output-mode compatibility

Files:

- modify `tests/test_library_natural_language_retrieval.py`
- modify `tests/test_unified_docs_context_mcp.py`
- modify `tests/docs/test_model_visible_projection.py`

Add a recording fake gateway and assert record-specific lexical retrieval receives the raw `topic` exactly. The library name must not be prepended; scope comes from the record-specific index plus library/version/snapshot filters.

Evaluate one retrieval result through `answer`, `compact`, `full`, `debug`, and `bounded_direct`. Assert all modes expose the same support decision, missing requirement IDs, and selected evidence IDs. `bounded_direct` may project operational success into model-visible `status="insufficient_evidence"`, but it must not change the underlying support decision or expose rejected candidates as usable evidence.

Declare language expectations before implementation:

- lexical control: the Russian conceptual query is expected to return honest `insufficient_evidence` against an English corpus;
- multilingual variant: the same query may become supported only after a separately measured local multilingual A/B passes Phase 3.2;
- English explicit and unbackticked paraphrases remain mandatory lexical cases.

### Task 0.3: Add only a thin library adapter to existing eval harnesses

Files:

- create `eval/library_retrieval_quality/development.json`
- create `eval/library_retrieval_quality/holdout.json`
- create `eval/library_retrieval_quality/adversarial.json`
- create `eval/library_retrieval_quality_baseline.py`
- create `tests/test_library_retrieval_quality_baseline.py`
- reuse `eval/retrieval_quality_baseline.py`
- reuse `eval/evidence_selection_quality.py`

`eval/library_retrieval_quality_baseline.py` is an adapter only: load library-service outputs, map them into the existing retrieval/evidence case contracts, and call the existing metric, serialization, required-fact, contamination, insufficient-evidence, deterministic-selection, and model-visible validation functions. Do not copy aggregate logic or define a second `required_fact_pass`/`insufficient_evidence_pass`.

Retain existing recall@5, MRR, nDCG@20, authority, exact-version, required-fact, snippet, contamination, token-budget, and insufficient-evidence metrics. Add only library-specific derived fields:

- mandatory requirement coverage at ranks 1 and 5;
- support-decision consistency across output modes;
- answerable-abstention and unsupported-answer rates;
- partial-overlap false-positive rate;
- required code-group pass bound to one visible source/version/code block.

Keep holdout wording outside unit tests and include the non-Kotlin case. Run `pytest tests/test_library_retrieval_quality_baseline.py -q`; expected before implementation: fixture failures without metric-schema divergence from the existing harnesses.

## Phase 1 — Build and atomically publish a bounded corpus generation

### Task 1.1: Resolve and fetch an immutable GitHub directory manifest

Files:

- create `docmancer/docs/github_source_manifest.py`
- modify `docmancer/docs/application/docs_target_service.py`
- modify `docmancer/connectors/fetchers/web.py`
- modify `tests/docs/test_docs_target_service.py`
- create `tests/test_github_source_manifest.py`
- modify `tests/test_web_fetcher.py`

Use the existing `DocsTarget.source_manifest`; do not add a parallel field. Introduce source-manifest schema v2 while preserving curated schema-v1 parsing. Directory discovery is allowed only for an approved GitHub blob target with explicit or confirmation-approved `discovery.kind="github_directory"`. A plain blob remains single-page.

Persist this nested contract:

```json
{
  "schema_version": 2,
  "official": true,
  "discovery": {
    "kind": "github_directory",
    "owner": "Kotlin",
    "repository": "kotlinx.coroutines",
    "requested_ref": "1.8.1",
    "resolved_commit_sha": "<40 lowercase hex>",
    "directory": "docs/topics"
  },
  "documents": [],
  "complete": true,
  "truncated": false,
  "digest": "<sha256>"
}
```

TDD sequence:

1. Assert schema-v1 curated targets still round-trip and a plain GitHub blob does not expand.
2. Resolve `requested_ref` to a 40-hex commit before listing content; preserve the human version separately.
3. List only the validated `/repos/{owner}/{repo}/contents/{normalized_directory}?ref={resolved_commit_sha}` scope.
4. Build every subsequent API request, canonical blob URL, and raw transport URL from validated owner/repository/commit/path fields. Ignore response-provided `download_url`, `html_url`, `git_url`, and child-directory URLs.
5. Normalize paths and accept only regular `.md`/`.mdx` blobs beneath the exact directory. Reject symlinks, submodules, path escapes, wrong repository/ref, malformed type/size/SHA, and ambiguous 1,000-entry listings.
6. Enforce independent limits for `max_api_requests`, `max_directory_depth`, `max_entries_seen`, cumulative API response bytes, total duration, accepted document count, cancellation, and fetched document bytes. `max_pages` alone is not a traversal budget.
7. Sort documents by normalized path. Compute manifest digest over `(owner, repository, resolved_commit_sha, path, git_blob_sha, size)`, not URL alone.
8. After raw fetch, verify bytes against the stored Git blob SHA when supported by the transport helper; always record and verify a local content SHA-256 before indexing. A mismatch makes the manifest attempt incomplete.
9. Change the WebFetcher GitHub early return so validated manifest seeds are fetched deterministically under existing redirect, response-size, cancellation, and page-ledger budgets. Validate each seed before any request and retain the immutable commit blob as source provenance.

Request policy:

- `api.github.com` requests are reconstructed from validated scope; response URLs are data, never authorities;
- unauthenticated public access is the default and credentials are never logged;
- rate-limit, malformed response, budget exhaustion, blob mismatch, or cancellation yields `complete=false` with a reason code; never silently fall back to one-page “complete” coverage;
- proposing directory scope remains confirmation-first; retrieval never widens or mutates scope;
- keep hardened `WebFetcher` transport rather than switching factory routing to the current `GitHubFetcher`, which lacks the same budget/redirect/cancellation ledger contract.

Run: `pytest tests/test_github_source_manifest.py tests/test_web_fetcher.py tests/docs/test_docs_target_service.py -q`
Expected after implementation: deterministic blob-aware manifest, all security/budget cases green, basics and composing pages both present.

### Task 1.2: Atomically reconcile manifest-owned corpus generations

Files:

- modify `docmancer/docs/application/library_refresh_ops.py`
- modify `docmancer/docs/application/docs_prefetch_service.py`
- modify `docmancer/docs/infrastructure/agent_index_gateway.py` only if a shared staging agent API is required
- modify `tests/docs/test_docs_job_service.py`
- modify `tests/docs/test_docs_prefetch_service.py`
- create `tests/docs/test_manifest_ingestion_lifecycle.py`

Implement one manifest-ingest orchestrator in the application lifecycle and make both public prefetch/refresh paths delegate to it for schema-v2 directory targets. Do not leave one direct append-only `agent.add(..., recreate=False)` path and one staging path.

Required lifecycle:

1. Resolve the complete immutable manifest before mutating active state.
2. Create an empty staging corpus for directory manifests even for synchronous calls. Do not copy the production DB/extracted tree into this staging generation; retain copy-on-refresh behavior only for non-manifest targets that still need it.
3. Ingest exactly the accepted manifest entries with vectors disabled. Record normalized source identity, blob SHA, content SHA-256, requested version, and resolved commit for every indexed document.
4. Before commit, assert `indexed_source_set == accepted_manifest_source_set`, all indexed content hashes match, no stale/orphan sources exist, the manifest is complete/not truncated, and chunks are non-empty for every required document according to the declared extraction policy.
5. Publish lexical DB/extracted artifacts and registry generation metadata under the existing lock/rollback boundary. Removed manifest entries disappear because the candidate generation is exact, not append-only.
6. On API/fetch/extraction/index/validation failure or cancellation before commit, discard staging and leave the previous active generation, active manifest digest, and search results unchanged.
7. For a first ingest with no previous complete generation, persist `manifest_incomplete` attempt diagnostics but do not mark the record `available`.
8. Synchronize the record-specific vector collection only after successful lexical publication. A vector failure marks vector readiness degraded without relabeling an incomplete lexical corpus as complete.

Mandatory tests:

- manifest v2 removes `obsolete.md` and refresh makes it unsearchable;
- one page fails and the old generation/digest/results remain unchanged;
- truncated manifest never publishes as complete;
- cancellation between fetch and commit leaves production unchanged;
- synchronous refresh also uses empty staging and rollback;
- both public manifest prefetch paths produce the same source set, digest, and registry state;
- vector sync is not invoked before lexical publication.

Run: `pytest tests/docs/test_manifest_ingestion_lifecycle.py tests/docs/test_docs_job_service.py tests/docs/test_docs_prefetch_service.py -q`
Expected after implementation: exact replacement, rollback, cancellation, and entry-removal tests pass.

### Task 1.3: Make coverage health generation-aware

Files:

- modify `docmancer/docs/application/library_refresh_ops.py`
- modify `docmancer/docs/application/library_registry_ops.py` or the existing inspect serializer
- modify relevant refresh/inspect tests

Expose at least:

- `manifest_expected`, `manifest_fetched`, `manifest_indexed`, `manifest_missing`, `manifest_stale_orphans`;
- `active_manifest_digest`, `last_attempt_manifest_digest`, `last_complete_manifest_digest`;
- `requested_ref`, `resolved_commit_sha`, `complete`, `truncated`;
- ingestion/fetch policy version, page/chunk counts, active generation identity, and likely single-page coverage.

For a directory target, `healthy` requires the exact source-set and completeness invariants from Task 1.2. `chunks > 0` is not sufficient. A single-file target retains complete-one-page semantics.

Bump the ingestion/fetch policy version. A record built under the old one-page policy becomes `needs_refresh`, even when non-empty. Distinguish support failure causes:

- `corpus_incomplete`: manifest/active generation is incomplete, truncated, stale, or missing entries;
- `retrieval_miss`: a complete corpus contains requirement witnesses confirmed by a bounded index probe, but candidate retrieval omitted them;
- `required_evidence_missing`: the complete corpus/candidate bundle cannot cover mandatory requirements and no retrieval-miss proof exists.

Do not infer `retrieval_miss` merely from an empty candidate list. Emit it only when the bounded index-level witness probe proves the evidence exists outside the selected candidates.

## Phase 2 — Extend the canonical evidence contract and abstain honestly

### Task 2.1: Build one shared requirement set from the query

Files:

- modify `docmancer/docs/application/evidence_selection.py`
- modify `docmancer/retrieval/query_planning.py`
- modify `docmancer/docs/models.py`
- modify `tests/docs/test_evidence_selection.py`
- add focused query-analysis tests beside existing retrieval planning tests

Extend the existing `EvidenceRequirement`/`build_requirements()` machinery; do not add a selector in `snippets.py`. Introduce one immutable `EvidenceRequirementSet` container with:

- mandatory/optional `required_entities`;
- mandatory/optional `required_facets`;
- source, exact-version, snapshot, project/module requirements already owned by the selector;
- query-span and extraction provenance for every requirement;
- enrichment/index revision when corpus metadata contributes an identifier;
- deterministic `requirements_hash` over the complete contract.

`query_planning.py` owns only pure deterministic query analysis and retrieval hints. `evidence_selection.py` remains the canonical builder/validator of the requirement set. Corpus-confirmed identifier enrichment is a separate stage after query analysis; if used, include the index revision and enrichment inputs in `requirements_hash`. Do not hide mutable index reads inside pure `build_query_plan()`.

Supported extraction patterns:

- explicit quoted/backticked/dotted/camelCase/snake_case/call-like identifiers;
- conservative lowercase comparison anchors from spans such as `X instead of Y`, `difference between X and Y`, and equivalent syntax;
- answer facets such as `comparison` and `result_access`, tied to the actual query span;
- no rule that turns every content word into an entity and no Kotlin-specific API table.

For the target query the production requirement set must include:

```text
mandatory entities: async, launch
mandatory facet: comparison(async, launch)
mandatory facet: result_access(async), query span="obtain its result"
```

`await` and `Deferred` remain fixture-approved witness facts for `result_access`, not globally hardcoded synonyms. The non-Kotlin fixture must produce the same facet kinds with different lowercase APIs.

Add a `library_docs_answer` selection profile so these new facet requirements do not silently change project patch-query semantics. Run selector/query-analysis tests and assert stable hashes under candidate-order changes.

### Task 2.2: Make the existing selector produce the sole support decision

Files:

- modify `docmancer/docs/application/evidence_selection.py`
- modify `docmancer/docs/application/model_visible_projection.py`
- modify `docmancer/docs/application/library_docs_service.py`
- modify `docmancer/docs/application/unified_context_service.py`
- modify `docmancer/docs/interfaces/mcp/context_tools.py`
- modify `docmancer/docs/models.py`
- modify `tests/docs/test_evidence_selection.py`
- modify `tests/docs/test_model_visible_projection.py`
- modify `tests/test_unified_docs_context.py`
- modify `tests/test_unified_docs_context_mcp.py`

Keep `select_evidence()` as the only eligibility/coverage algorithm. Extend its existing `SelectionDecision` and serialize one immutable `SupportDecision` projection from that same decision—never recompute missing entities/facets downstream. The shared support contract contains:

- `supported` and `support_status`;
- `missing_requirements` and mandatory coverage;
- `selected_evidence_ids`;
- existing requirement/candidate/eligibility/selection hashes plus one deterministic `decision_hash`;
- reason code selected from manifest health and selector/retrieval diagnostics.

Coverage is evaluated over the final selected evidence bundle, not every individual chunk. One chunk may cover comparison and another result access. Before returning `supported=true`, the selector must reserve token budget for at least one visible witness of every mandatory requirement and prove all selected witnesses survive projection. Supporting evidence used to satisfy a facet must be included in the returned model-visible source/evidence bundle, not only in internal `supporting_snippets`.

Required invariant:

```text
answer_supported=true
  implies visible mandatory-requirement coverage == 1.0
  and visible evidence IDs == support decision selected_evidence_ids
```

Operational and support state remain separate. Bump public `DocsResult.schema_version` from `2.0-mvp` to `2.1-mvp` and add:

```json
{
  "status": "success",
  "context_available": true,
  "answer_supported": false,
  "answer_available": false,
  "support_status": "insufficient_evidence",
  "decision": "insufficient_evidence",
  "reason_code": "required_evidence_missing",
  "missing_evidence": ["facet:result_access:async"],
  "evidence_coverage": 0.67
}
```

`answer_available` is a compatibility alias for `answer_supported`, never `context_available`. Preserve operational statuses such as `success`, `partial_success`, `not_found`, `confirmation_required`, and `failed`. In bounded model-visible projection, unsupported evidence becomes `{status: "insufficient_evidence", kind: "insufficient_evidence"}` without rewriting the underlying lane status.

All `answer`, `compact`, `full`, `debug`, and `bounded_direct` modes consume the same support decision. Internal debug diagnostics may contain bounded rejected-candidate identities/reasons; direct answer payloads must not expose rejected snippets as admissible evidence. Remove ecosystem-specific Dart-only abstention and use the same profile-driven selector contract across ecosystems.

Delete the `_answer_text()` fallback that turns `sources[0].snippet` into an answer without supported evidence. On insufficient evidence, project only the bounded reason, missing requirements, and recovery action.

### Task 2.3: Restrict snippets to presentation ranking

Files:

- modify `docmancer/docs/domain/snippets.py`
- modify `tests/test_snippet_presentation.py`

`snippets.py` consumes `EvidenceRequirementSet` and `SupportDecision` but does not determine support or implement `missing_symbols`. Its responsibilities are limited to:

- choose a primary item among already selected/eligible evidence by facet utility;
- rank full-coverage presentation above partial presentation without changing the selector decision;
- use supporting items to display facets not present in the primary;
- report matched/missing requirement IDs from the canonical decision in `why_relevant`;
- prevent `high` confidence when the support decision is insufficient.

Normalize dispatcher metadata: `metadata["code_snippets"]` remains a structured list; `metadata["code_snippet_count"]` is the integer count. Add tests proving presentation order cannot turn an unsupported decision into supported and cannot drop a mandatory-facet witness from the model-visible bundle.

Phase acceptance:

- launch-only or async+launch-without-result-access evidence cannot authorize the target answer;
- a two-chunk bundle may authorize it only when all mandatory facets remain visible;
- every public output mode has the same `decision_hash` and selected evidence IDs;
- exact-version/source isolation stays green;
- project patch-query selector behavior stays unchanged under its existing profile.

## Phase 3 — Reuse retrieval orchestration before adding new models

### Task 3.1: Route library lexical retrieval through the existing dispatcher

Files:

- `docmancer/docs/infrastructure/agent_index_gateway.py`
- `docmancer/docs/application/library_docs_service.py`
- `docmancer/retrieval/dispatch.py` only if a small public adapter is required
- focused dispatcher/library tests

Add a gateway retrieval method that invokes `RetrievalDispatcher` against the record-specific agent/store. Preserve `DocmancerAgent.query()` compatibility for existing callers, but remove `query = f"{info.library} {topic}"` from library mode: pass the raw topic unchanged. Scope is enforced by the record-specific index boundary plus metadata guards, not query pollution.

First production mode must remain `lexical`, but it should receive existing dispatcher behavior:

- deterministic query plan;
- the shared `EvidenceRequirementSet` as recall/ranking hints, never as a second support decision;
- exact-term supplement;
- intent reranking;
- retrieval traces;
- `library_id`, exact version, and exact resolved-snapshot filters;
- bounded candidate limits.

Lexical mode must not initialize or call embeddings/vector storage. After dispatch, preserve the current library post-retrieval owner/repository/source/version guard as defense in depth before passing candidates to the canonical selector.

Expose in diagnostics:

- mode requested/used;
- candidate counts by lane;
- query-plan hash;
- retrieval failures/degradation;
- final component ranks.
- raw topic hash and record/index identity;
- post-retrieval guard rejection counts;
- bounded index-witness probe result when classifying `retrieval_miss`.

Acceptance:

- no change to provider calls;
- recording gateway receives the raw topic with no library-name prefix;
- lexical tests prove no vector/embedding call occurs;
- operational `status="success"` is compatible with `answer_supported=false`;
- frozen project retrieval gates do not regress;
- library fixture improves or abstains correctly;
- exact source/version/snapshot contamination remains zero after dispatcher fusion and post-guard;
- p95 retrieval/projection latency remains within the existing frozen gate or an explicitly reviewed bound.

### Task 3.2: Evaluate local hybrid and multilingual retrieval as explicit A/B variants

Do not enable by default in the same change as Task 3.1.

Use only record-specific collections with declared embedding/model identity. Compare:

- lexical dispatcher;
- hybrid dense+sparse+lexical;
- hybrid with existing deterministic post-fusion rerank.
- a separately labelled local multilingual variant if—and only if—the configured local retrieval model is documented/tested for both query and corpus languages.

Evaluation cells must include:

- English explicit API queries;
- English conceptual/unbackticked paraphrases;
- the Russian cross-language query;
- the non-Kotlin lowercase-API comparison/result case;
- answerable controls and partial-overlap/unsupported cases.

The lexical oracle for the Russian query remains `insufficient_evidence`. Do not count that honest abstention as a lexical defect. The Russian query becomes expected-supported only for a predeclared multilingual variant that retrieves and visibly covers all mandatory requirements.

Go criteria:

- no per-case frozen gate regression;
- required-fact and required-symbol coverage improve on holdout;
- unsupported-answer rate does not increase and answerable-abstention rate is reported separately;
- source/version contamination remains zero;
- vector readiness is verified rather than silently using an unrelated collection;
- latency and model-visible token bounds remain acceptable.
- on the untouched semantic/paraphrase holdout, MRR improves by at least `0.05` and at least two predeclared cases move up by one or more ranks;
- no case regresses in status, required facts, required code group, or contamination.
- support decision consistency across output modes remains 100%;
- the Russian case is scored against the declared expectation for each variant, not one shared oracle.

If hybrid does not improve holdout, keep lexical as default and diagnose chunk/context quality rather than shipping complexity.

## Phase 4 — Optional reranker experiment only if deterministic retrieval is insufficient

This phase requires explicit approval because it can add provider calls and recurring cost.

Run only after Phases 1-3 are measured. Start with the user's strict exploratory budget:

- one canary;
- two comparison cells;
- no retry;
- three provider calls total.

Do not start a reranker experiment unless the authoritative target is already present in the bounded candidate pool but misses the required final rank. If the target is absent from the candidates, fix corpus/retrieval instead.

Compare a bounded reranker against deterministic lexical/hybrid candidates. The reranker may reorder or abstain; it must not introduce uncited facts or bypass source/version guards.

Do not ship it unless it improves hidden required-fact coverage enough to justify cost and latency. If used, cache by query-plan hash, index revision, and candidate digest.

## Phase 5 — Live acceptance and rollout

### Task 5.1: Fresh pinned Kotlin and non-Kotlin canaries

Use a new isolated `DOCMANCER_HOME` for each run. Ingest fresh `kotlinx.coroutines@1.8.1` and the existing exact-version `go_router@14.8.1` target.

Kotlin manifest checks:

- pinned exact version and active generation/manifest digest;
- official canonical GitHub sources only;
- more than one page indexed;
- composing-suspending-functions page present;
- source isolation rejection counts remain zero for accepted pages;
- no broad raw host trust;
- requested ref resolves to and is reported with an immutable commit SHA.

Run the existing smoke plus novel questions not present in development tests:

1. result-bearing concurrency versus fire-and-forget;
2. failure propagation between sibling coroutines;
3. cancellation cleanup;
4. timeout with nullable result;
5. supervisor behavior;
6. one deliberately unsupported concept.

For `go_router@14.8.1`, run a predeclared lowercase-API comparison/result query such as when to use `push` instead of `go` and how a pushed route result is obtained. Require comparison and result-access facets in visible exact-version evidence. This is the second-library generalization gate; do not substitute another Kotlin phrasing.

Also run one deliberate unsupported exact-version/API query with its missing requirement fixed before the canary starts, for example `entity:GoRouter.nonexistentResultApi`. Expected result: operational retrieval may succeed, but `answer_supported=false`, `support_status="insufficient_evidence"`, and that exact requirement remains missing.

For each record:

- operational status and support status separately;
- answer support and decision hash;
- required-fact coverage;
- visible mandatory entity/facet coverage;
- primary source/title;
- exact version;
- context items/citations;
- latency;
- missing evidence when abstaining.

Unsupported questions must abstain without changing successful lane execution into an operational failure. Supported questions must cite the official page(s) containing every mandatory visible fact/facet.

Strengthen `scripts/kotlin_live_smoke.py` before using it as a gate. Its current predicate accepts `launch OR (async AND await)`, so launch-only evidence can pass an async-result smoke. For the async-result case, require `async { ... }` and `.await()` in the same cited Kotlin code block from the pinned composing source; `async` without `await`, `await` without `async`, prose-only matches, and launch-only snippets must fail. A separate launch control may retain a launch-specific predicate.

### Task 5.2: Regression and rollout gates

Verification order:

1. focused fetcher/security tests;
2. atomic manifest lifecycle/reconciliation tests;
3. canonical selector/query-analysis tests;
4. presentation and output-mode consistency tests;
5. library/unified context tests;
6. thin-adapter provider-free library retrieval baseline;
7. existing frozen retrieval/evidence-quality baselines;
8. source-isolation and exact-version suites;
9. full normal test suite;
10. isolated live Kotlin and `go_router` canaries plus the deliberate unsupported API case.

Stop rollout on:

- any cross-source or wrong-version acceptance;
- unsupported-answer or answerable-abstention regression outside its declared variant oracle;
- holdout required-fact regression;
- source-set, blob/content hash, generation, or manifest digest mismatch;
- failed/cancelled refresh changing active generation;
- output modes disagreeing on support decision/evidence IDs;
- unbounded crawl behavior;
- vector collection identity mismatch;
- provider use in the default path.

## Hard implementation gates

1. `answer_supported=true` implies visible mandatory-requirement coverage is exactly `1.0`.
2. All public output modes produce the same support decision, decision hash, missing requirements, and selected evidence IDs.
3. A complete manifest implies `indexed_source_set == accepted_manifest_source_set` and zero stale/orphan entries.
4. A failed or cancelled manifest refresh leaves the active generation, digest, and searchable results unchanged.
5. Removed manifest entries do not remain searchable after a successful refresh.
6. Operational retrieval status and answer support status are independently testable and serialized.
7. Record-specific retrieval uses the raw topic without library-name query pollution.
8. Exact source/version/resolved-snapshot contamination remains zero.
9. Lexical and multilingual expectations are declared and scored separately, including the Russian query.
10. No new requirement extractor, output serializer, or presentation code duplicates the canonical evidence selector's eligibility/support algorithm.

## Risks, tradeoffs, and open questions

- **Scope expansion:** a single blob may intentionally mean one page. Directory scope must be explicit or confirmation-approved, never inferred during retrieval.
- **Ref ambiguity:** GitHub refs can contain `/`. If owner/repository/ref/directory cannot be parsed unambiguously from a blob URL, require explicit manifest fields instead of guessing.
- **API availability and rate limits:** cache the manifest digest and distinguish “last known complete manifest” from “refresh could not resolve manifest.” Never label a one-page fallback complete.
- **Directory breadth:** a docs directory can contain irrelevant or generated Markdown. Preserve `max_pages`, authority metadata, and low-value filtering; measure candidate quality after coverage expansion.
- **Atomic replacement cost:** exact empty staging uses additional temporary disk and rebuild time, but append-only refresh cannot satisfy manifest reconciliation. Bound disk use and clean orphaned staging generations.
- **Schema compatibility:** `2.1-mvp` adds support fields while retaining `answer_available` as an alias. Characterization tests across all output modes are mandatory before changing clients.
- **Over-abstention:** requirement extraction must remain conservative and profile-scoped. Broad conceptual questions without high-confidence entities/facets retain the existing selector behavior; do not weaken mandatory facets once extracted.
- **Cross-language limits:** English lexical retrieval is not multilingual. Keep Russian lexical abstention honest unless a declared local multilingual variant passes its own gate.
- **Hybrid complexity:** vector readiness, collection identity, latency, and degraded-mode semantics must be proven per record before default enablement.
- **Benchmark overfitting:** development cases can guide implementation; holdout and novel live questions decide rollout.
- **Context7 comparison:** its public corpus size is a useful coverage reference, not evidence about its private ranking implementation or a substitute for official-source expected facts.

## Expected outcome

After Phases 0-3:

- natural-language API questions remain valid inputs;
- direct GitHub documentation seeds can build an immutable, blob-aware, bounded multi-page corpus;
- directory refresh atomically replaces the exact corpus and removes obsolete pages without risking the last complete generation;
- exact API terms and semantics have separate retrieval signals;
- one canonical selector decides bundle-level support for all output modes;
- operational retrieval success no longer implies answer support;
- trusted but irrelevant or facet-incomplete snippets no longer become successful answers;
- unsupported questions abstain with actionable diagnostics;
- hybrid retrieval can be enabled only where measured evidence justifies it;
- the default implementation remains local, deterministic, and provider-free.

## Recommended implementation order

1. Phase 0: freeze paired corpora, raw-topic behavior, output-mode consistency, and thin eval adapters.
2. Phase 1.1: immutable blob-aware manifest resolution/fetch.
3. Phase 1.2: shared atomic manifest ingestion and exact source-set reconciliation.
4. Phase 1.3: generation-aware coverage health and reason codes.
5. Re-run paired corpus/lifecycle checks before changing support semantics.
6. Phase 2.1: extend the existing selector's shared requirement contract.
7. Phase 2.2: canonical bundle support decision and public schema/status compatibility.
8. Phase 2.3: presentation ranking only.
9. Re-run holdout/adversarial/output-mode evaluation.
10. Phase 3.1: raw-topic lexical dispatcher integration.
11. Phase 3.2: hybrid/multilingual A/B only.
12. Phase 4 only with explicit approval and measured need.
13. Phase 5: Kotlin, second-library, and deliberate-unsupported live acceptance.

Do not combine manifest resolution, corpus publication, selector semantics, dispatcher integration, hybrid enablement, and model reranking in one patch. Each phase has a distinct rollback and acceptance boundary.
