# Docs MCP response and workflow contract

This note clarifies the runtime response fields and the conditional context-first workflow. Narrative result unions do not turn a status into a response kind.

## Response fields

Project reads return source-attributed `docs_context` with `answer_supported=false`, `answer_available=false`, and `edit_ready=false`. The advertised compatibility schema also names `docs_answer`; it does not grant free-form answer certification. Advanced `patch_context` is available only when explicitly enabled and advertised and carries no edit permission. The separate `status` includes `ok`, `truncated`, `insufficient_evidence`, and `failed`; it is not another result kind.


## Omitted material

When a bounded Docs MCP response returns `status="truncated"`, its
`omitted_counts` reports omitted material; clients should honor that field
when interpreting the bounded packet. This status describes omission of
non-critical material. It does not certify that a project-context answer is
complete or replace `status="insufficient_evidence"`.

For client handling, inspect `status`, `kind`, `sources`,
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

The response fields and source fidelity are validated in `docmancer/docs/application/model_visible_projection.py`; project reads are projected by `docmancer/docs/interfaces/mcp/context_tools.py`. The project-read boundary is defined in [ADR 0003](./adr/0003-context-first-project-reads.md).
