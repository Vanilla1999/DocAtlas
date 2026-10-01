# Task 31 — persist documentation job state across restart

## Priority

P0 operational reliability after tasks 13 and 30.

## Problem

Docs jobs are held in memory. MCP restart loses status, timestamps, counters, and failure evidence; staging from an interrupted worker can become orphaned. Restart must not imply that arbitrary Python work can resume safely.

## Goal

Persist the observable job state and recover interrupted work deterministically without reviving or publishing an expired generation.

## Required implementation

1. Add a versioned SQLite migration for a Docs job record containing:
   - job/correlation id and action;
   - redacted request/source identity;
   - generation/lease id;
   - queued/started/updated/finished timestamps and deadline;
   - phase, terminal state, progress counters;
   - safe error code, failed phase/URL, retryability;
   - bounded recent safe events.
2. Make the job tracker write transitions atomically through one store interface. `docs_status` reads the persisted record, not a separate divergent in-memory truth.
3. On startup, convert previously queued/running/cancelling records to terminal `interrupted`, `retryable=true`. Do not attempt to resume an arbitrary old worker.
4. Revoke every recovered generation before orphan staging cleanup. Cleanup must never delete data owned by a newer generation.
5. Retain at most 1,000 terminal jobs or 30 days by default, whichever bound is reached first; make both configurable and test pruning deterministically.
6. Keep response/event sizes bounded and reuse safe redaction from tasks 12/30.
7. An identical retry after restart creates a new job/generation linked to the interrupted predecessor and can succeed normally.

## Required tests

- persisted queued/running/cancelling jobs recover as terminal interrupted;
- terminal successful/failed/partial jobs retain status and counters after restart;
- stale generation cannot publish or delete newer staging;
- identical retry links predecessor and succeeds;
- migration from a database without the job table is idempotent;
- retention pruning keeps active/new records and respects both bounds;
- status response remains below one second for 1,000 retained jobs.

Use temporary SQLite and injected clocks; do not use real process crashes or sleeps.

## Non-goals

- Do not resume Python workers across restart.
- Do not create a distributed queue.
- Do not store raw tracebacks, credentials, or full fetched pages in job rows.

## Acceptance criteria

- Restart never loses a job silently or leaves it falsely running.
- Recovered generations cannot publish or clean newer state.
- Safe status fields survive restart and bounded retention.
- A retry after restart works without manual database cleanup.
- Migration/job tests and `git diff --check` pass.
