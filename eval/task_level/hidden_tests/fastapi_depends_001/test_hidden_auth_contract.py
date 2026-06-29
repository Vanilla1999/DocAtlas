from __future__ import annotations

import inspect
import typing

from fastapi.testclient import TestClient

from app import main
from app.audit import AUDIT_EVENTS, clear_audit


def test_shared_dependency_uses_annotated_depends() -> None:
    assert hasattr(main, "require_token")
    signature = inspect.signature(main.read_user)
    annotations = typing.get_type_hints(main.read_user, include_extras=True)

    token_annotation = annotations.get("token")
    assert token_annotation is not None
    metadata = getattr(token_annotation, "__metadata__", ())
    assert any(item.__class__.__name__ == "Depends" for item in metadata)
    assert "x_token" in inspect.signature(main.require_token).parameters


def test_no_test_only_bypass_and_existing_response_preserved() -> None:
    source = inspect.getsource(main.read_user)
    assert "secret-token" not in source
    client = TestClient(main.app)

    response = client.get("/users/5", headers={"X-Token": "secret-token"})

    assert response.status_code == 200
    assert response.json() == {"user_id": 5, "status": "ok"}


def test_background_audit_runs_after_success_only() -> None:
    clear_audit()
    client = TestClient(main.app)

    denied = client.get("/users/5")
    assert denied.status_code == 401
    assert AUDIT_EVENTS == []

    allowed = client.get("/users/5", headers={"X-Token": "secret-token"})
    assert allowed.status_code == 200
    assert AUDIT_EVENTS == ["user:5"]
