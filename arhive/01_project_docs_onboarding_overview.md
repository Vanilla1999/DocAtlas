# Project Docs Onboarding Roadmap: Overview

## Goal

Make Docmancer's project-owned docs workflow reliable for coding agents, including weaker agents that may otherwise skip local documentation, read code too early, or fall back to WebFetch/model memory.

The target workflow is:

1. Inspect project docs state.
2. Follow a structured next action.
3. Ingest or refresh reviewable project docs when safe.
4. Ask for confirmation before network fetches or repo writes.
5. Query `get_project_context` / `get_project_docs` before answering project-level questions.

## Current baseline

Already available MCP surface:

- `inspect_project_docs(project_path)`
- `ingest_project_docs(project_path, ...)`
- `get_project_docs(project_path, query, ...)`
- `get_project_context(project_path, question, ...)`
- `prefetch_project_docs(project_path, ...)` for dependency docs from project manifests/lockfiles

Already established product constraints:

- Project-owned docs are reviewable repository files, not hidden Docmancer memory.
- Docmancer should not silently create or edit `ARCHITECTURE.md`.
- Dependency docs prefetch may access the network and should require user confirmation.
- Local project docs ingest is safe when it indexes existing reviewable docs only.

## Main UX gap

The workflow is close to first-class, but not yet agent-proof:

- agents may not call `inspect_project_docs` first;
- agents may ignore `next_actions`;
- agents may treat missing docs as a dead end;
- agents may miss stale index warnings;
- agents may confuse project-owned docs with dependency docs;
- agents may use generic WebFetch before local project context.

## Roadmap files

- `02_reason_codes_and_next_actions.md` — strict machine-readable states and next actions.
- `03_tool_flow_and_agent_contract.md` — expected tool choreography and agent-facing instructions.
- `04_architecture_doc_remediation.md` — safe `ARCHITECTURE.md` creation flow handled by the coding agent.
- `05_dependency_docs_prefetch.md` — lockfile/manifests path and naming cleanup for dependency docs.
- `06_bootstrap_project_docs.md` — optional high-level onboarding wrapper.
- `07_tests_and_acceptance.md` — acceptance criteria, evals, and regression tests.

## Implementation sequence

1. Add/normalize reason codes and structured next actions in `inspect_project_docs`.
2. Make `get_project_docs` / `get_project_context` return actionable remediation when project docs are missing, stale, or not indexed.
3. Strengthen tool descriptions and agent instructions around project-docs-first behavior.
4. Add safe `ARCHITECTURE.md` remediation guidance without adding hidden write behavior to Docmancer.
5. Clarify dependency docs prefetch naming and confirmation behavior.
6. Consider a high-level `bootstrap_project_docs` wrapper after the lower-level contract is stable.
7. Add tests and evals for happy paths, weak-agent paths, stale docs, and WebFetch avoidance.

## Non-goals

- Do not build a hidden CMS for official architecture knowledge.
- Do not silently write repository files from Docmancer.
- Do not silently fetch network dependency docs.
- Do not make Docmancer a hosted Context7 clone.
- Do not force Docmancer for trivial file-local edits where project docs are irrelevant.
