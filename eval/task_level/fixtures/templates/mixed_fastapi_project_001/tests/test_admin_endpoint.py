from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_authorized_admin_succeeds() -> None:
    client = TestClient(app)

    response = client.get("/internal/admin/status", headers={"X-Admin-Token": "admin-secret"})

    assert response.status_code == 200
    assert response.json() == {"admin": "ok"}


def test_admin_dependency() -> None:
    client = TestClient(app)

    response = client.get("/internal/admin/status")

    assert response.status_code == 403
