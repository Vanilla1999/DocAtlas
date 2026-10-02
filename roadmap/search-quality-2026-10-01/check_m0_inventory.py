"""Emit reproducible static call sites for the migration boundaries.

This inventory includes all production Python callers, including compatibility
wrappers. Dynamic callback ownership is documented separately in the M0 report.
"""
import ast
import json
from pathlib import Path


BOUNDARIES = {
    "source_metadata_rejection_reason": "metadata eligibility",
    "evidence_policy_rejection_reason": "metadata plus legacy exclusions",
    "qualify_evidence": "mixed eligibility/relevance/support",
    "qualify_visible_trace": "compatibility qualification",
    "prepare_reference_probe": "reference identity/snapshot binding",
    "build_documentation_query_plan": "query planning",
    "build_project_retrieval_aliases": "NL retrieval hypotheses",
    "lifecycle_intent_for_question": "NL lifecycle inference",
    "is_change_request": "NL read/mutation routing",
    "build_mutation_intent": "mutation contract",
    "project_docs_context": "project read projection",
    "project_docs_answer": "answer certification projection",
    "_requalify_visible_source": "visible-window qualification",
    "has_context_hint_support": "hint relevance preference",
}


def main():
    calls = []
    definitions = []
    for path in sorted(Path("docmancer").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in BOUNDARIES:
                definitions.append(dict(path=str(path), line=node.lineno, symbol=node.name))
            if not isinstance(node, ast.Call):
                continue
            symbol = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None
            )
            if symbol in BOUNDARIES:
                calls.append(dict(path=str(path), line=node.lineno, symbol=symbol,
                                  boundary=BOUNDARIES[symbol]))
    assert all(any(row["symbol"] == symbol for row in definitions) for symbol in BOUNDARIES)
    print(json.dumps(dict(definitions=definitions, calls=calls,
                         limitations="Static names; aliases and dynamic callbacks require source review."),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
