"""Boundary and isolation controls for the published sync delta schema."""
from copy import deepcopy

import jsonschema
import pytest

from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface
from docmancer.mcp._docs_server_tool_data import RAW_TOOLS


def _spec(fallback=False):
    return next(s for s in build_docs_surface(DocsServerConfig(text_fallback=fallback)).tools if s.name == "prepare_docs")


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("field", ["changed_paths", "deleted_paths", "renamed_paths"])
@pytest.mark.parametrize("value_kind", ["null", "empty", "limit"])
def test_delta_boundary_shapes_are_advertised(fallback, field, value_kind):
    row = {"old_path": "docs/a.md", "new_path": "docs/b.md"} if field == "renamed_paths" else "docs/a.md"
    value = None if value_kind == "null" else [] if value_kind == "empty" else [deepcopy(row) for _ in range(500)]
    spec = _spec(fallback)
    args = {"action": "sync_project_docs", "project_path": "/project", field: value}
    jsonschema.validate(args, spec.input_schema)
    jsonschema.validate(args, spec.validation_schema)


@pytest.mark.parametrize("field", ["changed_paths", "deleted_paths", "renamed_paths"])
def test_even_null_delta_is_rejected_for_another_action(field):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"action": "cancel_docs_job", "job_id": "job", field: None}, _spec().input_schema)


@pytest.mark.parametrize("path", ["../outside.md", "/absolute.md", "C:\\outside.md", "\\\\server\\file.md", "docs/../secret.md", "docs/../../secret.md", "docs/a\x00.md", "docs/a\n.md"])
@pytest.mark.parametrize("field", ["changed_paths", "deleted_paths", "old_path", "new_path"])
def test_lexical_escape_is_rejected_in_every_delta_position(path, field):
    args = {"action": "sync_project_docs", "project_path": "/project"}
    if field in {"old_path", "new_path"}:
        row = {"old_path": "docs/a.md", "new_path": "docs/b.md", field: path}
        args["renamed_paths"] = [row]
    else:
        args[field] = [path]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(args, _spec().input_schema)


def test_public_schema_copies_do_not_mutate_raw_or_validation():
    raw = next(t for t in RAW_TOOLS if t["name"] == "prepare_docs")
    before = deepcopy(raw)
    spec = _spec()
    validated = deepcopy(spec.validation_schema)
    spec.input_schema["properties"]["changed_paths"]["items"]["type"] = "integer"
    assert raw == before
    assert spec.validation_schema == validated
    assert _spec().input_schema["properties"]["changed_paths"]["items"]["type"] == "string"
