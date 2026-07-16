# DocAtlas agent contract

DocAtlas is a local-first documentation router for coding agents. It grounds answers in project-owned files and exact dependency evidence while keeping source attribution visible.

<!-- docmancer:start -->
## Public Docs MCP tools

The default `doc-atlas mcp docs-serve` surface has exactly three tools:

1. `get_docs_context` — for coding and patch tasks, call it once before the first edit; the server returns bounded structured context by default. Use broader compatibility output only for explicit documentation exploration.
2. `prepare_docs` — for bounded delivery, call only from `recommended_next_action`; unbounded compatibility output may use `next_action`. Explicit user sync, refresh, index, or prefetch requests are also allowed. Network actions require approval.
3. `docs_status` — use only for an explicit health, freshness, index, or background-job status request.

Do not guess a lifecycle action before querying context. For a normal repository question:

```text
get_docs_context(question=..., project_path=...)
→ follow returned prepare_docs recommended_next_action when present
→ retry the same bounded get_docs_context only after successful preparation
→ answer from selected sources and navigation guidance
```

Inspect canonical result `status` and `kind`. Stop before editing on `insufficient_evidence`; for `patch_context`, cite `sources` through factual `evidence_ids`. Only an explicit compatibility/advanced exploration path exposes broader `answer_outline`, `trust_contract`, and `context_pack`. Project docs prove repository decisions and conventions; dependency docs prove external APIs; source code proves current implementation.

Advanced compatibility tools such as patch planning, constraints, validation, and low-level inspection are available only when `DOCMANCER_MCP_ADVANCED_TOOLS=1`. Legacy direct project-doc verbs require their separate compatibility flag. New agent instructions must target the three-tool public surface.

MCP Packs are a separate advanced API-action surface exposed by `doc-atlas mcp packs-serve`; they are not the default documentation workflow.

## CLI fallback

When MCP tools are unavailable:

```bash
doc-atlas list
doc-atlas query "question"
doc-atlas ingest ./docs
doc-atlas add https://docs.example.com
doc-atlas doctor
```

Always prefer source-grounded DocAtlas context over model memory or latest-only hosted docs when documentation is relevant.
<!-- docmancer:end -->
