# Docs MCP response and workflow contract

This note clarifies the runtime response fields and the conditional context-first workflow. Narrative result unions do not turn a status into a response kind.

## Response fields

The `get_docs_context` response has three `kind` values: `docs_answer` for a narrow typed question whose mandatory relation-specific proof obligations are complete, `docs_context` for safe retrieval-only project context when completeness or the requested relation remains uncertain, and `patch_context` for explicit change tasks. Project reads return `docs_context`, never `docs_answer`; certification belongs to library, dependency, or mixed evidence lanes. The separate `status` is `ok`, `truncated`, or `insufficient_evidence` when no safe context is available, not a fourth kind.


## Omitted material

When a bounded Docs MCP response returns `status="truncated"`, its
`omitted_counts` reports omitted material; clients should honor that field
when interpreting the bounded packet. This status describes omission of
non-critical material. It does not certify that a project-context answer is
complete or replace `status="insufficient_evidence"`.

For bounded client handling, inspect `status`, `kind`, `sources`,
`missing`, and `omitted_counts`. A response with
`status="insufficient_evidence"` means no safe context is available for the
requested documentary claim; do not present it as documentation support.

The project-documentation authoring handoff has its own nested omission report,
`documentation_gap.bounds.omitted_counts`. That nested field is not a second
name for a top-level public response field.

## Normal Docs MCP workflow

The normal Docs MCP flow is:

```text
get_docs_context(question, project_path)
→ sufficient context? answer with sources and stop
→ returned recommended_next_action? obtain confirmation if required and call that exact action
→ if a job was returned, poll docs_status(job_id)
→ preparation succeeded? retry the original bounded get_docs_context question
```

A returned preparation action is not mandatory when the context is already sufficient. A failed preparation remains an actionable failure rather than an unconditional retry loop.

## Implementation authority

The bounded field enums are validated in `docmancer/docs/application/model_visible_projection.py`; project reads are projected by `docmancer/docs/interfaces/mcp/context_tools.py`. The project-read boundary is defined in [ADR 0003](./adr/0003-context-first-project-reads.md).
