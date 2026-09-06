## DocAtlas documentation workflow

Agent workflow contract schema: `docatlas-agent-contract-v1`  
Agent workflow contract identity: `{{DOCATLAS_AGENT_CONTRACT_ID}}`

Use the three-tool Docs MCP workflow:

1. Start documentation, coding, and patch tasks with `get_docs_context`; pass the original request as `question` and the repository root as `project_path`. It returns bounded structured evidence. Never replace the request with a documentation-governance meta-question.
2. Call `prepare_docs` only from `recommended_next_action` or for an explicit documentation-lifecycle request. Call `docs_status` only for explicit status/health/freshness/job requests or a returned next action.
3. Choose scope explicitly. For onboarding or cross-module investigation use `scope="all"` without module filters. Use `scope="project"` for repo-level policy and `scope="module"` plus the exact `module_path` for one known module. Preserve explicit scope; never widen `project` to `all` after a miss. If one task needs module-local and repo-level proof, prefer two bounded calls.
4. After preparation, retry the original question unchanged; follow at most one returned non-automatic `rephrase_question`. Use at most five single-concept `lookup_queries`; partial coverage is not completeness and never authorizes edits.
5. On `insufficient_evidence`, do not claim support. Follow returned local recovery when `hard_stop=false`. Stop before editing only when `hard_stop=true`.

Project docs prove repository conventions, dependency docs prove external APIs, and repository code proves current implementation. Do not use legacy direct documentation tools. Treat project-doc catalog metadata as routing data; do not invent missing documentation or claims.
