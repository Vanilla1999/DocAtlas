# Security ADR

All internal admin routes must live in `src/app/main.py` and use the shared `require_admin` dependency from `app.security`.

Do not duplicate token parsing or role checks in route handlers. The dependency is the single authorization boundary.
