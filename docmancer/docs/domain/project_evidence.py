from __future__ import annotations

import ast
import json
import re
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from docmancer.docs.domain.code_graph import CodeGraph


_MANIFESTS = ("pyproject.toml", "package.json", "Cargo.toml", "pubspec.yaml")
_RUNTIME_ACCESS_RE = re.compile(
    r"\b(?:process\.env(?:\.[A-Za-z_][A-Za-z0-9_]*)?|std::env::var|System\.getenv|Platform\.environment)\b"
)


def classify_project_evidence(
    root: Path,
    *,
    repo_map: list[dict[str, Any]],
    code_graph: CodeGraph | None,
) -> list[dict[str, Any]]:
    """Translate production repo-map/code-graph facts into section evidence.

    A path or filename never proves a category by itself. Every emitted category is
    backed by parsed manifest data, source syntax, or a resolved graph relationship.
    """
    evidence: dict[str, dict[str, list[str]]] = {}

    def add(category: str, *, paths: list[str], facts: list[str]) -> None:
        if not facts:
            return
        item = evidence.setdefault(category, {"paths": [], "facts": []})
        item["paths"] = list(dict.fromkeys([*item["paths"], *paths]))
        item["facts"] = list(dict.fromkeys([*item["facts"], *facts]))

    manifest_facts, entrypoint_targets, build_facts, test_facts = _manifest_facts(root)
    if manifest_facts:
        add("manifests", paths=[fact[0] for fact in manifest_facts], facts=[fact[1] for fact in manifest_facts])

    mapped_symbols = _mapped_symbols(repo_map)
    verified_entrypoints = _verified_entrypoints(entrypoint_targets, mapped_symbols)
    if verified_entrypoints:
        paths = [path for path, _fact in verified_entrypoints]
        facts = [fact for _path, fact in verified_entrypoints]
        add("root entrypoints", paths=paths, facts=facts)
        add("entrypoints", paths=paths, facts=facts)

    runtime_facts = _runtime_configuration_facts(root, repo_map)
    if runtime_facts:
        add(
            "runtime configuration",
            paths=[path for path, _fact in runtime_facts],
            facts=[fact for _path, fact in runtime_facts],
        )

    module_paths, module_facts = _module_directory_facts(code_graph)
    if module_facts:
        add("module directories", paths=module_paths, facts=module_facts)

    import_paths, import_facts = _module_import_facts(code_graph)
    if import_facts:
        add("module imports", paths=import_paths, facts=import_facts)

    if build_facts and test_facts:
        add(
            "test and build configuration",
            paths=list(dict.fromkeys([fact[0] for fact in [*build_facts, *test_facts]])),
            facts=[fact[1] for fact in [*build_facts, *test_facts]],
        )

    return [
        {"category": category, "paths": value["paths"], "facts": value["facts"]}
        for category, value in evidence.items()
    ]


def _manifest_facts(root: Path) -> tuple[
    list[tuple[str, str]], dict[str, tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]
]:
    manifests: list[tuple[str, str]] = []
    entrypoints: dict[str, tuple[str, str]] = {}
    build: list[tuple[str, str]] = []
    tests: list[tuple[str, str]] = []
    for name in _MANIFESTS:
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if name == "pyproject.toml":
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                project = data.get("project") if isinstance(data.get("project"), dict) else {}
                if project.get("name"):
                    manifests.append((name, f"parsed project name: {project['name']}"))
                scripts = project.get("scripts") if isinstance(project.get("scripts"), dict) else {}
                for script_name, target in scripts.items():
                    if isinstance(target, str) and ":" in target:
                        entrypoints[str(script_name)] = (name, target)
                if isinstance(data.get("build-system"), dict) and data["build-system"].get("build-backend"):
                    build.append((name, f"build backend: {data['build-system']['build-backend']}"))
                tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
                if any(key in tool for key in ("pytest", "coverage", "tox")):
                    tests.append((name, "parsed Python test tool configuration"))
            elif name == "package.json":
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("name"):
                    manifests.append((name, f"parsed package name: {data['name']}"))
                scripts = data.get("scripts") if isinstance(data, dict) and isinstance(data.get("scripts"), dict) else {}
                if isinstance(scripts.get("build"), str):
                    build.append((name, "parsed build script"))
                if isinstance(scripts.get("test"), str):
                    tests.append((name, "parsed test script"))
                for field in ("bin", "main"):
                    value = data.get(field) if isinstance(data, dict) else None
                    if isinstance(value, str):
                        entrypoints[field] = (name, value)
                    elif isinstance(value, dict):
                        for script_name, target in value.items():
                            if isinstance(target, str):
                                entrypoints[str(script_name)] = (name, target)
            elif name == "Cargo.toml":
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                package = data.get("package") if isinstance(data.get("package"), dict) else {}
                if package.get("name"):
                    manifests.append((name, f"parsed package name: {package['name']}"))
                if isinstance(data.get("build-dependencies"), dict) or package.get("build"):
                    build.append((name, "parsed Cargo build configuration"))
            elif name == "pubspec.yaml":
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("name"):
                    manifests.append((name, f"parsed package name: {data['name']}"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError, json.JSONDecodeError, yaml.YAMLError):
            continue
    return manifests, entrypoints, build, tests


def _mapped_symbols(repo_map: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for item in repo_map:
        path = str(item.get("path") or "")
        if not path:
            continue
        result[path] = {
            str(symbol.get("name"))
            for symbol in item.get("symbols") or []
            if isinstance(symbol, dict) and symbol.get("name")
        }
    return result


def _verified_entrypoints(
    targets: dict[str, tuple[str, str]], mapped_symbols: dict[str, set[str]]
) -> list[tuple[str, str]]:
    verified: list[tuple[str, str]] = []
    for script_name, (_manifest, target) in targets.items():
        if ":" in target:
            module, symbol = target.split(":", 1)
            suffix = module.replace(".", "/") + ".py"
            match = next(
                (path for path, symbols in mapped_symbols.items() if path.endswith(suffix) and symbol in symbols),
                None,
            )
            if match:
                verified.append((match, f"script {script_name!r} resolves to mapped symbol {target}"))
        else:
            normalized = target.removeprefix("./")
            if normalized in mapped_symbols:
                verified.append((normalized, f"manifest entrypoint {script_name!r} resolves to mapped source"))
    return verified


def _runtime_configuration_facts(root: Path, repo_map: list[dict[str, Any]]) -> list[tuple[str, str]]:
    facts: list[tuple[str, str]] = []
    for item in repo_map:
        relative = str(item.get("path") or "")
        path = root / relative
        if not relative or not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = _call_name(node.func)
                if name in {"os.getenv", "os.environ.get"}:
                    key = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else "<dynamic>"
                    facts.append((relative, f"runtime environment read via {name}({key!r})"))
                    break
        elif _RUNTIME_ACCESS_RE.search(text):
            facts.append((relative, "parsed runtime environment access expression"))
    return facts


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Subscript):
        return _call_name(node.value)
    return ""


def _module_directory_facts(code_graph: CodeGraph | None) -> tuple[list[str], list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for node in code_graph.nodes if code_graph else []:
        if node.kind == "file" and "/" in node.path:
            grouped[str(Path(node.path).parent)].add(node.path)
    qualified = {directory: paths for directory, paths in grouped.items() if len(paths) >= 2}
    paths = sorted({path for values in qualified.values() for path in values})
    facts = [f"code graph contains {len(values)} source files under module {directory}" for directory, values in sorted(qualified.items())]
    return paths, facts


def _module_import_facts(code_graph: CodeGraph | None) -> tuple[list[str], list[str]]:
    edges = [
        edge for edge in (code_graph.edges if code_graph else [])
        if edge.kind == "imports" and edge.from_path and edge.to_path and edge.to_node_id
    ]
    paths = sorted({str(path) for edge in edges for path in (edge.from_path, edge.to_path) if path})
    facts = [f"resolved import {edge.from_path} -> {edge.to_path}" for edge in edges]
    return paths, facts
