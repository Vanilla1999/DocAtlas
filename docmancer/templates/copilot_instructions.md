# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

Use docmancer when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.

## Workflow

1. Run `doc-atlas list` to see indexed docs.
2. Run `doc-atlas query "question"` when relevant docs are present.
3. If local docs are missing and the user approves the path, run `doc-atlas ingest <path>`.
4. If URL docs are missing and the user approves the source, run `doc-atlas add <url>`.
5. Use the returned sections as source-grounded context for the answer or code change.

## Core Commands

```bash
doc-atlas setup
doc-atlas ingest ./docs
doc-atlas add https://docs.example.com
doc-atlas update
doc-atlas query "how to authenticate"
doc-atlas query "how to authenticate" --limit 10
doc-atlas query "how to authenticate" --expand
doc-atlas query "how to authenticate" --expand page
doc-atlas query "how to authenticate" --format json
doc-atlas query "how to authenticate" --allow-degraded
doc-atlas clear --dry-run
doc-atlas list
doc-atlas inspect
doc-atlas remove <source>
doc-atlas doctor
doc-atlas fetch <url> --output <dir>
```

`query` prints estimated raw docs tokens, context-pack tokens, percent saved, and agentic runway. Prefer the compact default. Use `--expand` for adjacent sections; use `--expand page` only when the surrounding page is necessary. Use `--allow-degraded` in dense, sparse, or hybrid modes when vector retrieval is down or misconfigured and you still need lexical results.

When documentation context is relevant, do not rely only on model memory or latest-only hosted docs. Query docmancer first, then cite or summarize the relevant local sections in the response.
