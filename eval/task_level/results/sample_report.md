# Sample Task-Level Report

No causal benchmark results are committed.

Current pilot scaffold status:

- two materialized FastAPI fixtures are available;
- fixture validation requires base-fail and gold public+hidden pass;
- Codex is the preferred adapter because it exposes `exec --json --ephemeral`, model selection, sandbox modes, and configured auth;
- Codex canary produced a real patch and passing test, with network probe denied by benchmark wrappers;
- kernel-level `workspace-write` sandbox failed on this host, so network enforcement is `policy_and_trajectory_audit` plus blocked `curl`/`wget` wrappers.

Example commands:

```bash
uv run python -m eval.task_level.runner --materialize --validate --tasks fastapi_depends_001 mixed_fastapi_project_001
uv run python -m eval.task_level.runner --verify-runner --runner codex --model gpt-5.5
uv run python -m eval.task_level.runner --execute --runner codex --model gpt-5.5 --tasks fastapi_depends_001 mixed_fastapi_project_001 --conditions repo_only docatlas_snippet_first --repeats 1 --run-id pilot_001
```

Latest sanitized utilization findings:

- DocAtlas MCP visibility is verified for Codex when launched through `uv run --project <repo> doc-atlas mcp docs-serve`.
- Optional availability alone produced zero adoption in the two-task utilization pilot.
- A strict diagnostic `docatlas_tool_required_once` condition produced one resolved run out of two, but it is not a product-default condition.
- A softer `docatlas_tool_recommended` condition fixed adoption (`2-6` DocAtlas calls per run across two repeats) but resolved zero out of four recommended runs.
- Observed failure classes were implementation-contract misses, not tool access failures: FastAPI auth patches missed hidden introspection names, and mixed project patches missed the exact `Annotated` dependency plus `HTTPException` error-envelope convention.

Current decision:

```text
ITERATE_DOCATLAS_CONTEXT_QUALITY
```

Secondary risk: `mixed_fastapi_project_001` may need task/public-test/context-quality iteration before scaling.

## Actionability checklist pilot

Run:

```text
docatlas_actionability_pilot_001
```

Matrix:

```text
2 tasks x 4 conditions x 1 repeat = 8 runs
conditions: repo_only, docatlas_tool_recommended, docatlas_context_injected, docatlas_action_checklist_injected
```

Sanitized result table:

| task | condition | resolved | public | hidden | behavior | form | project | checklist_used |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fastapi_depends_001 | repo_only | false | true | false | 1.0 | 0.6667 | 1.0 | false |
| fastapi_depends_001 | docatlas_tool_recommended | false | true | false | 1.0 | 0.6667 | 1.0 | false |
| fastapi_depends_001 | docatlas_context_injected | false | true | false | 1.0 | 0.6667 | 1.0 | false |
| fastapi_depends_001 | docatlas_action_checklist_injected | false | true | false | 1.0 | 0.6667 | 1.0 | true |
| mixed_fastapi_project_001 | repo_only | false | false | false | 1.0 | 0.3333 | 1.0 | false |
| mixed_fastapi_project_001 | docatlas_tool_recommended | false | false | false | 1.0 | 0.3333 | 1.0 | false |
| mixed_fastapi_project_001 | docatlas_context_injected | false | false | false | 1.0 | 0.0 | 1.0 | false |
| mixed_fastapi_project_001 | docatlas_action_checklist_injected | false | false | false | 1.0 | 0.0 | 1.0 | true |

Checklist impact:

- Resolved delta: no improvement.
- Contract score delta: no improvement; mixed form score decreased versus repo-only/recommended in this single repeat.
- Checklist usage: detected for both checklist runs.
- Token overhead: checklist condition was lower-token than recommended tool-use and full context injection in this run, so verbosity/cost was not the observed blocker.

Decision:

```text
ITERATE_TASKS
```

Reason: the checklist excluded hidden-only exact requirements by design, and those exact requirements remain the main failure mode. Public docs/tests should make required contracts discoverable or hidden tests should avoid brittle exact-form introspection before scaling.

## Task fairness calibration

Artifacts:

```text
eval/task_level/results/task_fairness_review/
```

Calibration changes:

- `fastapi_depends_001`: added visible `docs/auth.md` convention for `require_token`, `X-Token`, route parameter `token`, and no duplicated token validation.
- `mixed_fastapi_project_001`: expanded visible `docs/security.md` for route parameter `admin` and `admin: Annotated[str, Depends(require_admin)]`; expanded `docs/api-errors.md` for dependency-raised `HTTPException` envelope handling.

Validation:

```text
fastapi base expected tests fail: true
fastapi gold public+hidden pass: true
mixed base expected tests fail: true
mixed gold public+hidden pass: true
oracle isolation: true
```

Recalibrated pilot summary:

| task | condition | resolved | public | hidden | behavior | form | project | checklist_used |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fastapi_depends_001 | repo_only | true | true | true | 1.0 | 1.0 | 1.0 | false |
| fastapi_depends_001 | docatlas_tool_recommended | true | true | true | 1.0 | 1.0 | 1.0 | false |
| fastapi_depends_001 | docatlas_context_injected | true | true | true | 1.0 | 1.0 | 1.0 | false |
| fastapi_depends_001 | docatlas_action_checklist_injected | true | true | true | 1.0 | 1.0 | 1.0 | true |
| mixed_fastapi_project_001 | repo_only | true | true | true | 1.0 | 1.0* | 1.0 | false |
| mixed_fastapi_project_001 | docatlas_tool_recommended | false | false | false | 1.0 | 1.0* | 1.0 | false |
| mixed_fastapi_project_001 | docatlas_context_injected | false | false | false | 1.0 | 1.0* | 1.0 | false |
| mixed_fastapi_project_001 | docatlas_action_checklist_injected | true | true | true | 1.0 | 1.0* | 1.0 | true |

`*` The completed run used an earlier exact-decorator contract metric that reported mixed form as `0.6667` despite hidden tests passing. The evaluator was calibrated afterward to score the documented dependency exception envelope behavior instead of requiring a magic `HTTPException` decorator string; the heavy agent matrix was not rerun after that metric-only correction.

Decision:

```text
ITERATE_TASKS
```

Reason: the calibrated contracts are now visible, but `repo_only` solved both tasks in this single-repeat matrix, so the fixtures no longer differentiate DocAtlas/checklist value enough to justify scaling.
