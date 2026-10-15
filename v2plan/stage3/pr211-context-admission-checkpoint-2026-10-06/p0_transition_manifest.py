"""Read-only transition manifest: package provenance, corpus and assertion inventory."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path


def digest(path: Path) -> dict[str, str]:
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    external_imports = []
    frame_symbols = []
    for path in sorted(Path("docmancer").rglob("*.py")):
        tree = ast.parse(path.read_bytes())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in {"eval", "tests"}:
                external_imports.append({"path": str(path), "line": node.lineno, "statement": ast.unparse(node)})
        if path.name.startswith(("question_plan", "question_frame", "question_semantic", "question_retrieval")):
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
                    frame_symbols.append({"path": str(path), "line": node.lineno,
                                          "symbol": node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else
                                          ast.unparse(node).split("=", 1)[0].strip(),
                                          "kind": type(node).__name__, "review": "OPEN unless covered by symbol audit"})
    test_paths = [Path("tests/docs") / name for name in (
        "test_direct_question_retrieval_intents.py", "test_context7_style_project_chat.py",
        "test_retrieval_alias_subject_binding.py", "test_query_planning_alias_regressions.py")]
    assertions = []
    for path in test_paths:
        tree = ast.parse(path.read_bytes())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("test_"):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Assert):
                    assertions.append({"test": f"{path}::{fn.name}", "line": node.lineno,
                                       "assertion": ast.unparse(node), "migration": "NO CHANGE / approval pending"})
    corpus_paths = []
    for directory in ("eval/project_context_quality", "eval/direct_docatlas_questions_15",
                      "eval/project_context_quality_v2"):
        corpus_paths.extend(p for p in sorted(Path(directory).rglob("*")) if p.is_file())
    corpus = []
    for p in corpus_paths:
        item = digest(p)
        if p.suffix == ".json":
            data = json.loads(p.read_text())
            if isinstance(data, dict) and isinstance(data.get("cases"), list):
                item["case_ids"] = [r.get("id") for r in data["cases"] if isinstance(r, dict)]
        corpus.append(item)
    try:
        dist = importlib.metadata.distribution("doc-atlas")
        package = {"version": dist.version, "location": str(dist.locate_file("")),
                   "direct_url": dist.read_text("direct_url.json"),
                   "record_available": dist.read_text("RECORD") is not None}
    except importlib.metadata.PackageNotFoundError:
        package = {"status": "not installed"}
    templates = [digest(p) for p in sorted(Path("docmancer/templates").glob("*.md"))]
    print(json.dumps({"schema": "p0-transition-manifest-v1", "python": platform.python_version(),
                      "executable": sys.executable, "distribution": package,
                      "external_product_imports": external_imports, "frame_symbols": frame_symbols,
                      "assertions": assertions, "corpus": corpus, "templates": templates,
                      "limitations": "Manifest is not completed classification, holdout approval, or clean-wheel runtime verification."},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
