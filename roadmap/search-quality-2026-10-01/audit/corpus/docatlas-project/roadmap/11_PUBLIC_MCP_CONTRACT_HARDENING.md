# Task 11 — make the three-tool MCP contract agent-proof

## Priority

P0. This is the public boundary used by weaker coding models.

## Problem

The public tool count is three, but the boundary is still ambiguous:

- `get_docs_context` exposes flags that can trigger preparation or network work;
- missing library guidance can point back to retrieval with `allow_network=true`;
- `prepare_docs` uses one broad nullable argument bag for many actions;
- unknown or action-irrelevant fields may be ignored or become handler exceptions;
- singular `version` is not propagated consistently and can fall back to latest.

## Goal

Make tool choice and argument construction deterministic from the schemas and returned next action.

## Required behavior

### `get_docs_context`

1. It performs retrieval only. It must not crawl, fetch, index, sync files, or start a mutation job.
2. Remove mutating compatibility fields such as `prefetch_auto` and `prepare_project_docs` from the public schema. Keep compatibility, if required, outside the public three-tool inventory.
3. When a corpus is missing or stale, return one structured `next_action` for `prepare_docs` with the exact action and complete argument patch.
4. Repeating the original query after a successful preparation must require no rewritten question.

### `prepare_docs`

5. Define action-specific validation using a discriminated JSON Schema or an equivalent explicit server validator.
6. Reject unknown fields and fields irrelevant to the selected action with `validation_error`; never leak `KeyError`, `TypeError`, or a traceback.
7. Define one typed version contract. A singular `version=X` must reach source resolution as `X`; a list is accepted only by actions that explicitly document multiple versions.
8. Remote work returns either an immediate validation/policy error or a job reference. It must not hide a long crawl in the tool response.

### Shared response contract

9. Use stable reason codes and include only safe fields required for the next call.
10. Keep the public inventory exactly `get_docs_context`, `prepare_docs`, and `docs_status`.

## Tests

Test through the real MCP dispatcher and application service, not only helper functions:

- a missing Kotlin corpus returns `prepare_docs(prefetch_library_docs)` rather than another retrieval call;
- singular `version=1.8.1` is observed unchanged by the resolver;
- missing, unknown, and irrelevant fields return `validation_error`;
- `dry_run` for prefetch is rejected if unsupported;
- a spy proves `get_docs_context` makes zero mutation/network calls;
- public tool snapshot contains exactly three names.

## Non-goals

- Do not add a fourth tool.
- Do not fix crawler reliability in this PR.
- Do not delete legacy Python/CLI APIs unless required to keep them out of the public schema.

## Acceptance criteria

- A weaker model can follow every missing/stale response by copying one returned action and arguments.
- Exact singular versions never become `latest`.
- Invalid payloads always produce a stable structured validation response.
- Retrieval has a tested zero-mutation boundary.
- Focused MCP tests and `git diff --check` pass.
