## DocAtlas documentation workflow

Use the default Docs MCP server as a three-tool router:

- For a normal repository, library, dependency, or mixed documentation question, start with `get_docs_context`.
- Use `docs_status` only when the user explicitly asks about health, freshness, indexing, or background-job status.
- Use `prepare_docs` only when `get_docs_context` returns it as `next_action`, or when the user explicitly asks to sync, refresh, index, or prefetch documentation. Ask for approval before a network action.

Do not choose a lifecycle action speculatively. After a returned `next_action`, run the requested `prepare_docs` action and retry `get_docs_context`.

Keep evidence types separate: repository docs prove project conventions and decisions; dependency docs prove external APIs; source code proves the current implementation. Do not inject or rely on a generated full inventory of dependencies or documentation files.

If DocAtlas reports `documentation_gap`, ask for approval, inspect only its listed evidence, and create the proposed normal repository file. Do not invent project prose. After the file exists, call the returned `prepare_docs` sync action.
