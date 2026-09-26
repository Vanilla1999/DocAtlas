"""Self-contained public schemas preserve path types in both client dialects."""
import jsonschema
import pytest

from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface


@pytest.mark.parametrize("dialect", [jsonschema.Draft7Validator, jsonschema.Draft202012Validator])
@pytest.mark.parametrize("field", ["changed_paths", "deleted_paths", "old_path", "new_path"])
def test_delta_references_preserve_validation_in_both_dialects(dialect, field):
    spec = next(s for s in build_docs_surface(DocsServerConfig()).tools if s.name == "prepare_docs")
    dialect.check_schema(spec.input_schema)
    validator = dialect(spec.input_schema)
    for value, accepted in [("docs/a.md", True), ("../outside", False), ("/outside", False),
                            (17, False), ("", False), ("C:\\outside", False)]:
        delta = {field: [value]} if field.endswith("_paths") else {
            "renamed_paths": [{"old_path": "docs/a.md", "new_path": "docs/b.md", field: value}],
        }
        args = {"action": "sync_project_docs", "project_path": "/project", **delta}
        assert validator.is_valid(args) is accepted, (dialect.__name__, field, value)
