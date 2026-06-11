# Project Docs Onboarding Roadmap: Tests and Acceptance

## Goal

Verify that the project-docs onboarding path works for both ideal agents and weak agents that make common tool-use mistakes.

## Acceptance scenarios

### 1. Empty repository

Expected:

- `inspect_project_docs` returns `reason_code = no_project_docs`.
- `next_action.type = ask_user_to_create_project_doc`.
- `requires_confirmation = true`.
- User-facing message suggests `ARCHITECTURE.md`.
- No Docmancer tool writes a file silently.

### 2. Repository with README only

Expected:

- `inspect_project_docs` discovers `README.md`.
- If not indexed, it returns `project_docs_found_not_indexed`.
- Agent calls `ingest_project_docs`.
- `get_project_context` includes README-derived context with file attribution.

### 3. Repository with stale docs

Expected:

- `inspect_project_docs` returns `project_docs_stale`.
- Agent calls `ingest_project_docs` to refresh.
- Query results use fresh metadata.

### 4. Repository with docs and missing overview

Expected:

- Existing docs are still ingestible.
- `architecture_doc_creation_recommended` may appear as a suggestion or secondary remediation.
- Agent asks before creating `ARCHITECTURE.md`.

### 5. Repository with lockfile/manifests

Expected:

- Inspect output distinguishes dependency docs availability from project-owned docs status.
- Agent asks before `prefetch_project_docs` if network may be used.
- Prefetched docs preserve exact dependency version metadata.

### 6. Agent calls query before ingest

Expected:

- `get_project_docs` / `get_project_context` returns actionable remediation.
- Response includes the required next tool call and arguments.
- No generic empty answer.

### 7. Agent tries WebFetch first

Expected:

- Skills/tool descriptions instruct the agent to use local Docmancer project docs first for project-specific questions.
- Evaluation marks this as a failure for project-specific onboarding tasks.

## Unit tests

- Reason code selection for each fixture repo state.
- `next_action` shape and required fields.
- Confirmation flags for repo writes and network fetches.
- `arguments_patch` generation.
- Stale detection.

## Integration tests

Simulate full MCP flows:

```text
inspect -> ingest -> get_project_context
inspect -> stale ingest -> get_project_context
inspect -> no docs -> confirmation required
inspect -> dependency docs available -> confirmation required -> prefetch
```

## Agent evals

Create scripted agent traces for:

- compliant strong agent;
- weak agent skipping `inspect_project_docs`;
- weak agent ignoring `next_action`;
- weak agent trying WebFetch first;
- agent confusing `prefetch_project_docs` with project-owned docs ingest.

## Metrics

- `onboarding_success_rate`: percentage of sessions reaching useful Docmancer context.
- `calls_to_useful_context`: tool calls before relevant context is returned.
- `ignored_next_action_rate`: traces where agent does not follow the returned next action.
- `webfetch_before_docmancer_rate`: project-specific traces that use web before local docs.
- `architecture_doc_remediation_rate`: missing-docs traces where agent proposes `ARCHITECTURE.md`.
- `stale_refresh_success_rate`: stale-doc traces correctly refreshed before answer.

## Definition of done for MVP

- `inspect_project_docs` returns stable reason codes and next actions.
- Missing/not-indexed/stale docs return remediation, not generic failure.
- Existing docs can be inspected, ingested, and queried through the documented flow.
- User confirmation is required for repo writes and dependency docs network prefetch.
- Acceptance scenarios 1, 2, 3, and 6 pass.
