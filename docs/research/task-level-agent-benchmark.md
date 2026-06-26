# Task-Level Agent Benchmark Research Note

Date: 2026-06-25

Question: under the same coding model, agent harness, task, budget, and tools, does DocAtlas produce statistically and practically better patches than no docs retrieval and Context7?

Current answer: not yet measured causally. The repository had retrieval/live benchmark infrastructure, but not an independent task-level patch harness. A pilot harness and 8 curated task specs were added under `eval/task_level/`.

Important guardrail: retrieval quality, prettier context, Hit@1, and snippet count are not success metrics. The primary metric is whether the patch resolves the task and passes tests.

Environment observed during setup:

- DocAtlas commit: `80fc06c748dc20406e10c1e2d4e391c1939cce05`
- Branch: `research/task-level-agent-benchmark`
- Python: `Python 3.14.3` available as `python3`; project metadata supports `<3.14`
- OS: Ubuntu Linux kernel `6.17.0-35-generic` on x86_64
- Docker: `Docker version 29.3.1, build c2be9cc`
- OpenCode: `1.17.11`
- Claude Code: `2.1.138`
- Context7 MCP: available via current MCP tool schema; package version not exposed by the tool interface
- Benchmark timestamp: generated per run in `metadata.json`

Current DocAtlas checks performed:

- `inspect_project_docs` reported stale project docs; `sync_project_docs` reconciled without repo writes.
- `get_project_context` returned project context with Trust Contract and selected source attribution.
- `get_library_docs` for FastAPI returned snippet-first output and exact-version diagnostics warning that no project-pinned version was found, so latest/default docs were used.
- `get_docs_context` route was exercised with snippet-first style; output was large but successful.

Runner availability:

- `mini-SWE-agent`, `SWE-agent`, and `OpenHands` CLI were not found.
- `opencode run` and `claude -p` headless modes are installed.
- A SWE-style runner with verified condition tool isolation, fresh storage, normalized trajectories, patches, token metrics, and tool-call metrics has not yet been proven in this environment.

Pilot fixture update:

- `fastapi_depends_001` is materialized with pinned `fastapi==0.111.0`, public tests, evaluator-only hidden tests, and a gold patch.
- `mixed_fastapi_project_001` is materialized with pinned `fastapi==0.103.2`, project security/API-error docs, public tests, evaluator-only hidden tests, and a gold patch.
- Both fixtures validate as base-fail/gold-pass in the local harness.
- Claude Code is preferred over OpenCode for the first pilot because its help exposes stream-json output, model selection, strict MCP config, and tool allow/deny flags.
- The live runner canary did not pass in this environment because Claude Code reported `Not logged in`; no causal four-run pilot was executed.

Decision for this setup phase: ITERATE_RUNNER. The materialized fixtures and adapters are ready, but no DocAtlas task-level patch success claim should be made until an authenticated runner canary produces a patch, passes tests, and passes policy audit.
