# fastapi_depends_001 Context Quality Analysis

Scope: failed `docatlas_tool_recommended` runs from `docatlas_recommended_pilot_001` and `docatlas_recommended_pilot_002`.

This file is sanitized derived analysis. It does not include raw trajectories, workspace dumps, gold patch content, or hidden test source.

## Runs

| run_id | public | hidden | DocAtlas calls | DocAtlas tools | agent edits | primary failure |
| --- | --- | --- | ---: | --- | --- | --- |
| docatlas_recommended_pilot_001 | pass | fail | 2 | `get_docs_context` | `src/app/main.py`, `tests/test_auth_audit.py` | `context_missing_critical_contract` |
| docatlas_recommended_pilot_002 | pass | fail | 4 | `inspect_project_docs`, `get_project_context` | `src/app/main.py`, `tests/test_auth_audit.py` | `context_missing_critical_contract` |

## Hidden-Contract Requirements

Evaluator-only contract terms:

| requirement | rationale |
| --- | --- |
| Dependency function is named `require_token` | Hidden introspection checks for a shared dependency symbol with this name. |
| Route dependency parameter is named `token` | Hidden introspection reads `read_user` type hints by parameter name. |
| Route dependency uses `Annotated[..., Depends(...)]` | Hidden introspection checks dependency metadata on the route parameter. |
| Header reader accepts `x_token` / `X-Token` | Contract requires FastAPI header dependency rather than query parameter or inline route parsing. |
| Unauthorized requests do not record audit events | Background audit must run only after successful requests. |
| Successful requests preserve response shape | `TestClient` response remains `{"user_id": id, "status": "ok"}`. |

The exact symbol and route parameter names are not in the public issue text or fixture README.

## DocAtlas Questions And Responses

### docatlas_recommended_pilot_001

Question asked:

> For FastAPI in this project, what is the correct pattern to define a reusable dependency using Annotated and Depends, raise HTTP 401 for a missing X-Token header, use BackgroundTasks to enqueue work only after successful requests, and test this with TestClient?

Response shape:

| field | observed |
| --- | --- |
| status | `partial_success` |
| primary content | Project README only |
| library docs | Rejected/risky because network confirmation was required and `allow_network=false` |
| Trust Contract | Selected `README.md`; rejected/risky FastAPI dependency docs |
| primary snippet | None beyond README text |
| key project constraint surfaced | Reject missing `X-Token`; share token dependency; use `BackgroundTasks` after success |
| key missing constraints | `require_token`, route parameter `token`, exact `Annotated[..., Depends(require_token)]` shape |

### docatlas_recommended_pilot_002

Question asked:

> In this repository, how should the user API implement FastAPI dependencies with Annotated/Depends, reject missing X-Token as HTTP 401, and use BackgroundTasks for audit logging? Also mention relevant TestClient testing patterns.

Response shape:

| field | observed |
| --- | --- |
| status | `not_indexed` for the attempted `get_project_context` call |
| primary content | None from DocAtlas on that call |
| Trust Contract | Empty selected sources; next action recommended `sync_project_docs` |
| primary snippet | None |
| key project constraint surfaced | None through trusted context; agent later read README via shell |
| key missing constraints | All hidden contract details were absent from returned DocAtlas context |

## Contract Coverage

| requirement | present_in_docatlas_context | present_in_primary_snippet | present_in_context_pack | present_in_project_docs | present_in_library_docs | agent_mentioned_it | patch_implemented_it | test_failed_because_missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `require_token` exact function name | false | false | false | false | false | false | false | true |
| route parameter name `token` | false | false | false | false | false | false | false | true |
| `Annotated[..., Depends(...)]` dependency metadata | partial | false | partial in agent question, not evidence | false | false | true | true but with wrong symbol/name | true |
| `X-Token` header dependency | true | true in run 001 | true in run 001 | true | false | true | true | false |
| HTTP 401 for missing token | true | true in run 001 | true in run 001 | true | false | true | true | false |
| invalid token rejected | false | false | false | false | false | true in run 002 only | true in run 002 only | false for hidden focus |
| audit only after success | true | true in run 001 | true in run 001 | true | false | true | true | false |
| TestClient behavior | false | false | false | false | false | true | public tests passed | false |

Summary metrics:

| metric | value | notes |
| --- | ---: | --- |
| contract_recall | 4 / 8 | High-level behavior was present; exact introspection names were missing. |
| contract_precision | 4 / 4 | Returned README facts were relevant but incomplete. |
| agent_context_utilization | medium | Agent used `Annotated`, `Depends`, `BackgroundTasks`, `X-Token`; it could not use missing exact names. |
| actionability_gap | high | Context did not turn public docs into an implementation checklist with names/signatures. |

## Patch Outcome

Run 001 patch summary:

- Added a dependency named `require_x_token`.
- Added route parameter `x_token` with an alias type using `Depends(require_x_token)`.
- Used `BackgroundTasks` and public tests passed.
- Hidden failed because the exact dependency symbol and route parameter expected by the contract were absent.

Run 002 patch summary:

- Added a dependency named `verify_token` and alias `TokenDependency`.
- Added route parameter `_token`.
- Rejected invalid tokens and used `BackgroundTasks`; public tests passed.
- Hidden failed because the exact dependency symbol and route parameter expected by the contract were absent.

## Failure Classification

Primary label:

```text
context_missing_critical_contract
```

Secondary labels:

```text
agent_used_context_incompletely
task_hidden_contract_too_brittle
public_tests_too_weak
```

## Task Quality Diagnosis

| question | answer |
| --- | --- |
| is task fair? | Partially. High-level behavior is fair; exact symbol/parameter-name introspection is brittle. |
| is hidden contract discoverable? | Partially. `X-Token`, shared dependency, and audit behavior are discoverable; `require_token` and `token` are not. |
| is required info in repo docs? | No for exact names; yes for behavior. |
| is required info in DocAtlas context? | No for exact names; partial for behavior. |
| is required info in prompt? | No for exact names; partial for behavior. |

## Offline Counterfactual Context Packet

Oracle-free improved packet from public docs and visible code only:

```text
Project constraints:
1. Keep the user endpoint in `src/app/main.py` and preserve the current response shape.
2. Replace inline/query token handling with a reusable FastAPI dependency that reads `X-Token` from request headers and raises HTTP 401 on failure.
3. Do not record audit events during failed auth; enqueue `record_audit("user:{user_id}")` with `BackgroundTasks` only in the successful route body.

Visible code clues:
- Existing route parameter is named `x_token`; this currently behaves as query input, not header input.
- Existing public tests exercise missing token, valid `secret-token`, and audit side effects.

Implementation checklist:
- Import `Annotated`, `BackgroundTasks`, `Depends`, `Header`, and `HTTPException`/status.
- Create one shared dependency function for token validation.
- Use `Annotated[str, Depends(...)]` on the route dependency parameter.
- Keep token validation out of the route body; keep audit enqueueing in the route body after dependency resolution.
- Add/keep public tests for missing token, valid token, invalid token, and no failed-auth audit event.
```

Could a reasonable agent infer the hidden-correct patch from this? Mostly for behavior, but not for the exact hidden names `require_token` and `token` unless those names are added to public docs/tests or inferred from a naming convention that is not present.

## Recommended Path

This task supports Path C plus some Path A:

```text
ITERATE_TASKS
```

Reason: the hardest failed requirements are not present in public/project docs and cannot be recovered by better context presentation without leaking evaluator-only details.
