# Task 13 — enforce library-job deadlines and capacity

## Priority

P0 reliability. This PR owns in-process execution bounds and late-publication safety only. Task 31 owns persistence/restart recovery.

## Problem

Each external ingest can create daemon threads without admission control. When the overall deadline expires, the controller changes state to cancelling but can keep waiting forever for a worker. A late worker must also be prevented from publishing staged data after timeout or cancellation.

## Goal

Bound running/queued work and make deadline/cancellation terminal even when a worker never returns.

## Required implementation

1. Replace per-job daemon-thread creation with one injected executor and bounded admission queue for library ingest.
2. Freeze safe defaults in configuration/tests:
   - maximum 2 running library jobs;
   - maximum 8 queued jobs;
   - default overall job deadline 120 seconds;
   - terminalization grace at most 2 seconds after deadline/cancel.
3. Reject overload before starting work with `busy`, `retryable=true`, and bounded retry guidance. A rejected job must not create a thread or staging generation.
4. Give every job a generation/lease checked before every staging publication, registry update, SQLite/vector commit, and success transition.
5. At deadline/cancel, revoke the lease and set a terminal state within the grace period without waiting for the worker to return.
6. Give the commit phase a bounded lease/deadline; `phase=committing` cannot bypass terminalization.
7. A late/superseded worker may clean only its own staging generation and cannot overwrite a newer job.
8. Keep `docs_status` independent of worker availability. Under full saturation, 99% of deterministic fixture calls must complete below one second.
9. Expose queue position/capacity, deadline, terminal reason, and safe phase through the existing job response. Persistence is deferred to task 31.

## Required tests

- a worker that never returns reaches terminal deadline state by `deadline + 2s`;
- that worker later returns and performs zero publication writes;
- cancellation follows the same rule;
- a hung commit cannot bypass the lease;
- two running plus eight queued jobs are accepted, the next is `busy`, and thread count remains bounded;
- a newer retry cannot be overwritten or cleaned by the older worker;
- status latency remains below the declared threshold under saturation.

Use injected clock/executor/barriers; do not use long real sleeps.

## Non-goals

- Do not persist jobs or implement restart recovery.
- Do not classify transport exceptions or change URL policy.
- Do not build a distributed queue or kill arbitrary Python threads.

## Acceptance criteria

- No in-process job remains non-terminal after deadline/cancel plus two seconds.
- Terminal/superseded workers cannot publish late state.
- Running and queued capacity is bounded, configurable, and observable.
- Status responsiveness and overload behavior pass deterministic tests.
- Related library-job/MCP tests and `git diff --check` pass.
