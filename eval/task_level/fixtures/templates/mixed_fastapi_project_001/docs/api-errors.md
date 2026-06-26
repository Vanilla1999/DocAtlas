# API Errors

Error responses use this envelope:

```json
{"error": {"code": "forbidden", "message": "admin access required"}}
```

Use the shared helper from `app.errors` for documented errors.
