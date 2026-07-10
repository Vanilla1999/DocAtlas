# Task 09 — make external-library ingest reliable and observable

## Priority

Treat this as an immediate reliability regression and complete it before Context7 parity evaluation. A failed or blocked ingest makes retrieval quality impossible to measure fairly.

## Incident

The following Kotlin workflow exposed several independent failures:

1. Query `coroutines launch async example with code` in library mode.
2. Receive a request for an explicit documentation source.
3. Call `prepare_docs(action="prefetch_library_docs", library="kotlin", ecosystem="kotlin", docs_url="https://kotlinlang.org/docs/")`.
4. Observe `unexpected keyword argument 'async_'`.
5. Retry network ingest with an explicit Kotlin page after changing connectivity through a VPN.
6. Observe a long-running request; even `docs_status` does not respond promptly.
7. On another attempt, observe an extraction failure on a discovered GitHub `blob` URL or an unhelpful `not_found` result.

Do not treat this transcript as proof that external-library indexing is fundamentally unsupported. It demonstrates distinct API-contract, concurrency, network-recovery, crawling, and error-reporting defects.

## Confirmed root causes

### Async argument contract mismatch

The public `prepare_docs` dispatcher passes `async_` to `LibraryDocsApplicationService.prefetch_docs`, but that method and `LibraryRefreshOps.prefetch_docs` do not accept the argument. This is deterministic and is unrelated to VPN state.

Define one typed prefetch contract and use it consistently at every boundary. Unsupported request fields must produce a structured validation error rather than an internal exception.

### Blocking MCP request handling

The async MCP `call_tool` handler invokes the synchronous tool dispatcher directly. Library crawling, extraction, and indexing can therefore block the MCP event loop, preventing `docs_status` and other tools from responding.

Network ingest must run outside the server event loop. Prefer the existing job model and return a job identifier immediately; use a bounded worker/thread boundary for synchronous internals.

### Connectivity transition is not diagnosable

The transcript started without working network access and continued after enabling a VPN. The current response does not distinguish DNS, routing, proxy, TLS, connection-timeout, read-timeout, extraction, and indexing failures. It is also unclear whether a failed client or negative discovery result survives the connectivity change.

A transient network failure must not poison future attempts. Repeating the same request after connectivity is restored must work in the same MCP process without clearing state manually.

### Source crawling and extraction are too fragile

An explicit Kotlin documentation page unexpectedly led to a failing GitHub `blob` page. One bad discovered page can obscure successful pages and the origin of the failure.

Canonicalize supported GitHub `blob` URLs to raw content or route them through the GitHub-aware fetcher. Keep crawls within declared source/domain policy, bound their page count and duration, and record per-page failures without discarding usable indexed pages.

## Goal

Make external-library ingestion a bounded background operation with responsive status, actionable errors, safe retry after connectivity changes, and a successful end-to-end Kotlin query.

Preserve the three public Docs MCP tools:

- `get_docs_context`;
- `prepare_docs`;
- `docs_status`.

Do not add another public tool.

## Required implementation

### 1. Unify the prefetch API

- Add `async_` support to the library prefetch application path or remove the mismatched argument by routing it through the shared job service.
- Cover both the public dispatcher and any enabled compatibility surface.
- Validate action-specific arguments before dispatch.
- Return stable machine-readable error codes instead of leaking Python exceptions.

### 2. Keep the MCP server responsive

- Run network fetch, crawl, extraction, and indexing outside the async MCP event loop.
- When `async=true`, return `queued` or `running` with a `job_id` without waiting for the crawl.
- Ensure `docs_status(action="jobs")` remains responsive while the job is active.
- Expose completed, failed, and cancelled terminal states with timestamps and progress counters.
- Apply an overall job deadline in addition to connect/read timeouts and page limits.

### 3. Recover after offline/VPN/proxy changes

- Classify at least DNS failure, network unreachable, connect timeout, read timeout, TLS failure, HTTP failure, extraction failure, and indexing failure.
- Do not permanently cache network/discovery failures as `not_found`.
- Do not reuse a poisoned transport after proxy or route changes; recreate or refresh the network client for a retry job where necessary.
- Return a retryable flag and a concise next action.
- Redact credentials and proxy secrets from logs and tool responses.

### 4. Make crawling predictable

- Treat an explicit page URL as a bounded seed rather than an implicit request to crawl an unlimited documentation site.
- Record the requested seed, canonical URL, redirects, discovered URLs, and the reason each page failed.
- Enforce an allowlist derived from the declared documentation source; report cross-domain traversal rather than following it silently.
- Convert supported GitHub web URLs to fetchable raw/API forms.
- With `continue_on_error=true`, retain successful pages and report partial success separately from total failure.

### 5. Clarify the public workflow

- `get_docs_context` must not hide a long network crawl behind a normal retrieval request.
- If a corpus is missing, return a bounded `prepare_docs` instruction with the required source fields.
- `prepare_docs` must return either a job reference or an immediate structured validation/network error.
- After the job succeeds, repeating the exact original question must retrieve source-attributed context and code snippets when the indexed source contains them.
- A failed ingest must not collapse into a silent `not_found` response.

### 6. Add observability

For each job expose:

- source and normalized seed URL;
- phase: resolve, fetch, extract, index, or complete;
- pages attempted, completed, and failed;
- chunks indexed;
- elapsed time and deadline;
- last safe error code and failed URL;
- whether retry is allowed.

Do not expose stack traces in normal MCP responses; retain them in diagnostic logs with a correlation/job identifier.

## Reproduction and tests

Add focused tests at the application and MCP boundaries plus an integration test using deterministic local HTTP fixtures. Do not make the default test suite depend on a live VPN or public Kotlin servers.

The test matrix must include:

1. `prepare_docs` for a library with `async=false` does not raise an argument error.
2. `prepare_docs` with `async=true` returns a job immediately.
3. A slow fixture ingest runs while `docs_status` responds within one second.
4. A first attempt fails with a retryable network error; the same request succeeds after the fixture becomes reachable without restarting the MCP server.
5. Connect, read, and overall deadlines end in distinct structured errors.
6. A GitHub `blob` fixture is canonicalized to raw content.
7. One broken page plus one valid page produces partial success when requested.
8. Cross-domain links are skipped and reported unless explicitly allowed.
9. Unsupported fields such as `dry_run` are rejected as validation errors if they are not part of the public schema.
10. Existing project-document indexing remains unchanged.

Add a manually runnable live smoke test for:

- library: `kotlinx.coroutines`;
- source: an explicit official Kotlin or kotlinx.coroutines documentation URL;
- exact question: `coroutines launch async example with code`;
- output: at least one relevant code-bearing snippet with a source URL.

The smoke test may require network access, but it must have a documented timeout and must not run in the default CI suite.

## Acceptance criteria

- No `unexpected keyword argument 'async_'` is reachable through either supported prefetch mode.
- Starting a slow external ingest never prevents `docs_status` from responding within one second under the integration fixture.
- Offline failure followed by restored connectivity succeeds on retry in the same server process.
- Every failed job ends within configured bounds and reports a stable error code, failed phase, retryability, and job identifier.
- Partial extraction success is queryable and is not mislabeled as total `not_found`.
- The Kotlin smoke workflow completes and the repeated original query returns cited, code-bearing context.
- Public MCP tool count remains exactly three.
- Related tests and `git diff --check` pass.

## Non-goals

- Building or bundling a Context7-sized hosted documentation corpus.
- Automatically authoring project documentation.
- Guaranteeing that every arbitrary website can be crawled.
- Hiding all network work inside retrieval calls.
- Adding a VPN-specific integration or requiring users to restart DocAtlas after connectivity changes.
