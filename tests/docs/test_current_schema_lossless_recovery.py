from __future__ import annotations

import copy

import jsonschema
import pytest

from docmancer.mcp._docs_server_schema import PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA
from docmancer.mcp.docs_server import current_tools


def _schema(layer):
    if layer == "internal":
        return PUBLIC_GET_DOCS_CONTEXT_OUTPUT_SCHEMA
    # Keep the shared branch checks while the default advertises docs only.
    return {"oneOf": [next(tool["outputSchema"] for tool in current_tools({})
                          if tool["name"] == "get_docs_context")]}


def _recovery():
    return {
        "status": "insufficient_evidence",
        "kind": "docs_context",
        "missing": [f"Раздел {index}: exact tail condition" for index in range(17)],
        "module_candidates": [{"module_path": f"packages/module-{index}"} for index in range(19)],
    }


@pytest.mark.parametrize("layer", ["advertised", "internal"])
def test_recovery_schema_preserves_all_missing_and_module_candidates(layer):
    payload = _recovery()
    before = copy.deepcopy(payload)
    jsonschema.validate(payload, _schema(layer))
    assert payload == before
    assert payload["missing"][-1] == "Раздел 16: exact tail condition"
    assert payload["module_candidates"][-1] == {"module_path": "packages/module-18"}
    properties = _schema(layer)["oneOf"][0]["properties"]
    assert "maxItems" not in properties["missing"]
    assert "maxItems" not in properties["module_candidates"]


@pytest.mark.parametrize("layer", ["advertised", "internal"])
@pytest.mark.parametrize("change", [
    {"missing": [None]},
    {"missing": "section"},
    {"module_candidates": [{"module_path": 1}]},
    {"module_candidates": [{}]},
    {"module_candidates": None},
    {"status": "unknown"},
    {"kind": "patch_context"},
    {"estimated_tokens": True},
])
def test_recovery_schema_keeps_item_types_required_and_discriminators(layer, change):
    schema = _schema(layer)
    payload = _recovery()
    jsonschema.validate(payload, schema)
    payload.update(change)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


@pytest.mark.parametrize("layer", ["advertised", "internal"])
def test_recovery_schema_keeps_status_required(layer):
    schema = _schema(layer)
    payload = _recovery()
    jsonschema.validate(payload, schema)
    del payload["status"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_candidate_unknown_field_behavior_remains_layer_specific():
    payload = _recovery()
    jsonschema.validate(payload, _schema("internal"))
    payload["module_candidates"][0]["unknown"] = "not authority"
    jsonschema.validate(payload, _schema("advertised"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, _schema("internal"))


def test_representation_changes_keep_continuation_work_bound():
    for layer in ("advertised", "internal"):
        schema = _schema(layer)
        jsonschema.validate(_recovery(), schema)
        assert schema["oneOf"][0]["properties"]["read_next"]["maxItems"] == 1
