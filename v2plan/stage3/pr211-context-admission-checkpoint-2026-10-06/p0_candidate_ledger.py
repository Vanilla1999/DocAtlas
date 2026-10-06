"""Lossless audit queue with enclosing owners and resolved static import edges.

This runner does not infer semantic decisions from names or allow a scan to
declare P0 complete. Unknown decisions and dynamic calls remain explicit.
"""
from __future__ import annotations

import ast
import hashlib
import gzip
import json
from collections import Counter
from pathlib import Path

from p0_structural_classification import classify_node


BASE = Path("v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06")

# Reviewed declarations only. Exact source-symbol identities are audit evidence,
# never runtime query triggers. A new declaration is not covered by resemblance.
REVIEWED_DECLARATIONS = {
    "docmancer/agent.py": {"_PARSERS": ("D33", "TECHNICAL-RETAIN-CANDIDATE")},
    "docmancer/docs/domain/project_retrieval_intent.py": {"_INTENT_ROLE_POLICY": ("D01", "REMOVE"), "mapping": ("D01", "REMOVE")},
    "docmancer/docs/domain/documentation_query_plan.py": {"_ORIGINAL_RETRIEVAL_INTENTS": ("D02", "REMOVE"), "_HOST_AUDITED_RETRIEVAL_INTENTS": ("D02", "REMOVE")},
    "docmancer/docs/domain/project_query_intent.py": {"PACKS_MCP_PHRASES": ("D03", "REMOVE"), "_DOCS_MCP_PHRASES": ("D03", "REMOVE")},
    "docmancer/docs/domain/question_surface_normalization.py": {"_SEMANTIC_IDENTITIES": ("D05", "REMOVE"), "_RU_SEMANTIC_ALIASES": ("D05", "REMOVE")},
    "docmancer/core/_sqlite_store_shared.py": {"_BOILERPLATE_KEYWORDS": ("D11", "REMOVE"), "_QUERY_STOPWORDS": ("D11", "REMOVE"), "_GENERIC_QUERY_TERMS": ("D11", "REMOVE")},
    "docmancer/docs/domain/context_windows.py": {"_QUERY_STOP_WORDS": ("D20", "REMOVE")},
    "docmancer/docs/domain/query_terms.py": {"_REQUEST_FRAMING_TERMS": ("D20", "REMOVE"), "_SUPPLEMENTAL_FUNCTION_WORDS": ("D20", "REMOVE")},
    "docmancer/retrieval/query_planning.py": {"_STOPWORDS": ("D20", "REMOVE")},
    "docmancer/docs/domain/legacy_question_coverage.py": {"_STOP_TOKENS": ("D20", "REMOVE"), "_GENERIC_LIST_TOKENS": ("D20", "REMOVE")},
    "docmancer/docs/domain/admission_grammar.py": {name: ("D21", "REMOVE") for name in ("_WORDS", "_FORMS", "_ACTIONS", "_STATES", "_PATTERNS")},
    "docmancer/docs/domain/question_plan_proof.py": {"canonical": ("D23", "REMOVE"), "_REQUIREMENT_STOP_WORDS": ("D25", "REMOVE"), "_GOVERNANCE_STOP_WORDS": ("D25", "REMOVE")},
    "docmancer/docs/domain/_answer_units_part01.py": {"canonical": ("D23", "REMOVE")},
    "docmancer/docs/domain/_answer_units_part02.py": {"aliases": ("D24", "REMOVE")},
    "docmancer/docs/domain/question_premise_proof.py": {"_ACTION_FORMS": ("D25", "REMOVE"), "_STOP_TARGET_TOKENS": ("D25", "REMOVE"), "_NUMBER_VALUES": ("D28", "SPLIT")},
    "docmancer/docs/domain/governance_value_proof.py": {"_STOP_WORDS": ("D25", "REMOVE")},
    "docmancer/docs/domain/query_reference_binding.py": {name: ("D26", "REMOVE") for name in ("_NON_ENTITY_ACTORS", "_PREDICATES", "_ROLE_WORDS")},
    "docmancer/docs/domain/technical_terms.py": {"_IRREGULAR_SINGULARS": ("D26", "REMOVE"), "_COMMAND_PREFIX_RE": ("D26", "REMOVE"), "_COMMAND_SUFFIX_RE": ("D26", "REMOVE")},
    "docmancer/docs/domain/need_composition.py": {"_COUNT_WORDS": ("D28", "SPLIT")},
    "docmancer/docs/domain/_answer_units_shared.py": {"_NUMBER_WORD_VALUES": ("D28", "SPLIT")},
    "docmancer/docs/domain/_project_answer_contract_shared.py": {"_NUMBER_WORDS": ("D28", "SPLIT"), "_STOP_HINTS": ("D20", "REMOVE")},
    "docmancer/docs/application/_patch_constraints_service_shared.py": {"PHRASE_ALIASES": ("D29", "REMOVE"), "ASSET_TASK_TERMS": ("D30", "REMOVE"), "GENERIC_CALL_SYMBOLS": ("D30", "REMOVE")},
    "docmancer/docs/application/_patch_review_service_shared.py": {"LOW_VALUE_SYMBOLS": ("D30", "REMOVE"), "TASK_TOKEN_STOPWORDS": ("D30", "REMOVE")},
    "docmancer/docs/code_context.py": {"_LOW_SIGNAL_TERMS": ("D31", "REMOVE"), "_GENERIC_SOURCE_TERMS": ("D31", "REMOVE")},
    "docmancer/docs/domain/source_map.py": {"_QUERY_STOPWORDS": ("D31", "REMOVE"), "_KEYWORDS": ("D31", "TECHNICAL-RETAIN-CANDIDATE")},
    "docmancer/docs/discovery_candidates.py": {"_KNOWN_DISCOVERY_CANDIDATES": ("D32", "TECHNICAL-RETAIN-CANDIDATE")},
    "docmancer/docs/dart_official_docs.py": {"DART_PACKAGE_OFFICIAL_DOCS": ("D32", "TECHNICAL-RETAIN-CANDIDATE")},
    "docmancer/mcp/search.py": {"_SYNONYMS": ("D10", "REMOVE")},
    "docmancer/mcp/agent_config.py": {"ARGS": ("D33", "TECHNICAL-RETAIN-CANDIDATE"), "OPENCODE_MCP_ENVIRONMENT": ("D33", "TECHNICAL-RETAIN-CANDIDATE")},
    "docmancer/mcp/agent_workflow_contract.py": {"WORKFLOW_POLICY": ("D33", "SPLIT"), "PUBLIC_EXAMPLES": ("D33", "ILLUSTRATIVE-DATA"), "PUBLIC_TOOL_ORDER": ("D33", "TECHNICAL-RETAIN-CANDIDATE")},
    "docmancer/docs/domain/question_ownership.py": {"FROZEN_OWNERSHIP_CASES": ("D37", "SPLIT")},
    "docmancer/connectors/fetchers/github.py": {"_DOC_EXTENSIONS": ("D38", "TECHNICAL-RETAIN-CANDIDATE"), "_DEFAULT_EXCLUDE_FILES": ("D38", "SPLIT"), "_DEFAULT_EXCLUDE_FOLDERS": ("D38", "SPLIT")},
    "docmancer/connectors/fetchers/pipeline/filtering.py": {"_BLOCKLIST_PATTERNS": ("D38", "SPLIT"), "_ROOT_HINT_SEGMENTS": ("D38", "REMOVE"), "_LOCALE_PREFIXES": ("D38", "SPLIT"), "_STRIP_PARAMS": ("D38", "SPLIT")},
}

REVIEWED_MIXED_FUNCTIONS = {
    ("docmancer/docs/application/_project_context_service_part01.py", "_ProjectContextServicePart01.dependency_mentioned_in_question"): ("D14", "SPLIT"),
    ("docmancer/docs/application/_patch_constraints_service_part02.py", "_PatchConstraintsServicePart02._source_relevant_to_task"): ("D30", "SPLIT"),
    ("docmancer/docs/application/_patch_constraints_service_part02.py", "_PatchConstraintsServicePart02._source_relevance_terms"): ("D30", "SPLIT"),
    ("docmancer/docs/domain/technical_terms.py", "_explicit_command_context"): ("D26", "SPLIT"),
    ("docmancer/docs/domain/technical_terms.py", "infer_technical_kind"): ("D26", "SPLIT"),
}


def main() -> None:
    files = sorted(Path("docmancer").rglob("*.py"))
    pinned = json.loads(gzip.decompress((BASE / "archives/p0-dictionary-static-audit.json.gz").read_bytes()))
    pinned_hashes = {row["path"]: row["sha256"] for row in pinned["files"]}
    assert set(map(str, files)) == set(pinned_hashes), "Product file set changed; refresh/review source pin first"
    modules = {str(path.with_suffix("")).replace("/", ".").removesuffix(".__init__"): path for path in files}
    reviewed = {(row["path"], row["symbol"]): row["audit_decision"]
                for row in json.loads((BASE / "archives/p0-frame-symbol-decisions.json").read_text())["rows"]}
    candidates, imports, calls, symbols = [], [], [], []
    sources = []
    bridge_manifest = json.loads((BASE / "archives/p0-bridge-closure.json").read_text())
    bridge_exports = {}
    for facade in bridge_manifest["rows"]:
        for wrapper in facade["wrappers"]:
            bridge_exports.setdefault((wrapper["original_module"], wrapper["original_qualname"]), []).append(
                {"public_module": facade["public_module"], "public_class": facade["class"],
                 "method": wrapper["name"], "source_line": wrapper["source_line"],
                 "wrapper_globals_module": wrapper["wrapper_globals_module"]})
    for module, path in sorted(modules.items()):
        raw = path.read_bytes()
        source = raw.decode()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == pinned_hashes[str(path)], f"Reviewed source changed: {path}"
        tree = ast.parse(source)
        parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        sources.append({"path": str(path), "sha256": digest})

        def owners(node):
            result = []
            current = node
            while current in parent:
                current = parent[current]
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    result.append(current.name)
            return list(reversed(result))

        def assignment(node):
            current = node
            while current in parent:
                current = parent[current]
                if isinstance(current, ast.Assign):
                    return [ast.unparse(target) for target in current.targets]
                if isinstance(current, ast.AnnAssign):
                    return [ast.unparse(current.target)]
                if isinstance(current, (ast.FunctionDef, ast.ClassDef)):
                    break
            return []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append({"module": module, "path": str(path), "symbol": ".".join([*owners(node), node.name]),
                                "line": node.lineno, "end_line": node.end_lineno, "kind": type(node).__name__})
            if isinstance(node, (ast.ImportFrom, ast.Import)):
                if isinstance(node, ast.ImportFrom):
                    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
                    parts = package.split(".")
                    prefix = parts[:len(parts) - node.level + 1] if node.level else []
                    target = ".".join([*prefix, *([node.module] if node.module else [])])
                    names = [{"name": item.name, "asname": item.asname} for item in node.names]
                    resolved = [target] if target in modules else []
                    resolved.extend(target + "." + item.name for item in node.names if target + "." + item.name in modules)
                else:
                    target = None
                    names = [{"name": item.name, "asname": item.asname} for item in node.names]
                    resolved = [item.name for item in node.names if item.name in modules]
                imports.append({"path": str(path), "module": module, "line": node.lineno, "owner": owners(node),
                                "import_module": target, "names": names, "resolved_product_modules": sorted(set(resolved)),
                                "wildcard": any(item["name"] == "*" for item in names)})
            if isinstance(node, ast.Call):
                calls.append({"module": module, "path": str(path), "line": node.lineno, "owner": owners(node),
                              "callee": ast.unparse(node.func), "callee_kind": type(node.func).__name__})
            strings = [child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)]
            kind = None
            if isinstance(node, (ast.Dict, ast.Set, ast.Tuple, ast.List)) and strings:
                kind = "string_collection"
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in {"re", "_re"} and node.func.attr in {"compile", "search", "match", "fullmatch", "findall", "finditer", "sub"}:
                    kind = "regex_call"
                elif node.func.attr in {"startswith", "endswith", "replace", "casefold", "lower"}:
                    kind = "string_operation"
            elif isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops) and strings:
                kind = "membership_branch"
            if kind is None:
                continue
            chain = owners(node)
            targets = assignment(node)
            owner = chain[0] if chain else next((target for target in targets if target.isidentifier()), "<module>")
            decision = reviewed.get((str(path), owner))
            ast_hash = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            reviewed_declaration = REVIEWED_DECLARATIONS.get(str(path), {}).get(targets[0] if targets else "") if kind in {"string_collection", "regex_call"} else None
            restricted_owner = {
                ("docmancer/docs/domain/_answer_units_part01.py", "canonical"): "_context_score",
                ("docmancer/docs/domain/question_plan_proof.py", "canonical"): "_semantic_terms",
                ("docmancer/docs/domain/_answer_units_part02.py", "aliases"): "_attribute_aliases",
            }.get((str(path), targets[0] if targets else ""))
            if restricted_owner and (not chain or chain[0] != restricted_owner):
                reviewed_declaration = None
            structural_export = (kind == "string_collection" and targets == ["__all__"]
                                 and isinstance(node, (ast.List, ast.Tuple, ast.Set))
                                 and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.elts))
            if structural_export:
                reviewed_declaration = ("TECH-EXPORT", "TECHNICAL-RETAIN-CANDIDATE")
            normalization = (kind == "string_operation" and node.func.attr in {"casefold", "lower"}
                             and not node.args and not node.keywords)
            if normalization:
                reviewed_declaration = ("TECH-CASE", "TECHNICAL-RETAIN-CANDIDATE")
            review_reason = "Exact reviewed declaration contents; callers recorded in inventory/audits, per-site closure separate"
            mixed = REVIEWED_MIXED_FUNCTIONS.get((str(path), ".".join(chain)))
            if mixed and reviewed_declaration is None:
                reviewed_declaration = mixed
                review_reason = "Concrete mixed-function source reviewed: semantic branches migrate; literal syntax, bounds and source/authority checks must be preserved separately. Caller closure not implied."
            if structural_export:
                review_reason = "Literal __all__ export names; Python export interface, not query meaning. Exported implementations remain separately in scope."
            if normalization:
                review_reason = "Atomic built-in case normalization without custom mapping or replacement arguments; callers/branches remain separately in scope. No blanket exemption for identifier binding."
            structural = classify_node(node, path=str(path), assignment=targets, parent=parent, owner=".".join(chain))
            if reviewed_declaration is None and structural is not None:
                group, action, review_reason = structural
                reviewed_declaration = (group, action)
            candidates.append({"id": f"{path}:{node.lineno}:{node.col_offset}:{node.end_lineno}:{node.end_col_offset}:{kind}", "path": str(path),
                               "module": module, "source_sha256": digest, "line": node.lineno,
                               "column": node.col_offset, "end_line": node.end_lineno, "end_column": node.end_col_offset,
                               "owner": chain, "assignment": targets,
                               "kind": kind, "ast_sha256": ast_hash, "expression": ast.get_source_segment(source, node),
                               "real_bridge_exports": bridge_exports.get((module, ".".join(chain)), []),
                               "strings": strings, "prior_owner_decision": decision,
                               "candidate_decision": reviewed_declaration[1] if reviewed_declaration else None,
                               "group": reviewed_declaration[0] if reviewed_declaration else None,
                               "classification_status": "DECLARATION-REVIEWED" if reviewed_declaration else "REVIEW-REQUIRED",
                               "reason": review_reason if reviewed_declaration else "Prior enclosing-owner decision is evidence, not automatic per-candidate classification"})
    adjacency = {module: set() for module in modules}
    for edge in imports:
        adjacency[edge["module"]].update(edge["resolved_product_modules"])
    connector_manifest = json.loads((BASE / "archives/p0-connector-boundaries.json").read_text())
    dynamic_edges = []
    for parser in connector_manifest["parsers"]:
        assert parser["configured_identity"] == parser["actual_identity"]
        target, symbol = parser["actual_identity"].split(":")
        assert target in modules
        adjacency["docmancer.agent"].add(target)
        dynamic_edges.append({"from": "docmancer.agent", "to": target, "symbol": symbol,
                              "mechanism": "_PARSERS → _import_class → importlib.import_module",
                              "suffix": parser["suffix"], "actual_import_verified": True})
    roots = ["docmancer.__main__", "docmancer.cli.commands", "docmancer.mcp.docs_server", "docmancer.mcp.dispatcher"]
    reached = set()
    pending = [root for root in roots if root in modules]
    while pending:
        module = pending.pop()
        if module in reached:
            continue
        reached.add(module)
        pending.extend(adjacency[module] - reached)
    result = {"schema": "p0-complete-candidate-queue-v1", "sources": sources, "candidates": candidates,
              "symbols": symbols, "imports": imports, "call_sites": calls,
              "verified_dynamic_import_edges": dynamic_edges,
              "real_class_bridge_manifest": bridge_manifest,
              "static_import_reachability": {"roots": roots, "reached_modules": sorted(reached),
                                             "not_statically_reached_modules": sorted(set(modules) - reached)},
              "counts": {"files": len(files), "candidates": len(candidates), "by_kind": dict(Counter(row["kind"] for row in candidates)),
                         "prior_owner_decision_present": sum(row["prior_owner_decision"] is not None for row in candidates),
                         "reviewed_declaration_candidates": sum(row["candidate_decision"] is not None for row in candidates),
                         "pending_classification": sum(row["candidate_decision"] is None for row in candidates)},
              "limitations": ["Lossless queue, not completed classification", "Imports inside conditional/functions conservatively included",
                              "Static import reachability is not runtime call reachability", "Attribute/callback/wildcard/facade dispatch requires explicit review",
                              "Computed strings and environment-supplied routers remain in audit scope"]}
    assert len({row["id"] for row in candidates}) == len(candidates), "Candidate IDs collided"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
