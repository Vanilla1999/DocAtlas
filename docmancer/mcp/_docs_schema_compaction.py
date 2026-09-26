"""Lossless schema factoring plus concise public-tool annotations."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_DESCRIPTIONS = {
    "get_docs_context": 'Source-grounded documentation tool. One call = one concrete question; original request unchanged, never a benchmark/evaluation or documentation-governance meta-question. For onboarding use scope=all without module filters (scope="all"); policy: scope="project"; module: scope="module". module_path always implies module scope. For module+repo make two bounded calls (module then project). Preserve explicit scope; never widen. Lookups never authorize an answer or edit. hard_stop=true blocks edits.',
    "prepare_docs": "Call only from get_docs_context recommended_next_action or explicit sync/refresh/index/prefetch. Honor approval; poll job_id via docs_status; retry unchanged on success.",
    "docs_status": "Read-only: user explicitly asks health/freshness/index/jobs, or poll prepare_docs job_id.",
}


def _remove_redundant_string_enum_types(value: Any) -> None:
    if isinstance(value, dict):
        allowed = value.get("enum")
        types = value.get("type")
        types = types if isinstance(types, list) else [types]
        if allowed and all(isinstance(item, str) for item in allowed) and "string" in types:
            value.pop("type")
        for child in value.values():
            _remove_redundant_string_enum_types(child)
    elif isinstance(value, list):
        for child in value:
            _remove_redundant_string_enum_types(child)


def compact_public_contract(name: str, schema: dict[str, Any], description: str):
    if name not in _DESCRIPTIONS:
        return schema, description
    schema = deepcopy(schema)
    _remove_redundant_string_enum_types(schema)
    props = schema["properties"]
    if name == "get_docs_context":
        props["question"]["description"] = "One concrete question; independent questions: separate calls."
        props["lookup_queries"]["description"] = "Same question only: cross-language, comparison, conditional or dependent facets use 1–3 short lookups in the documentation language; simple single-facet needs none. Original question unchanged. Preserve exact identifiers, versions, conditions, negation, comparison sides. Never batch independent questions; no expected answer or guessed source names."
        props["scope"]["description"] = "project=repo-level docs only; module=one module; all=repo-level plus modules; same repository."
        props["version"]["description"] = "Omit for current project; exact/historical only; re-query after lockfile changes."
    elif name == "prepare_docs":
        props["confirm"]["description"] = "Second-call clear_index apply only."
        paths = [props[key]["items"] for key in ("changed_paths", "deleted_paths")]
        paths.extend(props["renamed_paths"]["items"]["properties"].values())
        # Keep type inside the reference AND inline: older JSON Schema dialects
        # ignore siblings of $ref. Never turn a string-only path into any value.
        if all(path == paths[0] for path in paths) and "$defs" not in schema:
            schema["$defs"] = {"p": deepcopy(paths[0])}
            for path in paths:
                path.clear()
                path.update({"type": "string", "$ref": "#/$defs/p"})
        rules = schema.get("allOf", [])
        if len(rules) >= 2 and set(rules[0]) == {"if", "then"} and set(rules[1]) == {"if", "else"} and rules[0]["if"] == rules[1]["if"]:
            rules[0].update(rules.pop(1))
        delta_fields = ("changed_paths", "deleted_paths", "renamed_paths")
        for rule in rules:
            condition = rule.get("if", {})
            if condition.get("properties") == {"action": {"const": "sync_project_docs"}}:
                if "action" in schema.get("required", []):
                    condition.pop("required", None)
                expected = {"not": {"anyOf": [{"required": [key]} for key in delta_fields]}}
                if rule.get("else") == expected:
                    rule["else"] = {"properties": {key: False for key in delta_fields}}
        definitions = schema.setdefault("$defs", {})
        for kind, key in (("string", "s"), ("boolean", "b")):
            if key in definitions:
                continue
            # Draft7 ignores constraints next to $ref. Factor only pure types
            # with annotations; constrained scalars must remain inline.
            targets = [
                item for item in props.values()
                if item.get("type") == [kind, "null"]
                and set(item) <= {"type", "description", "default", "title", "examples"}
            ]
            if len(targets) < 8:
                continue
            definitions[key] = {"type": [kind, "null"]}
            for item in targets:
                item.pop("type")
                item["$ref"] = f"#/$defs/{key}"
    _remove_redundant_string_enum_types(schema)
    return schema, _DESCRIPTIONS[name]
