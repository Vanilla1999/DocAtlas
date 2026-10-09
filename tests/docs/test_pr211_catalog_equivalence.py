"""PR211 catalog reductions against an independent, exact advertised baseline.

The fixture was extracted with ast.literal_eval from git show
21fe472d983f394130849d6fd4e582043d58e9ba:docmancer/mcp/_docs_server_tool_data.py.
No service imports, reconstructed old schema, or post-change values produced it.
Encoding: UTF-8, ensure_ascii=False, sort_keys=True, separators=(',', ':').
These controls concern JSON Schema and pre-dispatch rejection, not MCP clients.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import jsonschema

from docmancer.mcp.docs_server import DocsMcpSurface, call_docs_tool_payload, current_tools


BASELINE_SHA256 = "ad63f367601a18fe04ec715800be2a935a7496c16beb71df4d1818d258bc06db"
BASELINE_PATH = Path(__file__).with_name("fixtures") / "pr211_catalog_21fe472d.json"


def _catalogs():
    previous = json.loads(BASELINE_PATH.read_bytes())
    current = current_tools({})
    return ({tool["name"]: tool for tool in previous},
            {tool["name"]: tool for tool in current})


def _normalized_schema(value):
    """Only language-preserving annotation/redundancy rules, not a validator.

    Enum/const rules are restricted to strings and JSON booleans. In particular,
    a Python equality such as True == 1 cannot justify removing a numeric type.
    Hash upper lengths deliberately remain: regex '$' admits a final newline.
    """
    if isinstance(value, list):
        return [_normalized_schema(child) for child in value]
    if not isinstance(value, dict):
        return value
    result = {key: _normalized_schema(child) for key, child in value.items()
              if key != "description"}
    declared_type = result.get("type")
    if declared_type == "string" and (
        ("const" in result and type(result["const"]) is str)
        or (result.get("enum") and all(type(item) is str for item in result["enum"]))
    ):
        result.pop("type")
    elif declared_type == "boolean" and type(result.get("const")) is bool:
        result.pop("type")
    pattern_minima = {
        "^[0-9a-f]{64}$": 64,
        "^gen-[0-9a-f]{32}$": 36,
        "^sha256:[0-9a-f]{64}$": 71,
        r"^(?!/)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*[\\:]).+$": 1,
    }
    guaranteed = pattern_minima.get(result.get("pattern"))
    if guaranteed is not None and result.get("minLength", guaranteed + 1) <= guaranteed:
        result.pop("minLength")

    condition = result.get("if", {}).get("properties", {}).get("action", {})
    then_action = result.get("then", {}).get("properties", {}).get("action")
    if set(condition) == {"const"} and then_action == condition:
        # The branch is evaluated only when this very discriminator matched.
        result["then"]["properties"]["action"] = {}
    if "allOf" in result:
        branches = result["allOf"]
        merged = []
        for branch in branches:
            if set(branch) == {"if", "else"}:
                matching = next((other for other in merged
                                 if set(other) == {"if", "then"}
                                 and other["if"] == branch["if"]), None)
                if matching is not None:
                    # (if C then A) AND (if C else B) == (if C then A else B).
                    matching["else"] = branch["else"]
                    continue
            merged.append(branch)
        result["allOf"] = merged
    return result


def _mutation_fixture():
    return {
        "operation": "sync_project_docs", "confirm": True,
        "storage_path": "/fixture-host/mcp-members/members.db",
        "catalog_sha256": "a" * 64, "expected_generation_id": None,
        "documents": [{"path": "docs/guide.md", "content_sha256": "b" * 64,
                       "catalog_entry_hash": "sha256:" + "c" * 64}],
    }


def _prepare_fixtures():
    return {
        "sync_project_docs": {"project_path": "/fixture-project", "mutation": _mutation_fixture()},
        "prefetch_project_dependency_docs": {"project_path": "/fixture-project"},
        "prefetch_library_docs": {"library": "fixture-library"},
        "discover_library_docs": {"library": "fixture-library", "ecosystem": "python"},
        "inspect_docs_target": {"target": {"library": "fixture-library"}},
        "validate_docs_manifest": {"manifest_path": "/fixture-project/manifest.json"},
        "prefetch_docs_manifest": {"manifest_path": "/fixture-project/manifest.json"},
        "refresh_library_docs": {"library": "fixture-library"},
        "prune_library_docs": {"library": "fixture-library"},
        "remove_library_docs": {"canonical_id": "fixture:library", "project_path": "/fixture-project"},
        "clear_index": {"scope": "project-local", "project_path": "/fixture-project"},
        "cancel_docs_job": {"job_id": "fixture-job"},
    }


def _boundary_cases():
    """Authored expectations cover accepted controls and adjacent refusals."""
    cases = []

    def add(label, tool, payload, valid):
        cases.append((label, tool, deepcopy(payload), valid))

    context = {"question": "What does the original documentation say?"}
    add("context-positive", "get_docs_context", context, True)
    add("context-required", "get_docs_context", {}, False)
    for value in (None, False, True, 0, 1, "", [], {}):
        add(f"question-{value!r}", "get_docs_context", {"question": value}, False)
    for field in ("project_path", "library", "version", "module_path"):
        for value in (None, "", "literal", False, 1, [], {}):
            add(f"context-{field}-{value!r}", "get_docs_context", {**context, field: value},
                value is None or type(value) is str)
    for value in (None, "project", "module", "all", "ALL", "", False, True, 0, 1, [], {}):
        add(f"scope-{value!r}", "get_docs_context", {**context, "scope": value},
            value is None or (type(value) is str and value in ("project", "module", "all")))
    for index, (value, valid) in enumerate((
        (None, True), ([], True), (["x"], True), ([str(i) for i in range(5)], True),
        ([str(i) for i in range(6)], False), (["x", "x"], False), ([""], False),
        (["x" * 500], True), (["x" * 501], False), ([False], False), ([1], False),
        ("x", False), (False, False), ({}, False),
    )):
        add(f"lookups-{index}", "get_docs_context", {**context, "lookup_queries": value}, valid)
    for field in ("unknown", "context_format"):
        for value in (None, "patch_context"):
            add(f"context-{field}-{value}", "get_docs_context", {**context, field: value}, False)

    for action, fields in _prepare_fixtures().items():
        positive = {"action": action, **fields}
        add(f"prepare-{action}", "prepare_docs", positive, True)
        for value in (None, False, True, 0, 1, "true"):
            add(f"confirm-{action}-{value!r}", "prepare_docs", {**positive, "confirm": value},
                action == "clear_index" and (value is None or type(value) is bool))
        if action != "sync_project_docs":
            add(f"mutation-on-{action}", "prepare_docs", {**positive, "mutation": None}, False)
    for value in (None, False, True, 0, 1, "", "unknown", [], {}):
        add(f"prepare-action-{value!r}", "prepare_docs", {"action": value}, False)
        add(f"status-action-{value!r}", "docs_status", {"action": value}, False)
    add("prepare-required-action", "prepare_docs", {}, False)
    add("status-required-action", "docs_status", {}, False)
    for action in ("project", "library", "jobs", "job"):
        add(f"status-{action}", "docs_status", {"action": action}, True)
    for value in (None, 1, 1.0, 200, 0, 201, True, False, 1.5, "1"):
        add(f"status-limit-{value!r}", "docs_status", {"action": "jobs", "limit": value},
            value is None or (type(value) in (int, float) and float(value).is_integer() and 1 <= value <= 200))
    for value in (None, 1, 1.0, 5, 0, 6, True, False, 1.5, "1"):
        add(f"inspection-limit-{value!r}", "prepare_docs",
            {"action": "inspect_docs_target", "target": {"library": "fixture-library"}, "max_pages": value},
            value is None or (type(value) in (int, float) and float(value).is_integer() and 1 <= value <= 5))
    for action in ("sync_project_docs", "clear_index", "remove_library_docs"):
        positive = {"action": action, **_prepare_fixtures()[action]}
        for value in (None, "", False, 1, [], {}):
            add(f"required-project-{action}-{value!r}", "prepare_docs",
                {**positive, "project_path": value}, False)
        missing = deepcopy(positive)
        del missing["project_path"]
        add(f"missing-project-{action}", "prepare_docs", missing, False)
    for field in ("scope", "canonical_id"):
        action = "clear_index" if field == "scope" else "remove_library_docs"
        positive = {"action": action, **_prepare_fixtures()[action]}
        for value in (None, "", False, 1, [], {}):
            add(f"required-{field}-{value!r}", "prepare_docs", {**positive, field: value}, False)
        del positive[field]
        add(f"missing-{field}", "prepare_docs", positive, False)

    envelope = {"action": "sync_project_docs", "project_path": "/fixture-project"}
    original = _mutation_fixture()
    for field in original:
        missing = deepcopy(original)
        del missing[field]
        add(f"mutation-missing-{field}", "prepare_docs", {**envelope, "mutation": missing}, False)
    for value in (None, False, 0, 1, 1.0, "true", [], {}):
        changed = {**original, "confirm": value}
        add(f"literal-confirm-{value!r}", "prepare_docs", {**envelope, "mutation": changed}, False)
    for value in (None, "ingest_project_docs", "", False, 1):
        changed = {**original, "operation": value}
        add(f"operation-{value!r}", "prepare_docs", {**envelope, "mutation": changed}, False)
    for value in (None, "gen-" + "a" * 32, "gen-" + "a" * 31, "gen-" + "a" * 33,
                  "gen-" + "a" * 32 + "\n", "gen-" + "A" * 32, "", False, 1):
        changed = {**original, "expected_generation_id": value}
        add(f"generation-{value!r}", "prepare_docs", {**envelope, "mutation": changed},
            value is None or value == "gen-" + "a" * 32)
    for field, prefix, nested in (("catalog_sha256", "", False), ("content_sha256", "", True),
                                  ("catalog_entry_hash", "sha256:", True)):
        for index, value in enumerate((prefix + "a" * 64, prefix + "a" * 63, prefix + "a" * 65,
                                      prefix + "a" * 64 + "\n", prefix + "A" * 64,
                                      None, "", False, 1)):
            changed = deepcopy(original)
            (changed["documents"][0] if nested else changed)[field] = value
            add(f"digest-{field}-{index}", "prepare_docs", {**envelope, "mutation": changed}, index == 0)
    for index, (path, valid) in enumerate((("docs/guide.md", True), ("docs/Руководство.md", True),
                                        ("", False), ("../secret", False), ("a/../secret", False),
                                        ("./guide", False), ("/absolute", False), ("a\\b", False),
                                        ("a:b", False), (None, False), (1, False))):
        changed = deepcopy(original)
        changed["documents"][0]["path"] = path
        add(f"member-path-{index}", "prepare_docs", {**envelope, "mutation": changed}, valid)
    for size in (0, 1, 500, 501):
        changed = deepcopy(original)
        changed["documents"] = [{**original["documents"][0], "path": f"docs/{i}.md"} for i in range(size)]
        add(f"member-count-{size}", "prepare_docs", {**envelope, "mutation": changed}, 1 <= size <= 500)
    changed = deepcopy(original)
    changed["documents"] *= 2
    add("member-duplicate", "prepare_docs", {**envelope, "mutation": changed}, False)
    for level in ("mutation", "document"):
        changed = deepcopy(original)
        (changed if level == "mutation" else changed["documents"][0])["unknown"] = True
        add(f"unknown-{level}", "prepare_docs", {**envelope, "mutation": changed}, False)
    for field in original["documents"][0]:
        changed = deepcopy(original)
        del changed["documents"][0][field]
        add(f"member-missing-{field}", "prepare_docs", {**envelope, "mutation": changed}, False)

    # Preserve permissive *schema* corners too. Runtime validation remains stricter.
    add("nullable-mutation-schema", "prepare_docs", {**envelope, "mutation": None}, True)
    add("unknown-prepare-schema", "prepare_docs", {"action": "prune_library_docs", "unknown": 1}, True)
    add("unknown-status-schema", "docs_status", {"action": "jobs", "unknown": 1}, True)
    return cases


def test_pr211_catalog_baseline_is_exact():
    raw = BASELINE_PATH.read_bytes()
    assert len(raw) == 7602
    assert hashlib.sha256(raw).hexdigest() == BASELINE_SHA256
    assert raw == json.dumps(json.loads(raw), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")


def test_pr211_catalog_preserves_all_remaining_schema_constraints():
    previous, current = _catalogs()
    assert tuple(previous) == tuple(current) == ("get_docs_context", "prepare_docs", "docs_status")
    for name, old in previous.items():
        jsonschema.Draft202012Validator.check_schema(old["inputSchema"])
        jsonschema.Draft202012Validator.check_schema(current[name]["inputSchema"])
        before = deepcopy(old["inputSchema"])
        assert _normalized_schema(before) == _normalized_schema(current[name]["inputSchema"]), name
        assert old.get("outputSchema") == current[name].get("outputSchema"), name


def test_pr211_catalog_boundary_acceptance_matches_independent_baseline():
    previous, current = _catalogs()
    validators = {name: (jsonschema.Draft202012Validator(old["inputSchema"]),
                         jsonschema.Draft202012Validator(current[name]["inputSchema"]))
                  for name, old in previous.items()}
    cases = _boundary_cases()
    assert len({case[0] for case in cases}) == len(cases)
    for label, name, payload, valid in cases:
        before, after = validators[name]
        assert before.is_valid(payload) is valid, ("baseline", label)
        assert after.is_valid(payload) is valid, ("current", label)


def test_pr211_vector_field_preserves_nullable_type_and_action_restrictions():
    previous, current = _catalogs()
    schema = previous["prepare_docs"]["inputSchema"]
    validators = (jsonschema.Draft202012Validator(schema),
                  jsonschema.Draft202012Validator(current["prepare_docs"]["inputSchema"]))
    assert schema["properties"]["with_vectors"] == current["prepare_docs"]["inputSchema"]["properties"]["with_vectors"] == {
        "type": ["boolean", "null"], "default": False,
    }
    assert set(_prepare_fixtures()) == set(schema["properties"]["action"]["enum"])
    for action, fields in _prepare_fixtures().items():
        positive = {"action": action, **fields}
        for validator in validators:
            assert validator.is_valid(positive), action
            for value in (None, False, True, 0, 1, "true", [], {}):
                valid = action != "sync_project_docs" and (value is None or type(value) is bool)
                assert validator.is_valid({**positive, "with_vectors": value}) is valid, (action, value)


def test_pr211_unknown_fields_and_invalid_mutation_never_reach_service(monkeypatch):
    from docmancer.mcp import _docs_server_part01 as boundary

    effects = {"destructive_scope": 0, "service": 0, "handler": 0}

    def destructive_scope(name, arguments):
        effects["destructive_scope"] += 1
        return None

    def service_for_project(service, arguments, *, read_only_startup):
        assert read_only_startup is True
        effects["service"] += 1
        return service

    def handler(name, arguments, service):
        effects["handler"] += 1
        return {"status": "ok", "tool": name}

    monkeypatch.setattr(boundary, "_destructive_project_scope_error", destructive_scope)
    monkeypatch.setattr(boundary, "_service_for_project_path", service_for_project)
    actual = boundary.current_docs_surface({})
    surface = DocsMcpSurface(tools=actual.tools, handlers={spec.name: handler for spec in actual.tools})
    # The real dispatcher and current schemas reach each spy on this harmless
    # positive control. A validation_error label alone would not prove no effects.
    positive = call_docs_tool_payload("docs_status", {"action": "jobs"}, object(), surface=surface)
    assert positive["status"] == "ok"
    assert effects == {"destructive_scope": 1, "service": 1, "handler": 1}
    effects.update({key: 0 for key in effects})
    for name, payload in (
        ("get_docs_context", {"question": "Original?", "unknown": None}),
        ("prepare_docs", {"action": "prune_library_docs", "unknown": None}),
        ("docs_status", {"action": "jobs", "unknown": None}),
        ("prepare_docs", {"action": "prune_library_docs", "with_vectors": "false"}),
        ("prepare_docs", {"action": "prefetch_library_docs", "library": "fixture-library", "with_vectors": 1}),
        ("prepare_docs", {"action": "remove_library_docs", "canonical_id": "fixture:library",
                          "project_path": "/fixture-project", "with_vectors": []}),
        ("prepare_docs", {"action": "sync_project_docs", "project_path": "/fixture-project",
                          "mutation": {**_mutation_fixture(), "confirm": 1}}),
        ("prepare_docs", {"action": "sync_project_docs", "project_path": "/fixture-project",
                          "mutation": {**_mutation_fixture(), "catalog_sha256": "a" * 64 + "\n"}}),
    ):
        result = call_docs_tool_payload(name, payload, object(), surface=surface)
        assert result["error"]["reason_code"] == "validation_error", (name, payload)
        assert effects == {"destructive_scope": 0, "service": 0, "handler": 0}, (name, payload)
