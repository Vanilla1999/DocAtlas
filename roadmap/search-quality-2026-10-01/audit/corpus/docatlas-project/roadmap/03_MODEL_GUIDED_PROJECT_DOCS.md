# Task 03 — guide the coding model when project docs are missing

## Audit status

Partial. The handoff exists, but `evidence_complete` can be true when required architectural evidence is still missing. Task 19 owns per-section completeness and missing-evidence reporting.

## Product decision

DocAtlas does not author official project documentation. It detects documentation gaps and gives the host coding model a bounded instruction for creating or updating normal reviewable files. After the file is accepted, DocAtlas indexes it.

## Goal

Turn `no_project_docs` and `architecture_doc_creation_recommended` into an actionable, source-grounded handoff without adding filesystem write capabilities to the Docs MCP server.

## Required response shape

For a documentation gap, return a compact structure similar to:

```json
{
  "reason_code": "architecture_doc_creation_recommended",
  "documentation_gap": {
    "suggested_path": "docs/ARCHITECTURE.md",
    "required_sections": ["purpose", "entrypoints", "modules", "runtime flow", "development commands"],
    "evidence_to_collect": ["manifests", "entrypoints", "module imports", "test and build configuration"],
    "rules": ["do not invent unsupported facts", "cite repository paths", "mark uncertain claims as unknown"]
  },
  "after_file_change": {
    "tool": "prepare_docs",
    "arguments_patch": {"action": "sync_project_docs"}
  }
}
```

The exact schema may differ, but it must remain compact and machine-readable.

## Required implementation

1. Reuse existing project metadata, project map, code graph, and Trust Contract evidence.
2. Add a maintained MCP resource or installed instruction explaining how the host model creates the file.
3. Keep all writes in the host coding agent workflow.
4. After a file appears, return the existing `prepare_docs(action="sync_project_docs")` lifecycle action.

## Non-goals

- No `write_project_doc` MCP tool.
- No hidden SQLite-only architecture memory.
- No direct commit, PR, or filesystem write.
- No LLM call inside DocAtlas.

## Acceptance criteria

- Missing-doc responses tell a weaker model exactly what evidence to inspect and what file to create.
- Every requested section has an evidence category.
- The response never contains invented project-specific prose.
- Existing project-doc onboarding remains backward compatible.
