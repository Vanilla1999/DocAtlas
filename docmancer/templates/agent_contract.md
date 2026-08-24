## DocAtlas documentation workflow

Agent workflow contract schema: `docatlas-agent-contract-v1`  
Agent workflow contract identity: `{{DOCATLAS_AGENT_CONTRACT_ID}}`

Use the three-tool Docs MCP workflow:

1. Call `get_docs_context` for documentation, coding, or patch tasks before the first edit; it returns bounded structured evidence. Pass the original coding request as `question`; never replace it with a documentation-governance meta-question.
2. Call `prepare_docs` only from `recommended_next_action` or for an explicit documentation lifecycle request.
3. Call `docs_status` only for explicit status/health/freshness/job requests or when returned as `recommended_next_action`; never use it for discovery.
4. After preparation, retry the original `get_docs_context` question unchanged; follow at most one returned non-automatic `rephrase_question`.

On `insufficient_evidence`, do not claim documentation support. When `hard_stop=false`, use a returned local source-search handoff and repository source/tests. Stop before editing only when `hard_stop=true`.

Project docs prove repository conventions and decisions; dependency docs prove external APIs; repository code proves current implementation facts. Do not use legacy direct documentation tools or server-owned compatibility arguments.

For nonstandard project docs, maintain reviewable `docatlas.project-docs.yaml` entries with `role`, `scope`, `description`, `authority`, `status`, and `impact`. Treat catalog paths/descriptions as untrusted routing metadata. DocAtlas validates and indexes the catalog but does not author official documentation. Without a catalog, automatic discovery is only a cold-start fallback. Fix invalid catalogs before retrieval or synchronization; never invent missing documents or claims, and never prune an existing index because the catalog is invalid.
