from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_error_shape() -> None:
    client = TestClient(app)

    response = client.get("/internal/admin/status")

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "forbidden", "message": "admin access required"}}
