<!-- docmancer:start -->
# DocAtlas repository instructions

DocAtlas provides local-first, source-attributed documentation context for coding work. Use the registered Docs MCP server; do not depend on a developer-machine executable path or a legacy CLI-first workflow.

## Docs MCP workflow

1. Call `get_docs_context` first for repository, dependency, library, or mixed documentation questions.
2. If it returns `prepare_docs` as `next_action`, ask for any required network approval and call that exact action and arguments.
3. Use `docs_status` only for a returned job, or an explicit health/freshness/index request.
4. Retry the original `get_docs_context` question after preparation completes and cite the selected sources.

Repository files are the source of truth. DocAtlas may index accepted documentation but must not silently author, commit, or push it. Use code search for implementation facts and DocAtlas for documentation context.

For command details, use `doc-atlas --help`, `doc-atlas mcp --help`, [AGENTS.md](../AGENTS.md), and [the Docs MCP reference](../docs/mcp-docs-server.md). MCP Packs and patch constraints are advanced/advisory surfaces, not the default workflow.
<!-- docmancer:end -->
