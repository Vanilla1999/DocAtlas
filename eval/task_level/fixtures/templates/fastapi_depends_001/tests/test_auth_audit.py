from __future__ import annotations

from fastapi.testclient import TestClient

from app.audit import AUDIT_EVENTS, clear_audit
from app.main import app


def test_requires_token() -> None:
    client = TestClient(app)

    response = client.get("/users/42")

    assert response.status_code == 401


def test_valid_token_succeeds() -> None:
    client = TestClient(app)

    response = client.get("/users/42", headers={"X-Token": "secret-token"})

    assert response.status_code == 200
    assert response.json() == {"user_id": 42, "status": "ok"}


def test_audit_background_task() -> None:
    clear_audit()
    client = TestClient(app)

    response = client.get("/users/7", headers={"X-Token": "secret-token"})

    assert response.status_code == 200
    assert AUDIT_EVENTS == ["user:7"]
