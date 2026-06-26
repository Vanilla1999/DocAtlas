# mixed_fastapi_project_001 Fairness Review

## Summary

The project already exposed `require_admin`, the route location, and the error envelope. The brittle parts were the exact route parameter name, the `Annotated[str, Depends(require_admin)]` shape, and the need for dependency-raised `HTTPException` errors to pass through the project error envelope.

Calibration decision: expose those as project conventions in `docs/security.md` and `docs/api-errors.md`, without adding a full endpoint implementation or gold patch.

| requirement | why it matters | currently discoverable before calibration? | visible source after calibration | fix plan | decision |
| --- | --- | --- | --- | --- | --- |
| Add `/internal/admin/status` in `src/app/main.py` | Keeps internal admin routes in the documented application module. | yes | issue text, `README.md`, `docs/security.md` | no change | keep strict |
| Use shared `require_admin` dependency | Prevents duplicated auth logic and follows security ADR. | yes | issue text, `docs/security.md`, `src/app/security.py` | no change | keep strict |
| Do not duplicate admin token parsing or role checks in handler | Ensures the shared dependency is the only authorization boundary. | yes | `docs/security.md`, `src/app/security.py` | no change | keep strict |
| Route parameter named `admin` | Stable local convention for the dependency value. | no/partial | `docs/security.md` | expose as project convention | expose |
| Use `admin: Annotated[str, Depends(require_admin)]` | Captures the intended FastAPI dependency injection shape without inline auth. | no/partial | `docs/security.md` | expose as project convention with a shape example | expose |
| Return documented forbidden error envelope | User-visible API error contract. | yes | issue text, `docs/api-errors.md`, `src/app/errors.py`, public tests | no change | keep hidden behavior coverage |
| Dependency-raised `HTTPException` 403 passes through envelope handler | Ensures auth failures raised from dependencies use the same API error contract. | partial | `docs/api-errors.md`, `src/app/security.py` | make dependency-raised path explicit in API error docs | expose |

## Oracle-Only Requirements

Before calibration:

- `admin` exact route parameter name was not sufficiently discoverable.
- `Annotated[str, Depends(require_admin)]` exact shape was not sufficiently discoverable.
- Dependency-raised `HTTPException` envelope handling was not sufficiently salient.

After calibration:

- `docs/security.md` documents the parameter name and accepted dependency shape.
- `docs/api-errors.md` documents dependency-raised `HTTPException` envelope handling.
- No exact-form hidden requirement remains oracle-only for this task.
