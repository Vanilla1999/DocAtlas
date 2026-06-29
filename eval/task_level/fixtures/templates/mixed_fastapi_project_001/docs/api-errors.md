# API Errors

Error responses use this envelope:

```json
{"error": {"code": "forbidden", "message": "admin access required"}}
```

Use the shared helper from `app.errors` for documented errors.

Dependency-raised `HTTPException` errors must still pass through the project error-envelope handler.

Do not return raw FastAPI error bodies for admin authorization failures.
