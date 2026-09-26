"""Public delta operations must preserve another project's actual SQLite rows."""
import json
import subprocess

import pytest

from tests.docs import test_public_incremental_sync_e2e as helpers
from tests._shared_test_docs_service import _flutter_project
from docmancer.mcp._docs_server_part01 import _service_for_project_path

project_state = helpers.project_state


def _project_rows(active, project):
    inventory = helpers._inventory(active, project)
    assert inventory
    sources = sorted(inventory.values())
    placeholders = ",".join("?" for _ in sources)
    with active._agent_instance().store._connect() as conn:
        return {
            table: sorted((tuple(row) for row in conn.execute(
                f"SELECT * FROM {table} WHERE source IN ({placeholders})", sources,
            )), key=repr)
            for table in ("sources", "sections")
        }


@pytest.mark.parametrize("operation", ["change", "delete", "rename"])
def test_public_delta_preserves_other_project(project_state, tmp_path, operation):
    first, service, active_first = project_state
    parent = tmp_path / "second"
    parent.mkdir()
    second = _flutter_project(parent)
    (second / "docs").mkdir()
    witness = second / "docs/b.md"
    witness.write_text("# Other project\n\nOtherProjectMustStayNeedle.\n", encoding="utf-8")
    for args in (("init", "-q"), ("add", "."),
                 ("-c", "user.name=DocAtlas Test", "-c", "user.email=test@example.invalid",
                  "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")):
        subprocess.run(["git", "-C", str(second), *args], check=True, capture_output=True)
    result = helpers._call(service, second)
    assert result["status"] == "success", result
    active_second = _service_for_project_path(service, {"project_path": str(second)})
    before = _project_rows(active_second, second)
    before_bytes = witness.read_bytes()
    assert "OtherProjectMustStayNeedle" in json.dumps(before, default=str)
    if operation == "change":
        (first / "docs/b.md").write_text("# Changed\n\nFirstProjectNewNeedle.\n", encoding="utf-8")
        delta = {"changed_paths": ["docs/b.md"]}
    elif operation == "delete":
        (first / "docs/b.md").unlink()
        delta = {"deleted_paths": ["docs/b.md"]}
    else:
        (first / "docs/b.md").rename(first / "docs/moved.md")
        delta = {"renamed_paths": [{"old_path": "docs/b.md", "new_path": "docs/moved.md"}]}
    result = helpers._call(service, first, **delta)
    assert result["status"] == "success", result
    after_first = helpers._inventory(active_first, first)
    if operation == "change":
        assert "FirstProjectNewNeedle" in json.dumps(_project_rows(active_first, first), default=str)
    else:
        assert "docs/b.md" not in after_first
    assert _project_rows(active_second, second) == before
    assert witness.read_bytes() == before_bytes
