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

Task fairness calibration (`task_fairness_review`):

- `fastapi_depends_001` now exposes the `require_token` dependency name and `token` route parameter convention in `docs/auth.md`.
- `mixed_fastapi_project_001` now exposes the `admin: Annotated[str, Depends(require_admin)]` route parameter convention in `docs/security.md` and dependency-raised `HTTPException` envelope handling in `docs/api-errors.md`.
- Fixture validation after calibration passed for both tasks: base expected tests fail, gold public tests pass, gold hidden tests pass, and oracle isolation remains true.

Recalibrated actionability pilot (`docatlas_actionability_pilot_recalibrated_001`):

- One completed 2-task x 4-condition x 1-repeat matrix was observed before a later metric-only rerun attempt was stopped; raw run directories are not committed.
- `fastapi_depends_001` resolved in all four conditions after the exact-form conventions became visible.
- `mixed_fastapi_project_001` resolved under `repo_only` and `docatlas_action_checklist_injected`; `docatlas_tool_recommended` and `docatlas_context_injected` did not resolve it in this single repeat.
- Checklist-injected runs used the checklist and surfaced the newly visible exact-form conventions.
- Because `repo_only` solved both tasks in this small recalibrated matrix, the result does not justify a DocAtlas improvement claim or an 8-task pilot.

Decision after recalibration: ITERATE_TASKS. The immediate issue shifted from unfair hidden contracts to weak differentiation: these two calibrated fixtures are now too solvable by repo-only in a single repeat to support causal DocAtlas claims.

Real-project suite expansion plan (`research/task-level-agent-benchmark`):

- Baselines are split into `repo_only_strict_offline` and `repo_only_web_audited`. Strict offline treats DocAtlas, Context7, web tools, and network shell probes as policy violations. Web-audited still forbids DocAtlas/Context7 but records web/network attempts separately for diagnostic leakage analysis.
- The real-project suite now targets three NBO-derived sanitized fixtures: `real_project_nbo_001`, `real_project_nbo_permission_002`, and `real_project_nbo_generated_source_001`.
- Each fixture uses minimal project docs/source/lockfile context and excludes git history, secrets, build output, dependency directories, and private remotes.
- Current allowed claim remains limited: DocAtlas can be reported as a positive signal only per real-project-derived fixture under policy-clean conditions. Do not claim broad agent improvement or robust vector retrieval from these fixtures alone.
- DocAtlas context-injected runs now record `docatlas_retrieval_status`, `vector_indexing_timed_out`, `fallback_used`, and `fallback_source` so fallback success is distinguishable from retrieval-path success.

Real-project suite pilot (`real_project_suite_pilot_002`):

- Matrix: `real_project_nbo_001`, `real_project_nbo_permission_002`, and `real_project_nbo_generated_source_001` x `repo_only_strict_offline`, `repo_only_web_audited`, `docatlas_tool_recommended`, and `docatlas_action_checklist_injected` x 1 repeat = 12 runs.
- Artifact integrity was clean: `completed_runs=12`, `runs_jsonl_records=12`, `ok=true`.
- All four conditions resolved `3/3` with public and hidden tests passing, including `repo_only_strict_offline`.
- `docatlas_tool_recommended` adopted DocAtlas in all three tasks (`12` total agent DocAtlas calls) and was policy-clean after the policy audit false-positive for the domain word `browser` was fixed.
- `docatlas_action_checklist_injected` used checklist/context in all three tasks, but context injection still fell back to visible fixture project docs after vector indexing timeouts.
- Because strict offline solved every task, this pilot does not support a DocAtlas improvement claim. It indicates the new fixtures are fair and valid, but still too easy as differentiators.

Decision after `real_project_suite_pilot_002`: ITERATE_REAL_PROJECT_TASKS. Next fixtures should raise difficulty by requiring more distributed local context, less issue-text specificity, or stronger private/version traps while keeping every hidden requirement visible from project docs/source/public tests/lockfiles.

NBO source profile and hard-task design pass:

- A sanitized source project profile is recorded at `eval/task_level/results/source_project_profiles/nbo.md`.
- NBO is represented only as a Flutter/Dart mobile application with permission-module fixture scope. The benchmark does not disclose full application domain details, private business logic outside fixture scope, live repository history, credentials, private remotes, generated runtime/build outputs, or user/customer data.
- The existing NBO fixtures are reclassified as smoke/regression fixtures: they are fair, sanitized, and useful for runner/policy/artifact regressions, but `repo_only_strict_offline` resolved all three in pilot 002, so they are not differentiating proof-of-value tasks.
- The first hard-candidate design target is `real_project_nbo_distributed_permission_policy_001`, because it combines distributed project docs, correct-layer constraints, pinned `permission_handler` context, browser/scan preflight policy, and tempting wrong locations.
- Candidate tasks must pass a screening gate before full pilot: `repo_only_strict_offline` over 2 repeats, with acceptance only when strict offline resolves `<= 1/2`, fairness is clean, base fails, gold passes, hidden requirements are discoverable, and artifact integrity is clean.
- If strict offline resolves `2/2`, the candidate is rejected as too easy. If hidden requirements require oracle-only information or the public tests do not exercise the intended behavior, the candidate is rejected as unfair.
- Current diagnosis remains `ITERATE_REAL_PROJECT_TASKS`; next implementation step is `READY_TO_IMPLEMENT_HARD_CANDIDATE`, not a DocAtlas improvement claim.

NBO distributed permission candidate implementation:

- `real_project_nbo_distributed_permission_policy_001` was added as the first hard candidate fixture.
- The issue text is symptom-style and does not directly reveal `Permission.notification`, `PermissionService`, generated-file restrictions, or pinned dependency details.
- The intended solution requires combining visible README, module architecture, notification policy docs, browser/scan preflight docs, service/provider source, generated-file stubs, and the pinned `pubspec.lock` context.
- Screening rule remains unchanged: run `repo_only_strict_offline` for 2 repeats and reject the candidate as too easy if strict offline resolves `2/2`.
- Validation passed for the implemented candidate, but screening rejected it as too easy: `repo_only_strict_offline` resolved `2/2`, policy-clean, with zero network attempts and clean artifact integrity.
- Full 4-condition pilot was not run for this candidate. The diagnosis remains `ITERATE_TASK_DESIGN` for harder NBO-derived tasks.

NBO cross-module permission candidate implementation:

- `real_project_nbo_cross_module_permission_contract_001` was added as the next hard candidate after the distributed permission-policy candidate was rejected as too easy.
- The task targets inconsistent permission gating between browser and scan flows. The issue text describes symptoms and does not directly instruct agents to edit service/gate/generated files.
- The intended context spans README, permission architecture docs, browser docs, scan docs, generated-file policy, permission service, and two flow gates.
- Validation passed for the cross-module candidate, but screening also rejected it as too easy: `repo_only_strict_offline` resolved `2/2`, policy-clean, with zero network attempts and clean artifact integrity.
- Full 4-condition pilot was not run for this candidate. The diagnosis remains `ITERATE_TASK_DESIGN`.
