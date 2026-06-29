# FastAPI Auth Audit Fixture

The user route must reject missing `X-Token`, share the token dependency across routes, and enqueue audit logging with FastAPI `BackgroundTasks` after successful requests.

Follow the local auth dependency convention in `docs/auth.md`.
