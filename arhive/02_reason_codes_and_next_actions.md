# Project Docs Onboarding Roadmap: Reason Codes and Next Actions

## Goal

Make `inspect_project_docs` output deterministic enough that capable agents can follow it without guessing, and weak agents receive obvious remediation instead of generic “nothing found” failures.

## Proposed response contract

`inspect_project_docs(project_path)` should return both machine-readable and human-readable fields.

### Machine-readable fields

- `reason_code`: enum describing the primary state.
- `next_action`: structured object describing the recommended next step.
- `requires_confirmation`: boolean.
- `confirmation_reason`: optional string enum.
- `docs_found`: list of discovered project docs candidates.
- `indexed`: boolean.
- `stale`: boolean.
- `dependency_docs_available`: boolean.
- `arguments_patch`: optional object with arguments for the recommended follow-up call.

### Human-readable fields

- `agent_message`: short instruction to the coding agent.
- `user_message`: optional message to show the user when confirmation is needed.

## Reason codes

Initial enum:

- `project_docs_ready`
- `project_docs_found_not_indexed`
- `project_docs_stale`
- `no_project_docs`
- `architecture_doc_creation_recommended`
- `dependency_docs_available_but_not_prefetched`
- `project_docs_ignored_or_excluded`
- `project_docs_error`

Only one primary `reason_code` should be returned. Secondary observations can appear in `warnings` or `suggestions`.

## Next action types

Initial enum:

- `none`
- `ingest_project_docs`
- `ask_user_to_create_project_doc`
- `ask_user_to_prefetch_dependency_docs`
- `retry_with_arguments_patch`
- `inspect_error_remediation`

Important distinction:

- `ingest_project_docs` is a Docmancer MCP tool call.
- `ask_user_to_create_project_doc` is a coding-agent action, not a Docmancer write tool.
- `ask_user_to_prefetch_dependency_docs` leads to `prefetch_project_docs` only after user confirmation.

## Example outputs

### Docs found but not indexed

```json
{
  "reason_code": "project_docs_found_not_indexed",
  "next_action": {
    "type": "ingest_project_docs",
    "tool": "ingest_project_docs"
  },
  "requires_confirmation": false,
  "agent_message": "Project documentation files were found but are not indexed. Call ingest_project_docs before answering project-level questions.",
  "user_message": null,
  "arguments_patch": {
    "skip_known": false,
    "with_vectors": true
  }
}
```

### Docs stale

```json
{
  "reason_code": "project_docs_stale",
  "next_action": {
    "type": "ingest_project_docs",
    "tool": "ingest_project_docs"
  },
  "requires_confirmation": false,
  "agent_message": "Indexed project documentation is stale. Refresh it with ingest_project_docs before using it as current context.",
  "user_message": null
}
```

### No project docs

```json
{
  "reason_code": "no_project_docs",
  "next_action": {
    "type": "ask_user_to_create_project_doc",
    "suggested_file": "ARCHITECTURE.md",
    "handled_by": "coding_agent"
  },
  "requires_confirmation": true,
  "confirmation_reason": "repo_write",
  "agent_message": "No reviewable project docs were found. Ask the user whether to create ARCHITECTURE.md as a repository file, then ingest it after creation.",
  "user_message": "Project documentation was not found. Create ARCHITECTURE.md as a reviewable file?"
}
```

### Dependency docs available

```json
{
  "reason_code": "dependency_docs_available_but_not_prefetched",
  "next_action": {
    "type": "ask_user_to_prefetch_dependency_docs",
    "tool_after_confirmation": "prefetch_project_docs"
  },
  "requires_confirmation": true,
  "confirmation_reason": "network_fetch",
  "agent_message": "Project manifests or lockfiles were found. Ask before prefetching exact dependency docs because this may use the network.",
  "user_message": "I found dependency manifests/lockfiles. May I fetch exact dependency documentation from the network?"
}
```

## Acceptance criteria

- Every non-ready state returns a `next_action`.
- Every network or write-related action has `requires_confirmation: true`.
- Missing docs never returns only a generic empty result.
- `prefetch_project_docs` is clearly described as dependency-docs prefetch, not project-owned docs ingest.
- Returned field names are stable and documented.
