from __future__ import annotations

from fastapi import FastAPI

from .errors import error_envelope

app = FastAPI()


@app.exception_handler(403)
async def forbidden_handler(request, exc):  # noqa: ANN001
    return error_envelope("forbidden", "admin access required", 403)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
