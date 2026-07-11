## DocAtlas documentation workflow

Use the default Docs MCP server as a three-tool router.

1. For a repository, library, dependency, or mixed documentation question, call `get_docs_context` first.
2. If it returns `next_action`, ask for any required network or write approval, then call the exact returned `prepare_docs` action.
3. Use `docs_status` only for explicit health, freshness, or index diagnostics, or when a returned job id needs progress or status.
4. After preparation succeeds, retry the original `get_docs_context` question unchanged.

Project documentation proves repository conventions and decisions. Dependency documentation proves external APIs. For current implementation facts, prefer repository code search. Do not use legacy direct documentation tools in this workflow.
