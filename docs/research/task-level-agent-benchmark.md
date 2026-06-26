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
- Claude Code was rejected for live execution because it reported `Not logged in` during canary.
- Codex CLI was selected for live execution because `codex exec` exposes JSONL events, `--ephemeral`, `--cd`, model selection, and configured auth.
- Codex canary produced a real patch, passed pytest, saved trajectory, and denied the network probe through benchmark `curl`/`wget` wrappers.
- Codex `workspace-write` sandbox failed on this host with a `bwrap` loopback error, so the pilot uses `danger-full-access` plus policy/trajectory audit and blocked network command wrappers. This is a runner limitation, not a DocAtlas result.
- A 2-task x 2-condition x 1-repeat pilot was executed with Codex. `mixed_fastapi_project_001` resolved under `repo_only`; no run called DocAtlas, so there is no DocAtlas utilization evidence yet.

Decision for this setup phase: ITERATE_DOCATLAS. The runner can execute patches and the fixtures are valid, but the DocAtlas condition did not actually retrieve/use DocAtlas context in the pilot.

DocAtlas utilization iteration:

- `docatlas_snippet_first` remains accepted as a deprecated alias for `docatlas_tool_optional`.
- The next pilot matrix is `repo_only`, `docatlas_tool_optional`, `docatlas_context_injected`, and `docatlas_tool_required_once` over the same two validated fixtures.
- `docatlas_context_injected` records harness-side DocAtlas calls separately from agent-side adoption and injects a compact verified context pack rather than raw JSON.
- `docatlas_tool_required_once` is a diagnostic condition only: the agent must call the documentation-context tool once before the first edit, then use or ignore the result based on relevance.
- Policy audit now distinguishes agent DocAtlas calls, Context7 calls, web calls, network shell calls, foreign MCP calls, and whether the first DocAtlas call preceded the first edit.
- A `--verify-docatlas-tool` canary checks MCP discoverability before running a utilization pilot. If it cannot observe `get_docs_context`, the decision is `ITERATE_TOOL_DISCOVERABILITY`.
- The Codex MCP config now launches DocAtlas through `uv run --project <repo> doc-atlas mcp docs-serve`; a bare `doc-atlas` executable was not available in this environment.

The utilization pilot must not support a product claim unless DocAtlas context is actually retrieved, available to the agent or injected by the harness, and independently judged as used in a successful patch.

DocAtlas utilization pilot result (`docatlas_utilization_pilot_004`):

- The tool visibility canary verified that Codex can see and call `get_docs_context` through the generated DocAtlas MCP config.
- `docatlas_tool_optional` adoption was `0/2`: the agent did not call DocAtlas when the tool was merely available.
- `docatlas_tool_required_once` compliance was `2/2`: the agent called DocAtlas before editing in both diagnostic runs.
- Patch success was `1/2` for `docatlas_tool_required_once`, `0/2` for `repo_only`, `0/2` for `docatlas_tool_optional`, and `0/2` for `docatlas_context_injected` in this two-task pilot.
- The only resolved run was `fastapi_depends_001 x docatlas_tool_required_once`; it passed public and hidden tests with policy clean and DocAtlas context judged used.
- `mixed_fastapi_project_001` remained unresolved in every condition, so it may require task/evaluator or context-quality iteration before scaling.

Interpretation: optional tool availability is insufficient for this runner. The next condition adds a product-like `docatlas_tool_recommended` workflow instruction: use DocAtlas/docmancer documentation context before code changes when a task may depend on library APIs, exact versions, or project docs, then use or ignore the result based on relevance. This is distinct from the stricter diagnostic `docatlas_tool_required_once` condition.

Current decision: ITERATE_TOOL_DISCOVERABILITY. Do not claim DocAtlas improves coding agents from this pilot; the supported claim is that this runner may require explicit workflow guidance to adopt DocAtlas.

Recommended-workflow follow-up (`docatlas_recommended_pilot_001` and `docatlas_recommended_pilot_002`):

- Matrix: `fastapi_depends_001` and `mixed_fastapi_project_001` x `repo_only` and `docatlas_tool_recommended` x 2 observed repeats.
- `docatlas_tool_recommended` fixed adoption: every recommended run called DocAtlas (`2-6` agent DocAtlas calls per run) and context was judged used.
- Patch success did not improve: `docatlas_tool_recommended` resolved `0/4`; `repo_only` resolved `1/4`.
- `fastapi_depends_001` failure class under recommended: agents used `Annotated`, `Depends`, and `BackgroundTasks`, but missed hidden contract details such as the exact shared dependency name (`require_token`) and/or route parameter name (`token`) required for introspection.
- `mixed_fastapi_project_001` failure class under recommended: agents found and used `require_admin`, but missed the exact project convention implementation: the route dependency needed `Annotated[str, Depends(require_admin)]`, and the app needed an `HTTPException` handler so the documented error envelope applied to dependency-raised 403 errors.
- This means the benchmark has moved past pure tool discoverability: DocAtlas can be discovered and used when recommended, but the returned/used context is not yet sufficiently action-directing for these hidden-contract tasks.
- `mixed_fastapi_project_001` remains unresolved by all tested conditions, which may indicate the task is too brittle, the public tests are not steering enough, or DocAtlas context formatting does not emphasize the critical convention.

Final decision for this phase: ITERATE_DOCATLAS_CONTEXT_QUALITY. Secondary risk: ITERATE_TASKS for `mixed_fastapi_project_001` before any larger 8-task pilot. No product claim is supported.

Context-quality failure analysis artifact: `eval/task_level/results/docatlas_context_quality_analysis/report.md`.

Diagnosis summary:

- `fastapi_depends_001`: context surfaced behavior but missed hidden exact-name contract (`require_token`, route parameter `token`). This is primarily a task/doc discoverability issue; context presentation cannot infer names absent from public docs without leaking evaluator-only details.
- `mixed_fastapi_project_001`: context selected relevant project docs and agents used `require_admin`, module placement, and envelope facts, but context did not provide an action checklist for the FastAPI-specific implementation shape (`Annotated[str, Depends(require_admin)]`, route parameter `admin`, `HTTPException` handler for dependency-raised 403). This supports context presentation iteration, with secondary task/doc brittleness risk.

Next recommended experiment: ITERATE_CONTEXT_PRESENTATION via an action-checklist section that prioritizes project constraints and visible-code implementation hazards before library snippets. Do not claim improvement until a new causal run passes the benchmark decision rule.

Actionability checklist pilot (`docatlas_actionability_pilot_001`):

- Matrix executed: `fastapi_depends_001` and `mixed_fastapi_project_001` x `repo_only`, `docatlas_tool_recommended`, `docatlas_context_injected`, `docatlas_action_checklist_injected` x 1 repeat = 8 runs.
- `docatlas_action_checklist_injected` injected 4 checklist items for `fastapi_depends_001` and 5 for `mixed_fastapi_project_001`; checklist usage was detected in both checklist runs.
- Resolved did not improve: all four conditions resolved `0/2` in this pilot.
- Contract scores did not improve over baselines: `fastapi_depends_001` remained behavior=1.0, form=0.6667, project=1.0 across all conditions; `mixed_fastapi_project_001` checklist remained behavior=1.0, project=1.0 but form=0.0, worse than the repo-only/recommended form score of 0.3333.
- Token/time overhead was not the blocker: checklist injection used fewer input tokens than full context or recommended tool use in this run, but did not improve correctness.
- The checklist correctly excluded hidden-only exact requirements (`require_token`, route parameter `token`, `admin: Annotated[...]`), so the remaining failures are mostly not fixable by oracle-free presentation alone.

Decision after actionability pilot: ITERATE_TASKS. Secondary follow-up: make the checklist/directive workflow more explicit only after task contracts are made discoverable from public docs/tests. No task-level improvement claim is supported.
