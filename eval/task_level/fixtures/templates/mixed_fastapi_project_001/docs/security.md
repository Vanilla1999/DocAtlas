# Security ADR

All internal admin routes must live in `src/app/main.py` and use the shared `require_admin` dependency from `app.security`.

Do not duplicate token parsing or role checks in route handlers. The dependency is the single authorization boundary.

Admin routes must declare the shared admin dependency as a route parameter named `admin`.

Use FastAPI dependency injection rather than duplicating auth logic in the handler.

The dependency value is typed as a string user/admin identifier. The expected route parameter shape is:

```python
admin: Annotated[str, Depends(require_admin)]
```
