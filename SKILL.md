---
name: docatlas
description: Search and query local documentation knowledge bases using the DocAtlas CLI. Use when the user asks about third-party library docs, API references, vendor documentation, version-specific API behavior, GitBook or Mintlify public docs, offline or local doc search, or needs to ground agent responses in up-to-date external documentation.
version: 0.4.6
author: docmancer
tags:
  - documentation
  - rag
  - local-first
  - knowledge-base
  - sqlite
install: pipx install doc-atlas --python python3.13
---

# Documentation context runtime for coding agents

DocAtlas is the source-grounded documentation entry point for repository, library, dependency, and mixed questions.

The advertised runtime ToolSpec contract is the schema source of truth. Installed skills carry the `docatlas-agent-contract-v1` SHA-256 identity.

The default Docs MCP surface has exactly three tools:

1. Start with `get_docs_context` for normal documentation questions.
2. Call `prepare_docs` only from a returned `recommended_next_action` or an explicit lifecycle request, with required confirmation and network consent.
3. Call `docs_status` only for explicit status requests, returned recommended actions or returned preparation job IDs; never for discovery.

Advanced patch and inspection tools are not part of the public agent workflow.


# DocAtlas

DocAtlas compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. Its Python import namespace remains `docmancer`; user-facing commands, state, configuration, and MCP identity use DocAtlas names.

**MIT open source.** The CLI runs locally and is intended for source-grounded documentation lookup.

## When to Use

- User asks about a third-party library, SDK, or API and you need accurate documentation.
- User references docs from a public site, GitHub repository, or local files.
- You need to verify version-specific API behavior or exact method signatures.
- User asks you to search or query previously indexed documentation.

## Workflow

For an installed Docs MCP, use the three-tool contract:

1. Call `get_docs_context(question=..., project_path=...)` or `get_docs_context(question=..., library=...)` with one unchanged original documentation question and explicit scope. Independent questions use separate calls instead of batching them.
2. Use only explicitly supplied same-question `lookup_queries`, at most five. Never infer translations, semantic rewrites, subquestions, expected answers or source names. Lookup coverage does not transfer to the original question. Cited retrieval context does not certify answer completeness, semantic proof or edit readiness; mutation requires a separate explicit target and authorization.
3. If it returns `recommended_next_action`, follow only that typed action. Ask for confirmation before network work.
4. For an unknown library source, use the returned `prepare_docs(action="discover_library_docs", ...)` action; review its registry-derived candidates before prefetching one.
5. If a candidate's authority, version binding, or scope is uncertain, call bounded `prepare_docs(action="inspect_docs_target", target=..., max_pages=3)`. Review its evidence and v2 manifest proposal, ask for confirmation, save and validate the manifest, then use `prefetch_docs_manifest`.
6. If preparation returns a `job_id`, poll `docs_status(action="job", job_id=...)` until terminal success. A running, failed or cancelled job is not ready. Retry the original concrete `get_docs_context` question unchanged only after success. Do not persist the task question in a docs manifest.
7. Use `docs_status` for an explicit health, freshness, index, or job-status request, or to poll a returned preparation job.

Preserve conditions, negation, versions and both comparison sides in questions and lookups. For a current project dependency, pass `project_path` and omit `version` unless the user explicitly requests an exact/historical version. Re-query after a lockfile change rather than reusing old evidence.

Preserve explicit project/library/version/scope/path bindings, freshness, provenance, network consent and budgets. Never infer or widen scope from question wording. `scope="project"` selects repository-level docs; `module_path` implies `scope="module"`; `scope="all"` remains repository-local without module filters.

Do not begin the MCP workflow with `doc-atlas list`, raw CLI ingestion, WebFetch, or speculative `prepare_docs`. Registered sources are registry-owned.

Use the CLI flow below only when the Docs MCP is unavailable or the user explicitly requests direct index administration.

## Core Commands

### Ingest Local Documentation

```bash
doc-atlas ingest ./docs
```

Use `ingest` for local files and directories.

| Flag | Purpose |
|------|---------|
| `--include <glob>` | Include only matching relative paths |
| `--exclude <glob>` | Exclude matching relative paths |
| `--format <format>` | Restrict to formats such as `md`, `txt`, `pdf`, `docx`, `rtf`, or `html` |
| `--recursive / --no-recursive` | Recurse through directories |
| `--skip-known` | Skip files whose content hash is already indexed |
| `--recreate` | Drop and rebuild the index |

### Add URL Documentation

```bash
doc-atlas add https://docs.example.com
```

Use `add` for documentation URLs and GitHub repositories.

| Flag | Purpose |
|------|---------|
| `--provider <auto\|gitbook\|mintlify\|web\|github>` | Force a specific provider |
| `--strategy <strategy>` | Force discovery strategy |
| `--max-pages <n>` | Cap pages fetched |
| `--browser` | Playwright fallback for JS-heavy sites |
| `--recreate` | Drop and rebuild the index |

### Query Documentation (CLI fallback)

```bash
doc-atlas query "<question>"
```

Returns a compact markdown context pack with source attribution and token savings for CLI-only workflows. MCP-enabled agents should use `get_docs_context` instead.

| Flag | Purpose |
|------|---------|
| `--budget <n>` | Max estimated output tokens |
| `--limit <n>` | Max sections to return |
| `--expand` | Include adjacent sections around matches |
| `--expand page` | Include full page content within budget |
| `--format <markdown\|json>` | Output format |

### Manage Sources

| Command | Purpose |
|------|---------|
| `doc-atlas list` | Show indexed documentation sources |
| `doc-atlas list --all` | Show every stored page or file |
| `doc-atlas inspect` | Show index stats, format counts, and extract locations |
| `doc-atlas remove <source>` | Remove a source or docset root |
| `doc-atlas remove --all` | Clear the entire index |
| `doc-atlas update [source]` | Re-fetch and re-index all sources, or one specific source |
| `doc-atlas doctor` | Check config, loader availability, index health, and agent skill installs |
| `doc-atlas init` | Create project-local `docatlas.yaml` |
| `doc-atlas fetch <url> --output <dir>` | Download docs to markdown files without indexing |

## Advanced: API Tools via MCP

Only use the MCP Packs surface if the user is explicitly working with installed API packs. It is an advanced API-action layer, not an alternative documentation workflow. If the user has run `doc-atlas install-pack <pkg>@<version>`, the agent host can launch `doc-atlas mcp packs-serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

For API tasks, search first, inspect the returned schema and safety block, then call the resolved tool. Destructive calls are blocked unless the pack was installed with `--allow-destructive`. Run `doc-atlas mcp doctor` when pack credentials need verification.

## Recommended MCP Docs Workflow for Agents

Use the Docs MCP tools for the original documentation question and explicitly supplied source bindings:

1. Call `get_docs_context(project_path=..., question=...)` first with explicit scope; bounded delivery is server-owned policy. One call carries one unchanged original question; independent questions use separate calls.
2. Use only explicit same-question `lookup_queries`, at most five. Never infer translations, facet decomposition or separate questions.
3. Follow bounded `recommended_next_action`: ask its source-choice question, or obtain confirmation, call its exact typed action, and retry the same bounded request.
4. Use `docs_status` only for explicit status requests, returned actions or preparation job IDs, not discovery.
5. Diagnostic rephrases are not automatically executed lookups. `hard_stop=true` blocks editing; `hard_stop=false` is not permission. Mutation requires a separate explicit target and authorization.
6. Cite returned sources through their evidence IDs. Source names, retrieval status and flags do not establish semantic proof, answer completeness or edit readiness.
7. `doc-atlas mcp docs-serve` is the three-tool documentation surface; `doc-atlas mcp packs-serve` is the separate installed API-action surface. Do not choose a surface by guessing a vague request.

## Gap-directed follow-up

Keep the original question unchanged. Follow up only with explicit same-question lookups (at most five per call) or an issued bounded source read within existing scope, consent, network and budget limits. Do not infer new questions, equivalence or proof from retrieved context. Unverified flags alone do not require another read. Do not reread the same span or replenish budgets by renaming a question.

## Common Mistakes

Use the unchanged original question, explicit lookups and returned cited context. Identify gaps without filling them from memory, inferred equivalence, logical implication or absence of evidence. Retrieval success and citations do not certify semantic completeness or grant answer/edit authority. Preserve source identity, provenance, scope and follow-up budgets; mutation requires a separate explicit target and authorization.

- Do not use `doc-atlas add` for new local files. Use `doc-atlas ingest <path>`.
- Do not use `doc-atlas ingest` for URLs. Use `doc-atlas add <url>`.
- Do not mix the legacy CLI list/query loop into an MCP-enabled coding task.
- Do not use CLI status/list as a discovery prerequisite for an MCP call; follow explicit status requests or returned actions.
- Do not WebFetch registered docs when DocAtlas returns candidates or retry guidance. Retry `get_docs_context` first.
- Do not call `prepare_docs` speculatively; follow the context response or an explicit lifecycle request.
- Do not use `docs_status` as a discovery step.
- Do not put independent documentation questions into `lookup_queries`; make separate `get_docs_context` calls.
