"""Real public dispatcher regression tests; only the storage service is a spy."""
from copy import deepcopy

import jsonschema
import pytest

from docmancer.docs.models import ProjectDocsSyncResult, ProjectMetadata
from docmancer.mcp.docs_server import (
    DocsServerConfig, build_docs_surface, call_docs_tool_payload,
)

DELTA = {
    "changed_paths": ["docs/new.md", "docs/changed.md"],
    "deleted_paths": ["docs/deleted.md"],
    "renamed_paths": [{"old_path": "docs/old.md", "new_path": "docs/new-name.md"}],
}


class SyncSpy:
    def __init__(self):
        self.calls = []

    def sync_project_docs(self, project_path, **kwargs):
        self.calls.append((project_path, deepcopy(kwargs)))
        return ProjectDocsSyncResult(
            status="success", project=ProjectMetadata(project_path=project_path),
        )


@pytest.fixture
def surface():
    return build_docs_surface(DocsServerConfig())


@pytest.mark.parametrize("field", tuple(DELTA))
def test_delta_property_is_advertised_and_validated(surface, field):
    spec = next(s for s in surface.tools if s.name == "prepare_docs")
    assert field in spec.input_schema["properties"]
    assert spec.input_schema["properties"][field] == spec.validation_schema["properties"][field]


@pytest.mark.parametrize("fields", [(), ("changed_paths",), ("deleted_paths",), ("renamed_paths",), tuple(DELTA)])
def test_public_dispatcher_forwards_valid_delta(surface, tmp_path, fields):
    spy = SyncSpy()
    args = {"action": "sync_project_docs", "project_path": str(tmp_path), "with_vectors": False}
    args.update({k: deepcopy(DELTA[k]) for k in fields})
    result = call_docs_tool_payload("prepare_docs", args, spy, surface=surface)
    assert "error" not in result, result
    assert result["status"] == "success"
    assert len(spy.calls) == 1
    path, forwarded = spy.calls[0]
    assert path == str(tmp_path)
    for field in DELTA:
        assert forwarded[field] == args.get(field)
    assert forwarded["with_vectors"] is False


@pytest.mark.parametrize("bad", [
    {"changed_paths": "docs/a.md"},
    {"changed_paths": [17]},
    {"changed_paths": [f"docs/{i}.md" for i in range(501)]},
    {"renamed_paths": [{"old_path": "docs/a.md"}]},
    {"renamed_paths": [{"old_path": "docs/a.md", "new_path": "docs/b.md", "extra": True}]},
    {"changed_paths": ["../outside.md"]},
    {"changed_paths": ["/absolute.md"]},
    {"surprise": True},
])
def test_bad_delta_cannot_reach_storage(surface, tmp_path, bad):
    spy = SyncSpy()
    result = call_docs_tool_payload("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(tmp_path), **bad,
    }, spy, surface=surface)
    assert result["error"]["reason_code"] == "validation_error"
    assert spy.calls == []


@pytest.mark.parametrize("field", tuple(DELTA))
def test_other_action_rejects_delta_in_public_schema(surface, field):
    spec = next(s for s in surface.tools if s.name == "prepare_docs")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({
            "action": "cancel_docs_job", "job_id": "job-test", field: DELTA[field],
        }, spec.input_schema)


def test_unknown_mode_is_not_added_as_compatibility_alias(surface):
    spec = next(s for s in surface.tools if s.name == "get_docs_context")
    assert "mode" not in spec.input_schema["properties"]
    result = call_docs_tool_payload("get_docs_context", {
        "question": "How does this repository work?", "mode": "project",
    }, object(), surface=surface)
    assert result["error"]["reason_code"] == "validation_error"
