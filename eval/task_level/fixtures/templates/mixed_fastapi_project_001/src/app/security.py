from __future__ import annotations

from fastapi import Header, HTTPException


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> str:
    if x_admin_token != "admin-secret":
        raise HTTPException(status_code=403, detail="admin access required")
    return "admin"
