# mixed_fastapi_project_001 Context Quality Analysis

Scope: failed `docatlas_tool_recommended` runs from `docatlas_recommended_pilot_001` and `docatlas_recommended_pilot_002`.

This file is sanitized derived analysis. It does not include raw trajectories, workspace dumps, gold patch content, or hidden test source.

## Runs

| run_id | public | hidden | DocAtlas calls | DocAtlas tools | agent edits | primary failure |
| --- | --- | --- | ---: | --- | --- | --- |
| docatlas_recommended_pilot_001 | fail | fail | 6 | `inspect_project_docs`, `sync_project_docs`, `get_project_context` | `src/app/main.py` | `context_present_but_not_salient` |
| docatlas_recommended_pilot_002 | fail | fail | 6 | `inspect_project_docs`, `bootstrap_project_docs`, `get_project_context` | `src/app/main.py` | `context_present_but_not_salient` |

## Hidden-Contract Requirements

Evaluator-only contract terms:

| requirement | rationale |
| --- | --- |
| Internal admin route lives in `src/app/main.py` | Project security docs specify module placement. |
| Route uses shared `require_admin` from `app.security` | Project security docs make this the single authorization boundary. |
| Route exposes dependency metadata as a route parameter named `admin` | Hidden introspection reads route function type hints by parameter name. |
| Route dependency form is `Annotated[str, Depends(require_admin)]` | Hidden introspection checks `Annotated` metadata rather than decorator-only dependencies or default-value `Depends`. |
| Route body does not duplicate token parsing or role checks | Project security docs forbid duplicate auth logic. |
| Dependency-raised 403 uses documented error envelope | Public and hidden tests expect the documented envelope for unauthorized admin access. |
| Exception handler targets `HTTPException` rather than integer `403` | FastAPI dependency failures raise `HTTPException`; integer-code handler is not sufficient for this path. |

The exact `Annotated[str, Depends(require_admin)]` parameter form and `HTTPException` handler target are not stated in the project docs.

## DocAtlas Questions And Responses

### docatlas_recommended_pilot_001

Question asked:

> What are the documented project conventions for adding internal admin FastAPI routes, especially required dependencies and error response envelope?

Response shape:

| field | observed |
| --- | --- |
| status | `success` after explicit `sync_project_docs` |
| primary content | Context pack led with API error envelope and then security docs |
| project constraints | Route in `src/app/main.py`; use shared `require_admin`; no duplicate token parsing/role checks; use shared `app.errors` helper |
| Trust Contract | Selected project docs: `docs/api-errors.md`, `docs/security.md`, `README.md` |
| primary snippet | JSON error envelope from `docs/api-errors.md` |
| key missing constraints | `Annotated[str, Depends(require_admin)]`, parameter name `admin`, `HTTPException` exception handler |

### docatlas_recommended_pilot_002

Question asked:

> How should internal admin FastAPI routes be registered, protected with dependencies, and format authorization errors in this project?

Response shape:

| field | observed |
| --- | --- |
| status | `success` after `bootstrap_project_docs` |
| primary snippet | JSON error envelope from `docs/api-errors.md` |
| context pack | `docs/security.md`, `README.md`, `docs/api-errors.md` |
| Trust Contract | Selected project docs; no library snippets |
| key project constraints surfaced | `src/app/main.py`; shared `require_admin`; no duplicate token parsing; documented error envelope |
| key missing constraints | `Annotated[str, Depends(require_admin)]`, parameter name `admin`, `HTTPException` handler |

## Contract Coverage

| requirement | present_in_docatlas_context | present_in_primary_snippet | present_in_context_pack | present_in_project_docs | present_in_library_docs | agent_mentioned_it | patch_implemented_it | test_failed_because_missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| route in `src/app/main.py` | true | false | true | true | false | true | true | false |
| use shared `require_admin` | true | false | true | true | false | true | true | false |
| route parameter named `admin` | false | false | false | false | false | false | false | true |
| `Annotated[str, Depends(require_admin)]` route parameter | false | false | false | false | false | false | false | true |
| no duplicate auth logic | true | false | true | true | false | true | true | false |
| documented error envelope | true | true | true | true | false | true | patch relied on existing handler but not correctly | true |
| `HTTPException` handler for dependency-raised 403 | false | false | false | false | false | false | false | true |
| import/use `app.errors.error_envelope` | true | true | true | true | false | true | already present | false |

Summary metrics:

| metric | value | notes |
| --- | ---: | --- |
| contract_recall | 5 / 8 | Project docs supplied high-level constraints but omitted implementation-critical FastAPI shape. |
| contract_precision | 5 / 5 | Selected docs were relevant; precision was not the problem. |
| agent_context_utilization | medium-high | Agent used `require_admin`, module placement, and error-envelope facts. |
| actionability_gap | high | Context lacked a checklist that distinguished FastAPI decorator dependencies from introspectable `Annotated` parameter dependencies and did not warn about integer exception handlers. |

## Patch Outcome

Run 001 patch summary:

- Added `GET /internal/admin/status` in `src/app/main.py`.
- Attached auth with `dependencies=[Depends(require_admin)]` on the route decorator.
- Did not add an `admin` route parameter with `Annotated` metadata.
- Kept `@app.exception_handler(403)`, so dependency-raised `HTTPException(403)` did not reliably use the documented envelope.

Run 002 patch summary:

- Added `GET /internal/admin/status` in `src/app/main.py`.
- Added `_admin: str = Depends(require_admin)` as a default-value dependency.
- Did not use `Annotated[str, Depends(require_admin)]` or parameter name `admin`.
- Kept `@app.exception_handler(403)`, so dependency-raised `HTTPException(403)` did not reliably use the documented envelope.

## Failure Classification

Primary label:

```text
context_present_but_not_salient
```

Secondary labels:

```text
snippet_missing_required_constraint
project_constraint_missing
library_api_present_but_project_contract_missing
public_tests_too_weak_for_signature_shape
task_hidden_contract_too_brittle
```

The error-envelope failure is public-test discoverable, but agents could not fully run public tests in their active environment. The `Annotated` signature failure is hidden-only and not discoverable from current docs.

## Task Quality Diagnosis

| question | answer |
| --- | --- |
| is task fair? | Partially. Shared dependency, module placement, and envelope are fair; exact `Annotated` signature is brittle. |
| is hidden contract discoverable? | Partially. `require_admin` and envelope are discoverable; `admin` parameter and `Annotated` form are not. |
| is required info in repo docs? | Yes for high-level constraints; no for exact FastAPI signature and handler target. |
| is required info in DocAtlas context? | Yes for high-level constraints; no for exact signature/handler target. |
| is required info in prompt? | No for exact signature/handler target. |

## Format, Priority, And Directivity

| dimension | diagnosis |
| --- | --- |
| primary snippet existed | Yes in run 002; JSON error envelope was primary. |
| project constraints included | Yes, in context pack and agent summaries. |
| Trust Contract included | Yes, selected project docs. |
| exact source/version included | Project source paths included; no library version context was selected. |
| warnings included | Yes for generic missing Dart/Flutter metadata; not relevant to this Python fixture. |
| critical project constraint priority | Partially wrong: API error JSON outranked security/dependency implementation constraints. |
| top-5 context items | High-level security and API docs were in top items; exact missing constraints were absent. |
| explicit actionable checklist | No. Context did not say to use a route parameter `admin: Annotated[str, Depends(require_admin)]` or change handler target to `HTTPException`. |

## Offline Counterfactual Context Packet

Oracle-free improved packet from public docs and visible code only:

```text
Project constraints:
1. Internal admin endpoints belong in `src/app/main.py`.
2. Use the shared `app.security.require_admin` dependency; do not parse `X-Admin-Token` or check roles inside the route body.
3. Unauthorized admin responses must use `app.errors.error_envelope` with `{"error": {"code": "forbidden", "message": "admin access required"}}`.

Visible code clues:
- `require_admin` raises `HTTPException(status_code=403, detail="admin access required")`.
- `main.py` currently registers `@app.exception_handler(403)`, but dependency failures are FastAPI `HTTPException` instances.
- Existing public tests call `/internal/admin/status` with and without `X-Admin-Token`.

Implementation checklist:
- Import `Annotated`, `Depends`, `FastAPI`, and `HTTPException` in `src/app/main.py`.
- Register the error handler for `HTTPException` and return `error_envelope("forbidden", "admin access required", 403)` for 403s.
- Add `GET /internal/admin/status` in `src/app/main.py`.
- Depend on `require_admin` through a route parameter rather than duplicating token logic or only using decorator-level dependencies.
- Keep the route body limited to returning `{"admin": "ok"}`.
```

Could a reasonable agent infer the hidden-correct patch from this? It should fix the public envelope failure and avoid duplicate auth. It still would not necessarily choose the exact hidden parameter name `admin` or `Annotated[str, Depends(require_admin)]` unless task docs/public tests add a visible convention for introspectable dependency parameters.

## Recommended Path

This task supports Path A plus Path C:

```text
ITERATE_CONTEXT_PRESENTATION
```

Reason: some high-level facts are present but not directive; however, hidden-only signature details also need task/doc clarification before scaling.
