# Natural-Language Library Retrieval Implementation Plan

> **For Hermes:** Use the `subagent-driven-development` skill to implement this plan task-by-task, with spec and code-quality review after each phase.

**Goal:** Make library-mode `get_docs_context` return evidence that supports a natural-language API question, or honestly return `insufficient_evidence` when the indexed corpus cannot support it.

**Architecture:** Repair the pipeline in dependency order: bounded corpus discovery first, deterministic required-evidence gating second, then route library retrieval through the existing dispatcher. Keep lexical/provider-free behavior as the control; evaluate hybrid retrieval separately and defer any model reranker until measured holdout evidence justifies it.

**Tech Stack:** Python 3, pytest, SQLite FTS5, existing Docmancer `RetrievalDispatcher`, optional existing Qdrant/FastEmbed lanes, MCP `get_docs_context`.

**Status:** Draft  
**Created:** 2026-07-20  
**Owner:** Docmancer retrieval  
**Scope:** library-mode `get_docs_context`

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

## Non-goals

- Do not add `raw.githubusercontent.com` as a generally trusted docset root.
- Do not crawl arbitrary repository roots or use an unbounded GitHub API walk. Directory-manifest discovery must be pinned to the owner/repository/ref/path derived from an approved source.
- Do not hardcode Kotlin API names into the general ranker.
- Do not add an LLM query rewriter or reranker in the first implementation.
- Do not enable hybrid retrieval globally before an A/B quality and latency gate.
- Do not treat Context7 as a correctness oracle; official pinned documentation remains the oracle.
- Do not migrate old indexes in place. Reindexing is acceptable after the index contract changes.

## Phase 0 — Freeze the defect and evaluation contract

### Task 0.1: Add a provider-free library retrieval fixture

Files:

- create `tests/fixtures/library_docs/kotlinx_coroutines/`
- create `tests/test_library_natural_language_retrieval.py`
- update `tests/diagnostic_labels.json`

Fixture inputs:

- `coroutines-basics.md`: contains launch examples and deliberately does **not** link to `composing-suspending-functions.md`;
- `composing-suspending-functions.md`: contains `async`, `Deferred`, and `await` evidence;
- `launch-distractor.md`: trusted and code-bearing but cannot answer async-result questions;
- a fake GitHub Contents API response containing approved Markdown files plus a subdirectory, symlink/submodule, non-doc file, path escape, wrong ref, and wrong repository variants for security assertions.

RED cases:

1. Natural query: “When should I use async instead of launch, and how do I obtain its result?”
2. Keyword query: `async await Deferred`.
3. Unbackticked paraphrase: “I need values from two concurrent computations rather than fire-and-forget jobs.”
4. Russian paraphrase: “Когда нужна корутина с возвращаемым результатом вместо запуска без результата?”
5. Adversarial partial match: corpus contains `launch` but no `async`; expected `insufficient_evidence`.

Required facts for supported cases:

- primary or supporting evidence contains `async`;
- evidence contains at least one result-retrieval fact: `await` or `Deferred`;
- exact version and official source remain correct.

Acceptance:

- tests fail for the current implementation for the expected reason;
- no network and no provider calls;
- failure artifacts show candidate titles and missing required evidence, not full documents.

### Task 0.2: Extend the frozen evaluation taxonomy

Files:

- create `eval/library_retrieval_quality/development.json`
- create `eval/library_retrieval_quality/holdout.json`
- create `eval/library_retrieval_quality/adversarial.json`
- create `eval/library_retrieval_quality_baseline.py`
- create `tests/test_library_retrieval_quality_baseline.py`

Reuse the existing metric vocabulary where possible:

- recall@5;
- MRR;
- nDCG@20;
- required-fact pass;
- authoritative-source-at-1;
- exact-version-at-1;
- snippet-required pass;
- insufficient-evidence pass;
- model-visible token budget.

Add:

- required-symbol coverage at 1 and 5;
- unsupported-success rate;
- partial-overlap false-positive rate;
- abstention precision on adversarial cases.

Keep holdout wording outside unit tests. The implementation author should not inspect or tune against hidden/holdout formulations while coding.

## Phase 1 — Fix bounded documentation coverage

### Task 1.1: Resolve a bounded pinned GitHub directory manifest

Files:

- create `docmancer/docs/github_source_manifest.py`
- modify `docmancer/docs/application/docs_target_service.py`
- modify `docmancer/docs/models.py` only if a typed manifest field is needed
- test in `tests/docs/test_docs_target_service.py` or create `tests/test_github_source_manifest.py`

Use the official GitHub Contents endpoint only when an approved GitHub blob target also has an explicit or confirmation-approved `source_manifest.discovery=github_directory` scope. Preserve existing single-page behavior for targets that intentionally register one blob.

```text
GET https://api.github.com/repos/{owner}/{repo}/contents/{directory}?ref={exact_ref}
```

TDD steps:

1. Add a fake API response for `Kotlin/kotlinx.coroutines`, ref `1.8.1`, directory `docs/topics`.
2. Assert that a plain single-page target still resolves only the original blob.
3. Assert that an explicitly directory-scoped target currently fails the expected multi-page manifest assertion.
4. Add a deterministic manifest resolver that derives owner/repository/ref/directory from the approved blob source, or requires explicit fields when the ref/path boundary is ambiguous.
5. Accept only `file` entries with approved `.md`/`.mdx` extensions under the exact directory prefix.
6. Recurse into returned `dir` entries only while under the exact prefix and within `max_pages`, response-byte, total-time, and cancellation limits.
7. Reject symlinks, submodules, path escapes, wrong owner/repository/ref, malformed entries, and directories whose listing reaches the documented 1,000-entry ambiguity without an explicit truncation result.
8. Construct canonical GitHub blob URLs and raw transport URLs from validated fields. Do not use or trust the API's temporary `download_url`.
9. Persist a deterministic `source_manifest` containing schema version, owner, repository, exact ref, path prefix, canonical document URLs, manifest digest, and truncation state.
10. Run the focused manifest tests and verify the fixture resolves both basics and composing pages.

Request policy:

- `api.github.com` is allowed only for the exact `/repos/{owner}/{repo}/contents/{directory}` prefix;
- the response is untrusted JSON and must pass structural and path validation;
- public unauthenticated access is the default; no token is required or logged;
- an API rate-limit or malformed response must produce an explicit incomplete-manifest diagnostic, not silently fall back to one-page “complete” coverage.
- proposing directory scope from a single-page target must remain a confirmation-first prepare action; retrieval itself must never mutate scope.

### Task 1.2: Fetch every explicit manifest seed without widening trust

Files:

- `docmancer/connectors/fetchers/web.py`
- `tests/test_web_fetcher.py`

TDD steps:

1. Pass a GitHub blob root plus two validated blob `seed_urls`; assert the current early return fetches only one page.
2. Replace the singleton GitHub branch with deterministic deduplicated fetching of the approved root and explicit manifest seeds, capped by `max_pages`.
3. For each page, reuse the exact blob-to-raw mapping and retain the canonical blob as `docset_root`/source provenance.
4. Validate every seed against owner/repository/ref/path prefix before any request.
5. Record a page-ledger row for every accepted, failed, or rejected seed.
6. Verify that a cross-repository/ref/path seed is never requested and that raw host trust is not broadened.
7. Run `pytest tests/test_web_fetcher.py -q` and the source-isolation regression tests.

Diagnostics:

- `discovery_strategy=github-directory-manifest`;
- manifest document count and digest;
- pages accepted/fetched/rejected;
- rejection counts by `cross_repo`, `cross_ref`, `outside_path_prefix`, `unsupported_type`, `non_doc_path`, and `manifest_truncated`;
- existing page ledger for every candidate.

Coverage acceptance:

- fixture indexes both basics and composing pages even though basics contains no link to composing;
- Kotlin fresh live index contains more than one page and includes the pinned composing-suspending-functions source;
- a forced refresh produces the same manifest digest;
- exact owner/repo/ref/path blob-to-raw mapping remains the only canonical equivalence.

### Task 1.3: Surface corpus coverage health

Files:

- `docmancer/docs/application/library_refresh_ops.py`
- `docmancer/docs/application/library_registry_ops.py` or the existing inspect serializer
- relevant refresh/inspect tests

Add diagnostics that distinguish:

- index exists;
- number of pages/chunks;
- manifest requested/resolved/complete/truncated;
- expected versus fetched manifest documents;
- source-manifest digest;
- likely single-page coverage.

Do not mark one page “unhealthy” universally. Return an explicit coverage shape so retrieval can explain that requested evidence is absent from a narrow or incomplete corpus.

## Phase 2 — Add semantic support and honest abstention

### Task 2.1: Introduce a conservative required-evidence contract

Files:

- `docmancer/retrieval/query_planning.py`
- `docmancer/docs/domain/snippets.py`
- tests in `tests/test_snippet_presentation.py`

Extend deterministic query analysis with `RequiredEvidence`:

- explicit quoted/backticked/dotted/camelCase/snake_case/call-like identifiers;
- conservative comparison patterns such as `X instead of Y` and `difference between X and Y`;
- optional identifiers confirmed by indexed code/title symbol metadata;
- no rule that treats every content word as a required symbol.

For the observed query, `async` and `launch` must be identified as discriminative entities even without backticks. `await`/`Deferred` can remain an eval-required fact rather than a globally inferred synonym until a general relation model is justified.

Return diagnostics:

- required symbols;
- matched symbols per candidate;
- missing symbols;
- symbol coverage ratio;
- extraction reasons.

### Task 2.2: Make snippet ranking coverage-aware

Files:

- `docmancer/docs/domain/snippets.py`
- `tests/test_snippet_presentation.py`

Change scoring so that:

- full discriminative-symbol coverage outranks partial overlap;
- source/version/completeness cannot compensate for zero coverage of a required API entity;
- `why_relevant` names actual matched and missing entities instead of generic “matches query symbols”;
- confidence cannot be `high` solely because all candidates are similarly irrelevant.

Do not require every natural-language term. Preserve conceptual queries that contain no high-confidence API entities.

### Task 2.3: Separate retrieval availability from answer support

Files:

- `docmancer/docs/application/library_docs_service.py`
- `docmancer/docs/application/unified_context_service.py`
- `tests/test_unified_docs_context.py`
- `tests/test_unified_docs_context_mcp.py`

Replace the effective `bool(context_pack)` contract with explicit fields:

- `context_available`;
- `answer_supported`;
- `evidence_coverage`;
- `missing_evidence`.

Behavior:

- supported evidence: existing success path;
- candidates exist but required API evidence is absent: `insufficient_evidence` with reason `required_evidence_missing`;
- rejected candidates stay in bounded diagnostics and are not presented as answer context;
- conceptual queries without required entities preserve existing behavior unless their existing relevance gate fails.

Acceptance:

- launch-only evidence cannot authorize an async answer;
- current exact-version and source-isolation tests remain green;
- unrelated conceptual and project-context fixtures do not over-abstain.

## Phase 3 — Reuse retrieval orchestration before adding new models

### Task 3.1: Route library lexical retrieval through the existing dispatcher

Files:

- `docmancer/docs/infrastructure/agent_index_gateway.py`
- `docmancer/docs/application/library_docs_service.py`
- `docmancer/retrieval/dispatch.py` only if a small public adapter is required
- focused dispatcher/library tests

Add a gateway retrieval method that invokes `RetrievalDispatcher` against the record-specific index. Preserve `DocmancerAgent.query()` compatibility for existing callers.

First production mode must remain `lexical`, but it should receive existing dispatcher behavior:

- deterministic query plan;
- exact-term supplement;
- intent reranking;
- retrieval traces;
- source/version filters;
- bounded candidate limits.

Expose in diagnostics:

- mode requested/used;
- candidate counts by lane;
- query-plan hash;
- retrieval failures/degradation;
- final component ranks.

Acceptance:

- no change to provider calls;
- frozen project retrieval gates do not regress;
- library fixture improves or abstains correctly;
- p95 retrieval/projection latency remains within the existing frozen gate or an explicitly reviewed bound.

### Task 3.2: Evaluate local hybrid as an A/B variant

Do not enable by default in the same change as Task 3.1.

Use the existing dense/sparse/RRF dispatcher path and record-specific vector collection. Compare:

- lexical dispatcher;
- hybrid dense+sparse+lexical;
- hybrid with existing deterministic post-fusion rerank.

Go criteria:

- no per-case frozen gate regression;
- required-fact and required-symbol coverage improve on holdout;
- unsupported-success rate does not increase;
- source/version contamination remains zero;
- vector readiness is verified rather than silently using an unrelated collection;
- latency and model-visible token bounds remain acceptable.

If hybrid does not improve holdout, keep lexical as default and diagnose chunk/context quality rather than shipping complexity.

## Phase 4 — Optional reranker experiment only if deterministic retrieval is insufficient

This phase requires explicit approval because it can add provider calls and recurring cost.

Run only after Phases 1-3 are measured. Start with the user's strict exploratory budget:

- one canary;
- two comparison cells;
- no retry;
- three provider calls total.

Compare a bounded reranker against deterministic lexical/hybrid candidates. The reranker may reorder or abstain; it must not introduce uncited facts or bypass source/version guards.

Do not ship it unless it improves hidden required-fact coverage enough to justify cost and latency. If used, cache by query-plan hash, index revision, and candidate digest.

## Phase 5 — Live acceptance and rollout

### Task 5.1: Fresh pinned Kotlin canary

Use a new isolated `DOCMANCER_HOME` and fresh `kotlinx.coroutines@1.8.1` ingest.

Required checks:

- pinned exact version;
- official canonical GitHub sources only;
- more than one page indexed;
- composing-suspending-functions page present;
- source isolation rejection counts remain zero for accepted pages;
- no broad raw host trust.

Run the existing smoke plus novel questions not present in development tests:

1. result-bearing concurrency versus fire-and-forget;
2. failure propagation between sibling coroutines;
3. cancellation cleanup;
4. timeout with nullable result;
5. supervisor behavior;
6. one deliberately unsupported concept.

For each record:

- status and reason;
- answer support;
- required-fact coverage;
- primary source/title;
- exact version;
- context items/citations;
- latency;
- missing evidence when abstaining.

The unsupported question must abstain. Supported questions must cite the official page containing the required facts.

### Task 5.2: Regression and rollout gates

Verification order:

1. focused fetcher/security tests;
2. snippet/query-planning tests;
3. library/unified context tests;
4. provider-free library retrieval baseline;
5. existing frozen retrieval-quality baseline;
6. source-isolation and exact-version suites;
7. full normal test suite;
8. isolated live Kotlin canary.

Stop rollout on:

- any cross-source or wrong-version acceptance;
- unsupported-success regression;
- holdout required-fact regression;
- diagnostic manifest mismatch;
- unbounded crawl behavior;
- vector collection identity mismatch;
- provider use in the default path.

## Risks, tradeoffs, and open questions

- **Scope expansion:** a single blob may intentionally mean one page. Directory scope must be explicit or confirmation-approved, never inferred during retrieval.
- **Ref ambiguity:** GitHub refs can contain `/`. If owner/repository/ref/directory cannot be parsed unambiguously from a blob URL, require explicit manifest fields instead of guessing.
- **API availability and rate limits:** cache the manifest digest and distinguish “last known complete manifest” from “refresh could not resolve manifest.” Never label a one-page fallback complete.
- **Directory breadth:** a docs directory can contain irrelevant or generated Markdown. Preserve `max_pages`, authority metadata, and low-value filtering; measure candidate quality after coverage expansion.
- **Over-abstention:** required-evidence extraction must remain conservative. Broad conceptual questions without high-confidence API entities must retain the existing relevance path.
- **Hybrid complexity:** vector readiness, collection identity, latency, and degraded-mode semantics must be proven per record before default enablement.
- **Benchmark overfitting:** development cases can guide implementation; holdout and novel live questions decide rollout.
- **Context7 comparison:** its public corpus size is a useful coverage reference, not evidence about its private ranking implementation or a substitute for official-source expected facts.

## Expected outcome

After Phases 0-3:

- natural-language API questions remain valid inputs;
- direct GitHub documentation seeds can build a bounded multi-page corpus;
- exact API terms and semantics have separate retrieval signals;
- trusted but irrelevant snippets no longer become successful answers;
- unsupported questions abstain with actionable diagnostics;
- hybrid retrieval can be enabled only where measured evidence justifies it;
- the default implementation remains local, deterministic, and provider-free.

## Recommended implementation order

1. Phase 0: freeze defect and metrics.
2. Phase 1: bounded Markdown coverage.
3. Re-run fixture and live corpus checks.
4. Phase 2: required-evidence gate and abstention.
5. Re-run holdout/adversarial evaluation.
6. Phase 3.1: lexical dispatcher integration.
7. Phase 3.2: hybrid A/B only.
8. Phase 4 only with explicit approval and measured need.
9. Phase 5: fresh live canary and rollout review.

Do not combine corpus discovery, semantic gating, hybrid enablement, and model reranking in one patch. Each phase has a distinct failure mode and must produce independent evidence.
