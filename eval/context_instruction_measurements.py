"""Measure instructions, not model quality or provider cost.

Parse baseline schemas without executing baseline code. Compare the installed
public schema in the same text-only host profile. Descriptions may shrink;
actual validation rules must not change.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path

NAMES = ("get_docs_context", "prepare_docs", "docs_status")


def baseline_tools(source):
    values = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in ("PUBLIC_ADVERTISED_DESCRIPTIONS", "PUBLIC_ADVERTISED_INPUT_SCHEMAS"):
                values[node.target.id] = ast.literal_eval(node.value)
    return [{"name": name, "description": values["PUBLIC_ADVERTISED_DESCRIPTIONS"][name],
             "inputSchema": values["PUBLIC_ADVERTISED_INPUT_SCHEMAS"][name]} for name in NAMES]


def validation(value):
    if isinstance(value, dict):
        return {k: validation(v) for k, v in value.items() if k != "description"}
    if isinstance(value, list):
        return [validation(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import tiktoken
    from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface
    current = [tool.to_tool_dict() for tool in build_docs_surface(DocsServerConfig(text_fallback=True)).tools]
    assert tuple(t["name"] for t in current) == NAMES
    prior = baseline_tools((args.baseline / "tools.py").read_text())
    assert [validation(t["inputSchema"]) for t in current] == [validation(t["inputSchema"]) for t in prior], "input validation drifted"
    files = (("root_skill", args.baseline / "SKILL.md", args.repo / "SKILL.md"),
             ("installed_bootstrap_template", args.baseline / "agent_contract.md", args.repo / "docmancer/templates/agent_contract.md"))
    source = {name: (old.read_text(), new.read_text()) for name, old, new in files}
    serialize = lambda data: json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    source["public_tools_text_host"] = (serialize(prior), serialize(current))
    result = {"baseline": "bde2a101032b204e6a4168c0e8a63f45040b3ddc",
              "boundary": "literal installed skill/templates and emitted schema text; no provider usage or model execution",
              "schema_validation_equal": True, "measurements": {}, "sha256": {}}
    for name, pair in source.items():
        result["sha256"][name] = [hashlib.sha256(text.encode()).hexdigest() for text in pair]
    for codec in ("o200k_base", "cl100k_base"):
        encoding = tiktoken.get_encoding(codec)
        rows = {}
        for name, (before, after) in source.items():
            old = len(encoding.encode(before, disallowed_special=()))
            new = len(encoding.encode(after, disallowed_special=()))
            rows[name] = {"before": old, "after": new, "saved": old-new,
                          "saved_percent": round(100*(1-new/old), 2)}
            assert new < old, (codec, name, old, new)
        result["measurements"][codec] = rows
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
