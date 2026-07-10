# Project Patch Contract Runtime for coding agents

For patch-like tasks, use DocAtlas as a Patch Contract runtime, not only as docs search.

Required agent ritual:

1. Call `get_docs_context(question, project_path)` when task scope is unclear.
2. If the response has `next_action.name == "get_patch_constraints"`, call `get_patch_constraints` before editing.
3. Treat `forbidden_edits`, `source_of_truth_rules`, `dependency_contracts`, `suggested_checks`, and `unknowns/manual_review` as the pre-patch contract.
4. Edit code.
5. Call `validate_patch_against_constraints` with `changed_files` and/or `patch_diff`.
6. Report `violated` and `manual_review` constraints clearly.
7. Never claim the patch is safe-to-merge from DocAtlas validation alone; this output is advisory and does not replace tests or human review.

<!-- docmancer:start -->
# DocAtlas / docmancer

DocAtlas compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution, via MCP tools. The Python package is still named `docmancer` for compatibility.

MCP tools are available under the `docmancer-docs` server and the `docmancer-*` prefix in opencode.

Use docmancer when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, project architecture, conventions, runbooks, or wants to add docs before answering a technical question.

## Project‑owned docs workflow (preferred)

1. **`inspect_project_docs(project_path)`** — read‑only discovery; returns `reason_code`, `next_action`, `source_summary`.
2. **`prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)`** — reconcile index with filesystem: prune orphans, reindex changed, index new. Canonical lifecycle action on the public MCP surface.
3. **`get_docs_context(project_path=..., question=..., mode="project")`** — compact context pack with Trust Contract and source attribution.

Read `answer_outline.recommended_reading_order` when present. Prefer `trust_contract.selected_sources` or compatibility alias `trust_contract.selected` for citations. Context items expose both flat fields (`path`, `title`, `heading_path`, `freshness`) and nested fields (`source.path`, `source.title`, `section.heading_path`). Treat `CHANGELOG.md` as release-history evidence unless the user asks about changes/releases.

Use legacy `sync_project_docs`, `bootstrap_project_docs`, `get_project_docs`, or `get_project_context` only when they are explicitly exposed by a compatibility surface. The public docs MCP surface routes lifecycle through `prepare_docs(...)` and context through `get_docs_context(...)`.

## Library docs workflow

1. **`resolve_library_id(library)`** / **`get_library_docs(library, topic)`** — find and query registered library docs.
2. **`inspect_library_docs(canonical_id)`** — check what is indexed for one source.
3. **`refresh_library_docs(library, version?)`** — re‑fetch and re‑index.

## Dependency‑docs workflow (project‑specific)

```
prefetch_project_dependency_docs(project_path)
```

Ask the user first — this fetches from the network based on manifests/lockfiles.

## Compact MCP responses

All project‑docs tools return compact JSON by default. Pass `details: true` for the full response.

**sync_project_docs**:
```json
{
  "status": "success",
  "summary": { "current": 3, "new": 1, "changed": 0, "orphaned": 0,
    "orphaned_removed": 1, "dedup_removed": 0, "stale_removed": 0,
    "sections_indexed": 24 }
}
```

**inspect_project_docs**:
```json
{
  "reason_code": "project_docs_ready",
  "next_action": { "type": "get_docs_context", "tool": "get_docs_context" },
  "source_summary": { "candidates": 4, "indexed": 4, "stale": 0, "ignored": 0 }
}
```

**prepare_docs(action="sync_project_docs")**:
```json
{
  "status": "ready",
  "reason_code": "project_docs_ready",
  "next_action": { "type": "get_docs_context", "tool": "get_docs_context" },
  "actions_taken": ["inspect", "sync"]
}
```

**get_docs_context(mode="project")**:
```json
{
  "answer_available": true,
  "mode": "auto",
  "trust_contract": { "selected": [...], "rejected": [...], "risky": [...] },
  "next_actions": []
}
```

## CLI (fallback when MCP tools are unavailable)

```bash
doc-atlas list
doc-atlas query "question"
doc-atlas ingest ./docs
doc-atlas add https://docs.example.com
doc-atlas doctor
```

`doc-atlas query` prints token savings and agentic runway. Use `--expand` for adjacent sections.

Always query docmancer before relying on model memory or latest‑only hosted docs when documentation context is relevant.
<!-- docmancer:end -->
