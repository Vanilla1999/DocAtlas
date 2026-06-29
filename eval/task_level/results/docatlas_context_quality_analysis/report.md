# DocAtlas Context Quality Failure Analysis

Source runs:

- `docatlas_recommended_pilot_001`
- `docatlas_recommended_pilot_002`

Condition analyzed:

- `docatlas_tool_recommended`

Tasks analyzed:

- `fastapi_depends_001`
- `mixed_fastapi_project_001`

This report is sanitized. It records derived facts from patches, public/hidden outcomes, DocAtlas calls, context packs, Trust Contracts, and agent messages. It does not include raw trajectories, workspace dumps, gold patches, or hidden test source.

## Executive Diagnosis

The recommended workflow fixed DocAtlas adoption but not task success.

| condition | analyzed runs | DocAtlas calls | context used | resolved |
| --- | ---: | ---: | --- | ---: |
| `docatlas_tool_recommended` | 4 | 2-6 per run | true | 0/4 |

Primary diagnosis:

```text
DocAtlas context was relevant but not sufficiently action-directing for hidden-contract success.
```

The failures are not generic retrieval failures. They are actionability failures at the boundary between high-level project docs, visible code, FastAPI implementation details, and hidden evaluator introspection.

## Contract Coverage

| task | requirement | in DocAtlas context | salient | used by agent | patch correct |
| --- | --- | --- | --- | --- | --- |
| fastapi_depends_001 | `require_token` exact function name | false | false | false | false |
| fastapi_depends_001 | route parameter `token` | false | false | false | false |
| fastapi_depends_001 | `Annotated[..., Depends(...)]` dependency metadata | partial | low | true | partial |
| fastapi_depends_001 | `X-Token` header dependency | true | medium | true | true |
| fastapi_depends_001 | HTTP 401 for missing token | true | medium | true | true |
| fastapi_depends_001 | no audit on failed auth | true | medium | true | true |
| mixed_fastapi_project_001 | route in `src/app/main.py` | true | high | true | true |
| mixed_fastapi_project_001 | shared `require_admin` dependency | true | high | true | true |
| mixed_fastapi_project_001 | route parameter `admin` | false | false | false | false |
| mixed_fastapi_project_001 | `Annotated[str, Depends(require_admin)]` | false | false | false | false |
| mixed_fastapi_project_001 | no duplicate auth logic | true | high | true | true |
| mixed_fastapi_project_001 | documented error envelope | true | high | true | partial |
| mixed_fastapi_project_001 | `HTTPException` handler for dependency-raised 403 | false | false | false | false |

## Failure Classes

### fastapi_depends_001

Primary:

```text
context_missing_critical_contract
```

Secondary:

```text
agent_used_context_incompletely
task_hidden_contract_too_brittle
public_tests_too_weak
```

The DocAtlas response surfaced the behavioral contract from README: reject missing `X-Token`, share a dependency, and enqueue audit logging with `BackgroundTasks` after successful requests. It did not contain the exact dependency function name or route parameter name that hidden introspection required. Agents produced behaviorally plausible solutions that passed public tests but failed hidden exact-name checks.

### mixed_fastapi_project_001

Primary:

```text
context_present_but_not_salient
```

Secondary:

```text
snippet_missing_required_constraint
project_constraint_missing
library_api_present_but_project_contract_missing
public_tests_too_weak_for_signature_shape
task_hidden_contract_too_brittle
```

The DocAtlas responses selected the right project docs and agents used several constraints: `src/app/main.py`, `require_admin`, no duplicate auth logic, and error envelope. However, context did not state the implementation-critical FastAPI shape: an introspectable route parameter using `Annotated[str, Depends(require_admin)]`, parameter name `admin`, and an `HTTPException` exception handler for dependency-raised 403s. In one run, the primary snippet was the JSON error envelope, which made the output relevant but not directive enough.

## Context Quality Diagnosis

Missing critical facts:

- `fastapi_depends_001`: exact `require_token` symbol name.
- `fastapi_depends_001`: exact route parameter name `token`.
- `mixed_fastapi_project_001`: exact `admin: Annotated[str, Depends(require_admin)]` dependency parameter form.
- `mixed_fastapi_project_001`: `HTTPException` handler target for dependency-raised 403 errors.

Buried facts:

- `mixed_fastapi_project_001`: security constraints were present in the context pack, but primary snippet favored the JSON error envelope.
- `mixed_fastapi_project_001`: docs said to use `app.errors` helper, but context did not connect that to the current integer-status exception handler not catching dependency `HTTPException` reliably.

Misprioritized snippets:

- `mixed_fastapi_project_001`: `docs/api-errors.md` JSON was chosen as primary despite the route/dependency implementation being the highest-risk part of the task.

Too much/noisy context:

- No evidence that volume alone caused failure. The larger problem was absence of an actionable checklist and missing implementation constraints.
- Generic warnings about unrelated ecosystem files appeared in some responses and are not useful for Python fixtures.

Wrong sources:

- No clearly wrong selected project sources. Selected project docs were relevant but incomplete.
- Library docs were absent in these no-network runs; for `fastapi_depends_001`, a library snippet might have helped with `Annotated`/`Depends` mechanics but not with hidden project names.

## Task Quality Diagnosis

| task | fair task? | brittle hidden contracts | public test weaknesses | fixture/doc issues |
| --- | --- | --- | --- | --- |
| fastapi_depends_001 | Partially | Exact `require_token` and `token` names are not discoverable from public docs/prompt. | Public tests pass behaviorally correct patches with different names. | README should expose naming convention or hidden tests should avoid exact names. |
| mixed_fastapi_project_001 | Partially | Exact `Annotated` parameter form and `admin` name are not discoverable from docs. | Public tests catch error envelope but not signature shape; agents also struggled to run tests due environment. | Docs should say dependency should be a typed route parameter if that is required. |

## Offline Counterfactual

Improved context packets were drafted for each task from public docs and visible code only. They avoid gold patches and hidden test source.

Result:

- A reasonable agent would likely fix more behavioral/public-test issues with a top-level action checklist.
- The exact hidden names in `fastapi_depends_001` remain non-obvious without task/doc changes.
- The `mixed_fastapi_project_001` `HTTPException` handler is inferable from visible code plus FastAPI knowledge, but the exact `Annotated` parameter name/form remains non-obvious without stronger docs/tests.

## Recommended Next Path

Selected:

```text
ITERATE_CONTEXT_PRESENTATION
```

Reason: `mixed_fastapi_project_001` shows that relevant facts can be present but not directive enough. Adding an action checklist and implementation constraints section is the smallest benchmark-side/product-facing hypothesis to test next.

Secondary risk:

```text
ITERATE_TASKS
```

Reason: both tasks contain hidden exact-form requirements not fully discoverable from public docs/prompt. Before scaling, either public docs/tests should expose these conventions or hidden tests should avoid exact introspection details.

## Proposed Next PR

```text
feat: add action checklist to DocAtlas context packs
```

Minimum experiment design:

- Add an action-checklist presentation layer to context packs or benchmark-side diagnostic context.
- Prioritize project constraints before library snippets when project docs contain matching symbols.
- Surface exact names/signatures only when they are present in project docs or visible code, not from evaluator-only hidden tests.
- Rerun the two-task recommended matrix before making improvement claims.

## Claims

Can claim:

- Explicit DocAtlas workflow guidance causes this Codex runner to call DocAtlas/docmancer.
- Current context is relevant but not sufficiently action-directing for these hidden-contract tasks.
- Some failures are task/doc discoverability issues rather than retrieval failures.

Cannot claim:

- DocAtlas improves coding agents.
- DocAtlas beats `repo_only`.
- Actionability improvements improve task-level success before a new causal run.
