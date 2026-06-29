from __future__ import annotations

import inspect
import typing
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.security import require_admin


def test_admin_endpoint_depends_on_shared_require_admin() -> None:
    route = next(route for route in main.app.routes if getattr(route, "path", None) == "/internal/admin/status")
    dependant = getattr(route, "dependant", None)
    assert dependant is not None
    assert any(dep.call is require_admin for dep in dependant.dependencies)

    annotations = typing.get_type_hints(main.admin_status, include_extras=True)
    metadata = getattr(annotations.get("admin"), "__metadata__", ())
    assert any(item.__class__.__name__ == "Depends" for item in metadata)


def test_no_duplicate_auth_logic_in_route() -> None:
    source = inspect.getsource(main.admin_status)
    assert "X-Admin-Token" not in source
    assert "admin-secret" not in source


def test_documented_error_envelope_and_module_contract() -> None:
    client = TestClient(main.app)
    response = client.get("/internal/admin/status")

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "forbidden", "message": "admin access required"}}
    assert Path("src/app/main.py").exists()
    assert "require_admin" in Path("docs/security.md").read_text(encoding="utf-8")
