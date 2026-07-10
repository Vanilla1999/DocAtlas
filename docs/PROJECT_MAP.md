# Project map

DocAtlas is a local-first documentation and context runtime for coding agents.
The user-facing CLI is `doc-atlas`; the Python package retains the
`docmancer` name for compatibility.

## Runtime areas

| Area | Location | Responsibility |
|---|---|---|
| CLI | `docmancer/cli/` | Installation, ingest, query, lifecycle and MCP commands |
| Documentation application | `docmancer/docs/application/` | Project, library and unified context workflows |
| Documentation domain | `docmancer/docs/domain/` | Ranking, trust, source identity and policy rules |
| MCP Docs server | `docmancer/mcp/docs_server.py` | Public documentation tools, resources and transport boundary |
| MCP Packs gateway | `docmancer/mcp/serve.py` | Advanced installed API-pack search and dispatch |
| Executors | `docmancer/mcp/executors/` | Capability-gated HTTP and Python execution |
| Connectors | `docmancer/connectors/` | Local and remote documentation acquisition |
| Evaluation | `eval/` | Retrieval and task-level benchmarks |
| Tests | `tests/` | Unit, contract, security and integration coverage |

## Default documentation flow

`get_docs_context(...)`
→ follow its returned `prepare_docs(...)` action when required
→ retry `get_docs_context(...)`

The index is derived state. Reviewable repository files remain the source of
truth for architecture, onboarding, runbooks and decisions.
`docs_status` is reserved for explicit health, freshness, index, and job
status requests.

## Security boundary

The Docs server is read-mostly and performs explicit confirmation for network
fetches. The Packs gateway can execute installed operations and therefore
applies integrity, host, credential, destructive-action and executor grants.
See `docs/security/mcp-runtime-threat-model.md`.
