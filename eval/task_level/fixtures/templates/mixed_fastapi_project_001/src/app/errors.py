from __future__ import annotations

from fastapi.responses import JSONResponse


def error_envelope(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})
