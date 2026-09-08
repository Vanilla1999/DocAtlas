## DocAtlas documentation workflow

Agent workflow contract schema: `docatlas-agent-contract-v1`  
Agent workflow contract identity: `{{DOCATLAS_AGENT_CONTRACT_ID}}`

Use the three-tool Docs MCP workflow with bounded structured results:

1. Start docs, coding, and patch tasks with `get_docs_context`; pass one concrete question as `question` and the repository root as `project_path`. Independent questions require separate `get_docs_context` calls. Never use a benchmark/evaluation or documentation-governance meta-question as `question`.
2. `lookup_queries` may only translate, paraphrase, or decompose the same question (max five, one concept each); never batch independent questions.
3. Use `prepare_docs` only from `recommended_next_action` or an explicit docs-lifecycle request. Use `docs_status` only for explicit status/health/freshness/job requests or a returned action.
4. Scope explicitly: onboarding/cross-module -> `scope="all"`; repo policy -> `scope="project"`; one known module -> `scope="module"` plus exact `module_path`. Preserve explicit scope; never widen `project` to `all`. For mixed module/repo proof, prefer two calls.
5. After preparation retry the original question unchanged; follow at most one returned non-automatic `rephrase_question`.
6. On `insufficient_evidence`, do not claim support. Continue local recovery when `hard_stop=false`. Stop before editing only when `hard_stop=true`.

Project docs prove repository conventions, dependency docs external APIs, and code current implementation. Partial coverage never authorizes edits. Do not use legacy direct documentation tools.
