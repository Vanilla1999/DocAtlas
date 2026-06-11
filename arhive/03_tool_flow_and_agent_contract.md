# Project Docs Onboarding Roadmap: Tool Flow and Agent Contract

## Goal

Define the expected choreography for coding agents using Docmancer on repository-level questions.

## When agents should start with Docmancer

Agents should call `inspect_project_docs` before reading large amounts of code or using public web/docs when the user asks about:

- project architecture;
- implementation planning;
- repository conventions;
- runbooks or operational behavior;
- dependency usage in this project;
- onboarding to an unfamiliar repository;
- broad “how does this repo work?” questions.

Agents do not need Docmancer-first behavior for trivial file-local edits, direct shell commands, or questions where documentation context is irrelevant.

## Canonical flow

```text
inspect_project_docs(project_path)
  -> if project_docs_ready:
       get_project_context / get_project_docs
  -> if project_docs_found_not_indexed:
       ingest_project_docs
       get_project_context / get_project_docs
  -> if project_docs_stale:
       ingest_project_docs
       get_project_context / get_project_docs
  -> if no_project_docs:
       ask user about creating ARCHITECTURE.md
       if approved: coding agent creates file, then ingest_project_docs
       if declined: continue with code context and explain limitation
  -> if dependency_docs_available_but_not_prefetched:
       ask user before prefetch_project_docs
```

## Agent-facing instruction text

Recommended instruction for MCP tool descriptions or skills:

> For repository-level questions, call `inspect_project_docs` before relying on code search, model memory, or generic web results. Follow structured `next_action` fields. Use `ingest_project_docs` for existing reviewable project docs. Ask the user before creating repository files or fetching dependency docs from the network. Use `get_project_context` for the final project-grounded context pack.

## User-facing copy examples

### Docs found but not indexed

“I found project documentation files. I’ll index them locally with Docmancer before answering.”

### Docs ready

“Project documentation is already indexed. I’ll use the Docmancer context pack for this answer.”

### Docs stale

“Project documentation changed since the last index. I’ll refresh the local index first.”

### Docs missing

“I could not find reviewable project documentation. Do you want me to inspect the repository and create `ARCHITECTURE.md` as a reviewable file?”

### Dependency docs available

“I found project dependency manifests/lockfiles. I can fetch exact dependency docs, but that may use the network. Should I proceed?”

## Error correction behavior

If an agent calls `get_project_docs` or `get_project_context` before project docs are indexed, the response should include:

- current state;
- why the context is unavailable or incomplete;
- the exact next tool call or user confirmation needed;
- `arguments_patch` when applicable.

If an agent tries generic public docs before local project docs for a project-specific question, the tool descriptions and skill guidance should nudge it back to `inspect_project_docs` first. This is guidance, not a hard runtime guarantee.

## Acceptance criteria

- Tool descriptions distinguish project-owned docs, dependency docs, and public library docs.
- Agent instructions explicitly say when Docmancer-first applies and when it does not.
- `next_action` semantics are documented in one place.
- `get_project_context` is positioned as the primary happy-path query tool after inspection/ingest.
