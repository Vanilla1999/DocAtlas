from __future__ import annotations

from fastapi import FastAPI

from .audit import record_audit

app = FastAPI()


@app.get("/users/{user_id}")
def read_user(user_id: int, x_token: str | None = None) -> dict[str, int | str]:
    if x_token == "secret-token":
        record_audit(f"user:{user_id}")
    return {"user_id": user_id, "status": "ok"}
