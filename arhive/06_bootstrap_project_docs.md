# Project Docs Onboarding Roadmap: Bootstrap Project Docs

## Goal

Consider a high-level MCP tool that reduces agent choreography errors by combining inspection, safe local remediation, and clear confirmation stops.

## Proposed tool

`bootstrap_project_docs(project_path, question = null)`

## Safety model

The tool may automatically perform safe local actions:

- inspect project docs state;
- ingest existing reviewable project docs when not indexed;
- refresh stale project docs when needed.

The tool must stop and request confirmation for unsafe or external actions:

- creating or editing repository files;
- fetching dependency docs from the network;
- large or destructive operations.

## Output contract

```json
{
  "status": "ready | confirmation_required | blocked | error",
  "reason_code": "project_docs_ready",
  "actions_taken": [
    {"tool": "inspect_project_docs"},
    {"tool": "ingest_project_docs"}
  ],
  "next_action": {
    "type": "get_project_context",
    "tool": "get_project_context"
  },
  "requires_confirmation": false,
  "agent_message": "Project docs are indexed and ready. Use get_project_context for the question.",
  "user_message": null
}
```

## When to add it

Do not start with this tool. First stabilize:

1. `inspect_project_docs` reason codes.
2. `next_action` semantics.
3. `ingest_project_docs` output.
4. `get_project_context` remediation behavior.

Only add `bootstrap_project_docs` once the lower-level tools are predictable.

## Benefits

- Fewer multi-tool mistakes for weak agents.
- One obvious entry point for repository onboarding.
- Easier documentation and demos.
- Better place to enforce safe confirmation stops.

## Risks

- Can hide important state if output is too compact.
- Can become unsafe if it mutates files or fetches network docs without confirmation.
- Can duplicate lower-level tool logic if added too early.

## Acceptance criteria

- The tool never writes files directly.
- The tool never fetches network docs without confirmation.
- The tool reports all actions taken.
- The tool returns enough detail for agents to continue with `get_project_context`.
- Lower-level tools remain available and documented.
