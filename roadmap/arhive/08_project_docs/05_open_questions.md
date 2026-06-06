# 08.05 — Open Questions

## Product / UX decisions

- Should `get_project_docs` auto-ingest when candidates exist, or only return next actions?
- Should local project file ingest require confirmation in all agents, or can it be considered safe local indexing?
- How should Docmancer phrase network-fetch confirmation for dependency docs?
- Should README present Docmancer as “Context7-compatible mental model, but project-aware”, or avoid the Context7 analogy entirely?

## Identity / storage decisions

- What is the best stable project identity: absolute path hash, git remote/root, config id?
- Can current storage metadata support project-scoped filters without schema churn?
- How should Docmancer represent stale state: file mtime, content hash, git commit, or combination?
- How should multiple checkouts of the same repo be handled?

## Tooling decisions

- How much of this should be CLI-first vs MCP-first?
- Should `inspect_project_docs` and `ingest_project_docs` exist both as MCP tools and CLI commands from day one?
- Should `prefetch_project_docs` be renamed to `prefetch_project_dependency_docs` to avoid confusion with project-owned docs?
- Should `get_project_docs(include_dependency_docs=true)` call dependency docs retrieval internally or only merge already-indexed docs?

## Memory decisions

- Should local memory exist in v1, or should it wait until official file workflow is proven?
- If local memory exists, where is the boundary between `local_memory` and `project_file`?
- Should local memory ever be included by default? Initial recommendation: no.

## Agent-discoverability decisions

- What exact wording in MCP tool descriptions reliably makes agents call `inspect_project_docs` first?
- Should `get_library_docs` itself suggest `inspect_project_docs` when called from inside a repo with no project context?
- Should Docmancer provide a single `start_project_docs_workflow` tool, or is `inspect_project_docs` enough?
- What should happen if user asks a repo-specific question and project docs are stale?
