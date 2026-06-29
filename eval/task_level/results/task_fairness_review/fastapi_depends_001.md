# fastapi_depends_001 Fairness Review

## Summary

The behavioral contract was already fair: the issue and public tests ask for `X-Token` rejection and successful audit logging. The unfair part was exact form: hidden tests required `require_token` and a route parameter named `token`, but no visible source named those conventions.

Calibration decision: expose the exact form as a project auth convention in `docs/auth.md`, while keeping public tests behavior-focused.

| requirement | why it matters | currently discoverable before calibration? | visible source after calibration | fix plan | decision |
| --- | --- | --- | --- | --- | --- |
| Reject missing `X-Token` with HTTP 401 | Core auth behavior and user-visible security contract. | yes | issue text, `README.md`, public test `tests/test_auth_audit.py` | no change | keep hidden as behavioral edge coverage |
| Use FastAPI dependency injection with `Annotated`/`Depends` | Ensures reusable FastAPI auth rather than inline handler checks. | yes/partial | issue text, FastAPI docs, `docs/auth.md` | add project convention doc for local dependency contract | keep strict |
| Shared dependency named `require_token` | Enables consistent route auth dependency naming and reusable project convention. | no | `docs/auth.md` | expose as visible project convention | expose |
| Route dependency parameter named `token` | Makes the validated token available to the route with a stable local convention. | no | `docs/auth.md` | expose as visible project convention | expose |
| Do not duplicate token validation inside route handlers | Prevents test-only bypasses and keeps auth centralized. | partial | `README.md`, `docs/auth.md`, hidden source inspection | make explicit in `docs/auth.md` | expose |
| Queue audit with `BackgroundTasks` after successful auth only | Prevents auditing failed auth and follows FastAPI background task behavior. | yes | issue text, public test, FastAPI docs | no change | keep hidden edge check |

## Oracle-Only Requirements

Before calibration:

- `require_token` exact name was oracle-only.
- `token` route parameter exact name was oracle-only.

After calibration:

- Both are visible in `docs/auth.md`.
- No exact-form hidden requirement remains oracle-only for this task.
