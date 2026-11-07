"""Offline literal-text accounting; no DocAtlas imports or model/runtime calls.

Uses the repository's pinned vocabulary through a locally constructed tiktoken
encoding. It never calls get_encoding(), downloads data, starts MCP, or runs tests.
Output is an artifact audit, not provider-token attribution or semantic proof.
"""
from __future__ import annotations

import argparse
import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path

import tiktoken


VOCABULARY_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
PATTERN = "|".join([
    r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
    r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
    r"\p{N}{1,3}", r" ?[^\s\p{L}\p{N}]+[\r\n/]*", r"\s*[\r\n]+", r"\s+(?!\S)", r"\s+",
])


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assigned_literal(tree: ast.AST, name: str):
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
            return ast.literal_eval(node.value)
    raise ValueError(f"Missing literal assignment {name}")


def static_value(node: ast.AST, known: dict):
    """Read only literal schema syntax and the two named size constants."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in known:
        return known[node.id]
    if isinstance(node, ast.List):
        return [static_value(v, known) for v in node.elts]
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                result.update(static_value(value, known))
            else:
                result[static_value(key, known)] = static_value(value, known)
        return result
    raise ValueError(f"Unsupported static schema syntax: {type(node).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw_vocabulary = gzip.decompress((repo / "docmancer/docs/data/o200k_base.tiktoken.gz").read_bytes())
    if sha(raw_vocabulary) != VOCABULARY_SHA256:
        raise ValueError("Unexpected tokenizer vocabulary")
    ranks = {base64.b64decode(token): int(rank)
             for token, rank in (line.split() for line in raw_vocabulary.splitlines())}
    encoder = tiktoken.Encoding(name="prompt_audit_vendored_o200k", pat_str=PATTERN,
                               mergeable_ranks=ranks, special_tokens={})
    texts, origins = {}, {}

    def read(name, relative):
        path = repo / relative
        texts[name] = path.read_text()
        origins[name] = {"path": str(path), "sha256": sha(path.read_bytes())}
        return texts[name]

    skill = read("repository_skill", "SKILL.md")
    # Separate packaging from behavior: the candidate is prompt text, not an
    # installable replacement skill. Header and guide links retain value elsewhere.
    skill_lines = skill.splitlines(keepends=True)
    texts["skill_workflow_without_metadata_heading_links"] = "".join(skill_lines[9:31]).rstrip() + "\n"
    texts["skill_metadata_heading_and_links"] = "".join(skill_lines[:9] + skill_lines[31:])
    agents = read("repository_AGENTS", "AGENTS.md")
    read("canonical_contract_template", "docmancer/templates/agent_contract.md")
    tool_source = read("tool_data_source", "docmancer/mcp/_docs_server_tool_data.py")
    texts.pop("tool_data_source")
    tool_tree = ast.parse(tool_source)
    descriptions = assigned_literal(tool_tree, "PUBLIC_ADVERTISED_DESCRIPTIONS")
    for name, description in descriptions.items():
        texts["public_description_" + name] = description
    constants = {}
    input_schemas = None
    for node in tool_tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) in {"_LOOKUP_TEXT_LIMIT", "_LOOKUP_COUNT_LIMIT"}:
                    constants[target.id] = ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "PUBLIC_ADVERTISED_INPUT_SCHEMAS":
            input_schemas = static_value(node.value, constants)
    if input_schemas is None:
        raise ValueError("Missing public input schemas")
    static_tools = []
    for name, description in descriptions.items():
        schema_text = json.dumps(input_schemas[name], ensure_ascii=False, separators=(",", ":"))
        texts["static_input_schema_" + name] = schema_text
        static_tools.append({"name": name, "description": description, "inputSchema": input_schemas[name]})
    texts["static_three_tools_text_fallback_projection"] = json.dumps(static_tools, ensure_ascii=False, separators=(",", ":"))
    shared_source = read("surface_builder_source", "docmancer/mcp/_docs_server_shared.py")
    texts.pop("surface_builder_source")
    for node in ast.walk(ast.parse(shared_source)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "description" for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                texts["minimal_context_description"] = node.value.value
    config_path = "eval/blind_project_context/step10-agent-evaluation/renewed-raw/L0/minimal-context/opencode.json"
    config_text = read("historical_config_source", config_path)
    texts.pop("historical_config_source")
    system = json.loads(config_text)["agents"]["measure"]["system"]
    if not system.endswith(skill):
        raise ValueError("Historical system no longer ends with the current skill")
    texts["historical_configured_system"] = system
    texts["historical_common_and_binding_prefix"] = system[:-len(skill)]
    capture_path = "eval/blind_project_context/step10-client-question-stdin/provider-1.json"
    capture_text = read("scripted_capture_source", capture_path)
    texts.pop("scripted_capture_source")
    request = json.loads(capture_text)
    captured_system = "\n".join(m["content"] for m in request["messages"] if m["role"] == "system")
    texts["scripted_capture_system"] = captured_system
    if captured_system.count(agents) != 1:
        raise ValueError("Expected exactly one byte-exact repository AGENTS in the historical capture")
    texts["scripted_capture_system_without_AGENTS_counterfactual"] = captured_system.replace(agents, "", 1)
    texts["scripted_capture_tools_json"] = json.dumps(request.get("tools", []), ensure_ascii=False, separators=(",", ":"))
    for name in ("candidate_workflow",):
        path = out / (name + ".txt")
        if path.exists():
            texts[name] = path.read_text()
            origins[name] = {"path": str(path), "sha256": sha(path.read_bytes())}
    prefix = ("Use only evidence retrieved from the designated frozen project corpus. "
              "Do not modify anything, use network search or delegate. Do not substitute "
              "knowledge of newer versions. This corpus is host-bound and documentation-language "
              "mode is enabled. Be concise but cover each requested aspect; answer the user, "
              "not the benchmark.\n\n")
    texts["candidate_consolidated_agent"] = prefix + texts["candidate_workflow"]
    path = out / "candidate_consolidated_agent.txt"
    path.write_text(texts["candidate_consolidated_agent"])
    origins["candidate_consolidated_agent"] = {"path": str(path), "sha256": sha(path.read_bytes())}
    minimal_addendum = texts["candidate_workflow"].split("\n\n")[-1]
    if not minimal_addendum.startswith("When the host enables minimal context,"):
        raise ValueError("Candidate conditional block changed; review applicability before recounting")
    texts["candidate_minimal_context_addendum"] = minimal_addendum
    texts["candidate_consolidated_only_if_minimal_context_disabled"] = texts["candidate_consolidated_agent"][:-len(minimal_addendum)].rstrip() + "\n"
    texts["historical_prefix_with_candidate_workflow"] = texts["historical_common_and_binding_prefix"] + texts["candidate_workflow"]
    rows = {name: {"tokens": len(encoder.encode(value, disallowed_special=())),
                   "utf8_bytes": len(value.encode()), "sha256": sha(value.encode())}
            for name, value in texts.items()}
    comparisons = []
    for before, after in [
        ("repository_skill", "candidate_workflow"),
        ("skill_workflow_without_metadata_heading_links", "candidate_workflow"),
        ("historical_configured_system", "historical_prefix_with_candidate_workflow"),
        ("historical_configured_system", "candidate_consolidated_agent"),
        ("candidate_consolidated_agent", "candidate_consolidated_only_if_minimal_context_disabled"),
        ("scripted_capture_system", "scripted_capture_system_without_AGENTS_counterfactual"),
    ]:
        if after in rows:
            old, new = rows[before]["tokens"], rows[after]["tokens"]
            comparisons.append({"before": before, "after": after, "before_tokens": old, "after_tokens": new,
                                "delta_tokens": new-old, "reduction_percent": (old-new)/old*100})
    result = {"schema": "offline-prompt-audit-1", "repository": str(repo),
              "source_commit": "9e2c331c45e8f9a86f809a1f4d66c43125250702",
              "method": "ordinary literal-text o200k_base, explicit local vocabulary; no DocAtlas runtime imports",
              "vocabulary_sha256": VOCABULARY_SHA256, "sources": origins,
              "text_measurements": rows, "comparisons": comparisons,
              "historical_capture": {"scripted_provider": True, "paid_model_calls": 0,
                                     "repository_AGENTS_exact_occurrences": captured_system.count(agents)},
              "conditional_fragment": {"name": "candidate_minimal_context_addendum",
                                       "omit_only_if": "actual target MCP runtime confirms minimal context is disabled",
                                       "unknown_mode": "keep the full candidate",
                                       "not_a_historical_baseline_comparison": True},
              "static_schema_scope": "Only the three base public name/description/inputSchema definitions in a conceptual text-fallback JSON projection. Excludes output schemas, host builtins, Code Mode lowering, advanced settings, minimal-mode overrides and the additional read_docs_source tool.",
              "boundaries": ["Not provider billing or attribution of the user-supplied 3068 system tokens.",
                             "Standalone text counts do not include message framing or all client-added text.",
                             "Static schemas are direct AST data, not a fresh installed tools/list or Code Mode prompt capture.",
                             "AGENTS counterfactual is historical attribution, not permission to remove repository instructions.",
                             "No answer-quality or behavioral equivalence claim from token counts or a rule checklist."]}
    (out / "measurements.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (out / "baseline_skill.txt").write_text(skill)
    (out / "baseline_configured_system.txt").write_text(system)
    (out / "baseline_public_descriptions.json").write_text(json.dumps(descriptions, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"text_measurements": rows, "comparisons": comparisons}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
