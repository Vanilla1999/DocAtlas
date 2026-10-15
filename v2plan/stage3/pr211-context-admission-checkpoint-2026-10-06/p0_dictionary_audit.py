"""Read-only source audit; candidates are not automatic dictionary verdicts.

Run from the repository root. Output JSON on stdout; no imports of product code,
network requests, environment-variable values, or modifications to source files.
"""
from __future__ import annotations

import ast
import hashlib
import json
import platform
import re
import subprocess
from pathlib import Path


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    files = []
    containers = []
    imports = []
    regex_calls = []
    parse_errors = []
    for path in sorted(Path("docmancer").rglob("*.py")):
        raw = path.read_bytes()
        files.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        try:
            tree = ast.parse(raw, filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            parse_errors.append({"path": str(path), "error": str(exc)})
            continue
        # Include small inline collections: no previous eight-string threshold.
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in {"re", "_re"}
                    and node.func.attr in {"compile", "search", "match", "fullmatch", "findall", "finditer", "sub"}):
                regex_calls.append({"path": str(path), "line": node.lineno,
                                    "call": ast.unparse(node)})
            if isinstance(node, (ast.Dict, ast.Set, ast.Tuple, ast.List)):
                strings = [n.value for n in ast.walk(node)
                           if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                if strings:
                    containers.append({"path": str(path), "line": node.lineno,
                                       "kind": type(node).__name__, "strings": strings})
            elif isinstance(node, ast.ImportFrom):
                imports.append({"path": str(path), "line": node.lineno,
                                "module": node.module, "level": node.level,
                                "names": [{"name": a.name, "asname": a.asname}
                                          for a in node.names]})
            elif isinstance(node, ast.Import):
                imports.append({"path": str(path), "line": node.lineno,
                                "module": None, "level": 0,
                                "names": [{"name": a.name, "asname": a.asname}
                                          for a in node.names]})
    assets = []
    pattern = re.compile(r"alias|synonym|router|intent|rewrite|keyword|trigger", re.I)
    # Tracked config/template candidates only; no user config or credential reads.
    for name in git("ls-files").splitlines():
        path = Path(name)
        if path.suffix.lower() not in {".json", ".yaml", ".yml", ".toml", ".md", ".j2", ".txt"}:
            continue
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        hits = [{"line": i, "text": line} for i, line in enumerate(text.splitlines(), 1)
                if pattern.search(line)]
        if hits:
            assets.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "hits": hits})
    locks = [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in (Path("uv.lock"), Path("pyproject.toml")) if p.is_file()]
    result = {"schema": "dictionary-audit-candidates-v1", "head": git("rev-parse", "HEAD"),
              "branch": git("branch", "--show-current"),
              "main_ref": git("rev-parse", "refs/remotes/origin/main"),
              "merge_base": git("merge-base", "HEAD", "refs/remotes/origin/main"),
              "python": platform.python_version(), "locks": locks,
              "product_diff_sha256": hashlib.sha256(
                  git("diff", "--", "docmancer").encode()).hexdigest(),
              "files": files, "parse_errors": parse_errors,
              "string_containers": containers, "imports": imports,
              "regex_calls": regex_calls,
              "tracked_asset_candidates": assets,
              "limitations": ["Static candidates, not semantic classification or runtime reachability proof",
                              "Does not inspect external user config, installed distributions, or secrets",
                              "Computed strings and dynamic imports require manual review",
                              "main_ref is the local remote-tracking ref; no fetch performed"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
