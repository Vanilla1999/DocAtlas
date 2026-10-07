# MCP delivery integration contract

Base: `2d060bf06904cc84a98b7de39f86529a94ea7c39`, PR #211.

## Product and authority

- One installed server, existing connection name preserved. Live replacement,
  reconnect, merge, publish and release version selection remain separately gated.
- Omitted/null format retains docs mode. Coding workflows explicitly request
  `context_format="patch_context"`; prose never selects a workflow or grant.
- V4 retained admitted evidence has no representation token/byte/count cap.
  Existing retrieval and issued resource I/O guards remain independent.
- Project preparation is an explicit confirmed, project/storage/catalog/member
  bound synchronous lexical upsert transaction. No orphan deletion, renames,
  deduplication, vectors, extraction publication or inferred authorization.
- Caller confirmation expresses intent, not authenticated issuer proof.
- Tests use isolated fixture indexes only; D1 stays exact 10 documents,
  `code_files=()`. No live provider calls or dependencies added.
- User expressly approved active contract-test migrations. Historical gold,
  thresholds, reports and evaluation suites remain protected. Gates are not
  disabled to manufacture green CI.

## Ownership

Separate worktrees `/tmp/opencode/mcp-delivery-{a,b,c}` share the fixed base.
No nested subagents. One owner per file; extensions require coordinator approval.

- A: project service parts 01/02, new member transaction module,
  MCP prefetch_tools, SQLite store part01, new member transaction tests/shard.
- B: MCP context_tools, grounded_mcp_session, host_context, runtime workflow
  contract, resources, tool-data/schema, template, model-visible projection
  and responsibility split modules, new consumer/workflow/split tests/shard,
  active tools-registration instruction expectations.
- C: stdio smoke, agent_config, install.sh, active registration/environment
  tests, new isolated installer/delivery tests/shard.
- Coordinator: agent parser-loading extraction and agent.py size gate;
  CLI docs-impact early legacy-write denial; portable docs/agent_contract;
  content-trust/residual/CLI active tests; integration and scoped reports.
  Active dictionary-exit inert-security/public-request and NL-removal packet
  tests also migrate to v4 while retaining nonauthorization and binding checks.
- R: independent integrated review, no production edits.

Shared prepare_docs mutation schema belongs only to B. A supplies the DTO and
executor; C consumes the real lifecycle. Integrate A then B then C and test the
actual installed artifact, not injected retrieval.

## Acceptance reporting

Report source tests, installed stdio, CI and deployed parity separately.
Do not claim merge/release readiness while any required gate or lifecycle/
transport/security review remains open.
