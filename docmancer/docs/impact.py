from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from docmancer.docs.project import ProjectMetadataReader


_MODULE_ROOTS = {"packages", "apps", "services", "modules", "libs", "crates", "plugins", "components"}
_LIB_MODULE_ROOTS = {"modules", "features"}
_DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "pubspec.yaml", "pubspec.lock", "Cargo.toml", "Cargo.lock",
    "pyproject.toml", "poetry.lock", "uv.lock", "requirements.txt",
}


def changed_files_from_git(project_path: str | Path, base: str, head: str = "HEAD") -> list[str]:
    """Return normalized changed paths for two git refs without shell interpolation."""

    root = Path(project_path).expanduser().resolve()
    completed = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--diff-filter=ACDMR", base, head],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or "git diff failed"
        raise ValueError(f"Could not read changed files for {base}..{head}: {message}")
    return _normalized_paths(completed.stdout.splitlines())


def analyze_docs_impact(project_path: str | Path, changed_files: list[str]) -> dict[str, Any]:
    """Map a code diff to maintained project docs without writing repository files."""

    root = Path(project_path).expanduser().resolve()
    metadata = ProjectMetadataReader().read(root)
    changed = _normalized_paths(changed_files)
    candidates = [candidate for candidate in metadata.docs_candidates if candidate.path]
    candidates_by_path = {candidate.path: candidate for candidate in candidates}
    module_docs: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        if candidate.module_path:
            module_docs[candidate.module_path].append(candidate.path)
    root_readmes = [
        candidate.path
        for candidate in candidates
        if candidate.doc_scope == "project" and candidate.reason == "root_readme"
    ]

    updated_docs = sorted(path for path in changed if path in candidates_by_path)
    code_changes = [path for path in changed if path not in candidates_by_path and not _is_test_path(path)]
    impacts: dict[str, dict[str, Any]] = {}
    missing_modules: set[str] = set()
    missing_root_readme = False

    for path in code_changes:
        module_path = _module_path(path)
        docs = module_docs.get(module_path or "", [])
        if docs:
            reason = "module_dependency_metadata_changed" if Path(path).name in _DEPENDENCY_FILES else "module_code_changed"
            for doc_path in docs:
                _add_impact(impacts, doc_path, reason=reason, changed_file=path, module_path=module_path)
            continue
        if module_path:
            missing_modules.add(module_path)
            continue
        if Path(path).name in _DEPENDENCY_FILES:
            if root_readmes:
                for doc_path in root_readmes:
                    _add_impact(impacts, doc_path, reason="dependency_metadata_changed", changed_file=path, module_path=None)
            else:
                missing_root_readme = True
            continue
        for candidate in candidates:
            if candidate.reason in {"architecture", "root_readme"} or candidate.path == "docs/INDEX.md":
                _add_impact(impacts, candidate.path, reason="project_code_changed", changed_file=path, module_path=None)

    for doc_path in updated_docs:
        item = impacts.setdefault(doc_path, {
            "path": doc_path,
            "status": "updated",
            "reasons": [],
            "changed_files": [],
            "module_path": candidates_by_path[doc_path].module_path,
        })
        item["status"] = "updated"
        item["reasons"] = list(dict.fromkeys([*item["reasons"], "documentation_changed"]))
        item["changed_files"] = list(dict.fromkeys([*item["changed_files"], doc_path]))

    missing = [{
        "module_path": module_path,
        "reason": "module_code_changed_without_module_docs",
        "suggested_path": f"{module_path}/README.md",
    } for module_path in sorted(missing_modules)]
    if missing_root_readme:
        missing.append({
            "module_path": ".",
            "reason": "dependency_metadata_changed_without_root_readme",
            "suggested_path": "README.md",
        })
    impact_rows = sorted(impacts.values(), key=lambda item: item["path"])
    review_required = [item for item in impact_rows if item["status"] == "review_required"]
    return {
        "schema_version": "docs-impact-1",
        "project_path": str(root),
        "changed_files": changed,
        "summary": {
            "changed_files": len(changed),
            "code_files": len(code_changes),
            "docs_updated": len(updated_docs),
            "docs_to_review": len(review_required),
            "missing_docs": len(missing),
        },
        "impacts": impact_rows,
        "missing": missing,
        "recommendation": _recommendation(review_required, missing),
        "warnings": metadata.warnings,
    }


def format_docs_impact_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "## DocAtlas documentation impact",
        "",
        f"Changed files: **{summary['changed_files']}** · docs updated: **{summary['docs_updated']}** · docs to review: **{summary['docs_to_review']}** · missing docs: **{summary['missing_docs']}**.",
        "",
    ]
    impacts = report.get("impacts") or []
    if impacts:
        lines.extend(["### Reviewable documentation", "", "| Document | Status | Why |", "|---|---|---|"])
        for item in impacts:
            reasons = ", ".join(item.get("reasons") or [])
            lines.append(f"| `{item['path']}` | {item['status']} | {reasons} |")
        lines.append("")
    missing = report.get("missing") or []
    if missing:
        lines.extend(["### Documentation gaps", ""])
        for item in missing:
            lines.append(f"- `{item['module_path']}` changed without module docs; consider `{item['suggested_path']}`.")
        lines.append("")
    lines.append(f"**Recommendation:** {report['recommendation']}")
    return "\n".join(lines)


def _add_impact(impacts: dict[str, dict[str, Any]], path: str, *, reason: str, changed_file: str, module_path: str | None) -> None:
    item = impacts.setdefault(path, {
        "path": path,
        "status": "review_required",
        "reasons": [],
        "changed_files": [],
        "module_path": module_path,
    })
    item["reasons"] = list(dict.fromkeys([*item["reasons"], reason]))
    item["changed_files"] = list(dict.fromkeys([*item["changed_files"], changed_file]))


def _module_path(path: str) -> str | None:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] in _MODULE_ROOTS:
        return "/".join(parts[:2])
    if len(parts) >= 3 and parts[0] == "lib" and parts[1] in _LIB_MODULE_ROOTS:
        return "/".join(parts[:3])
    return None


def _is_test_path(path: str) -> bool:
    parts = {part.lower() for part in Path(path).parts}
    name = Path(path).name.lower()
    test_suffixes = (
        "_test.py", "_test.go", ".test.js", ".spec.js", ".test.jsx", ".spec.jsx",
        ".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx",
    )
    return bool(parts & {"tests", "test", "__tests__"}) or name.startswith("test_") or name.endswith(test_suffixes)


def _normalized_paths(paths: list[str]) -> list[str]:
    return sorted({str(path).replace("\\", "/").strip("/") for path in paths if str(path).strip()})


def _recommendation(review_required: list[dict[str, Any]], missing: list[dict[str, Any]]) -> str:
    if missing:
        return "Create or link the missing module documentation, then review the affected docs before merge."
    if review_required:
        return "Review the listed docs for accuracy; no repository write is performed automatically."
    return "No maintained documentation changes are suggested by this diff."
