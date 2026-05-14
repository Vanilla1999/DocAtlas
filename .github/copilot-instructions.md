<!-- docmancer:start -->
# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. Docs are fetched from public sites, indexed locally with SQLite FTS5, and returned as compact context packs with source attribution. No API keys, no vector database, no background daemons on the core path.

**MIT open source.** Everything runs locally. The core path has no API keys, no vector database, and no background daemon.

Executable: `/Users/gaurangtorvekar/Documents/coding/personal/kytona_stuff/devrel/docmancer_stuff/docmancer/.venv/bin/docmancer --config /private/var/folders/fj/87wdckpn2j7fhjysk511vt3m0000gn/T/docmancer-live-cli.3FUAhO/project/docmancer.yaml`

**All commands below use `docmancer` as shorthand for the full executable path above.**

Use docmancer when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.

## Workflow

1. Run `docmancer list` to see indexed docs.
2. Run `docmancer query "question"` when relevant docs are present.
3. If docs are missing and the user approves the source, run `docmancer add <url-or-path>` to index it locally.
4. Use the returned sections as source-grounded context for the answer or code change.

## Core commands

```bash
docmancer setup
docmancer add https://docs.example.com
docmancer add ./docs
docmancer update
docmancer query "how to authenticate"
docmancer query "how to authenticate" --limit 10
docmancer query "how to authenticate" --expand
docmancer query "how to authenticate" --expand page
docmancer query "how to authenticate" --format json
docmancer list
docmancer inspect
docmancer remove <source>
docmancer doctor
docmancer fetch <url> --output <dir>
```

`query` prints estimated raw docs tokens, context-pack tokens, percent saved, and agentic runway. Prefer the compact default. Use `--expand` for adjacent sections; use `--expand page` only when the surrounding page is necessary.

`add` supports documentation URLs, GitHub repositories with README and docs markdown, local directories, markdown files, and text files. Extracted markdown/json remains inspectable under the configured `.docmancer/extracted` directory.

When documentation context is relevant, do not rely only on model memory or latest-only hosted docs. Query docmancer first, then cite or summarize the relevant local sections in the response.
<!-- docmancer:end -->
