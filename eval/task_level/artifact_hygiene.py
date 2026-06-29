from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

RUNTIME_DIR_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".hypothesis",
    ".tox",
    ".nox",
}
RUNTIME_FILE_NAMES = {
    ".coverage",
    "coverage.xml",
    ".DS_Store",
}
RUNTIME_SUFFIXES = (".pyc", ".pyo")
PRESERVED_LOCKFILES = {
    "pubspec.lock",
    "poetry.lock",
    "uv.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "go.sum",
}
PRESERVED_GENERATED_SUFFIXES = (
    ".g.dart",
    ".freezed.dart",
    ".pb.go",
    ".pb.dart",
)


@dataclass(frozen=True)
class PatchHygieneResult:
    filtered_changed_files: list[str]
    ignored_runtime_artifacts: list[str]
    preserved_generated_candidates: list[str]
    hygiene_warnings: list[str]
    raw_counts: dict[str, int]
    filtered_counts: dict[str, int]
    filtered_patch_diff: str

    def to_json_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("filtered_patch_diff", None)
        return data


def normalize_path(path: str) -> str:
    value = path.strip().replace("\\", "/")
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    return value.strip("/")


def is_runtime_artifact(path: str) -> bool:
    normalized = normalize_path(path)
    if not normalized:
        return False
    parts = normalized.split("/")
    name = parts[-1]
    if name in RUNTIME_FILE_NAMES:
        return True
    if name.endswith(RUNTIME_SUFFIXES):
        return True
    if any(part in RUNTIME_DIR_PARTS for part in parts):
        return True
    if len(parts) >= 2 and parts[0] in {"tmp", "temp"}:
        return True
    return False


def is_preserved_generated_candidate(path: str) -> bool:
    normalized = normalize_path(path)
    if not normalized:
        return False
    name = normalized.split("/")[-1]
    if name in PRESERVED_LOCKFILES:
        return True
    if normalized.endswith(PRESERVED_GENERATED_SUFFIXES):
        return True
    if ".generated." in name or ".generated." in normalized:
        return True
    if "generated" in normalized.split("/"):
        return True
    if normalized.startswith("dist/") or "/dist/" in normalized:
        return True
    return False


def paths_from_status_lines(raw_status_lines: list[str]) -> list[str]:
    paths: list[str] = []
    for line in raw_status_lines:
        if not line.strip():
            continue
        payload = line[3:] if len(line) > 3 else line
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        normalized = normalize_path(payload)
        if normalized:
            paths.append(normalized)
    return paths


def apply_patch_hygiene(*, raw_status_lines: list[str], raw_changed_files: list[str], raw_patch_diff: str) -> PatchHygieneResult:
    raw_changed = [normalize_path(path) for path in raw_changed_files if normalize_path(path)]
    status_paths = paths_from_status_lines(raw_status_lines)
    ignored = sorted({path for path in [*raw_changed, *status_paths] if is_runtime_artifact(path)})
    filtered = [path for path in raw_changed if not is_runtime_artifact(path)]
    preserved = [path for path in filtered if is_preserved_generated_candidate(path)]
    warnings: list[str] = []
    if ignored:
        warnings.append("runtime/cache artifacts were excluded from normalized patch metrics")
    return PatchHygieneResult(
        filtered_changed_files=filtered,
        ignored_runtime_artifacts=ignored,
        preserved_generated_candidates=preserved,
        hygiene_warnings=warnings,
        raw_counts={"changed_files": len(raw_changed), "status_paths": len(status_paths)},
        filtered_counts={
            "changed_files": len(filtered),
            "ignored_runtime_artifacts": len(ignored),
            "preserved_generated_candidates": len(preserved),
        },
        filtered_patch_diff=filter_patch_diff(raw_patch_diff),
    )


def filter_patch_diff(raw_patch_diff: str) -> str:
    if not raw_patch_diff:
        return ""
    sections: list[list[str]] = []
    current: list[str] = []
    for line in raw_patch_diff.splitlines(keepends=True):
        if line.startswith("diff --git ") and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append(current)
    kept = [line for section in sections if not _diff_section_is_runtime(section) for line in section]
    return "".join(kept)


def _diff_section_is_runtime(section: list[str]) -> bool:
    if not section:
        return False
    first = section[0]
    if not first.startswith("diff --git "):
        return False
    parts = first.strip().split()
    paths = [normalize_path(part) for part in parts[2:4]]
    return bool(paths) and all(is_runtime_artifact(path) for path in paths if path)


def write_patch_hygiene_artifacts(output_dir: Path, *, raw_status: str, raw_changed_files: list[str], raw_patch_diff: str) -> PatchHygieneResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_status_lines = raw_status.splitlines()
    hygiene = apply_patch_hygiene(
        raw_status_lines=raw_status_lines,
        raw_changed_files=raw_changed_files,
        raw_patch_diff=raw_patch_diff,
    )
    (output_dir / "patch.raw.diff").write_text(raw_patch_diff, encoding="utf-8")
    (output_dir / "patch.diff").write_text(hygiene.filtered_patch_diff, encoding="utf-8")
    (output_dir / "git_status.raw.txt").write_text(raw_status, encoding="utf-8")
    (output_dir / "git_status.txt").write_text("\n".join(line for line in raw_status_lines if not _status_line_is_runtime(line)) + ("\n" if raw_status_lines else ""), encoding="utf-8")
    (output_dir / "changed_files.raw.json").write_text(json.dumps([normalize_path(path) for path in raw_changed_files if normalize_path(path)], indent=2), encoding="utf-8")
    (output_dir / "changed_files.json").write_text(json.dumps(hygiene.filtered_changed_files, indent=2), encoding="utf-8")
    (output_dir / "ignored_runtime_artifacts.json").write_text(json.dumps(hygiene.ignored_runtime_artifacts, indent=2), encoding="utf-8")
    (output_dir / "patch_hygiene.json").write_text(json.dumps(hygiene.to_json_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return hygiene


def _status_line_is_runtime(line: str) -> bool:
    return any(is_runtime_artifact(path) for path in paths_from_status_lines([line]))


def diff_stats_from_patch(patch_text: str) -> tuple[int, int, int]:
    files: set[str] = set()
    added = 0
    removed = 0
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                path = normalize_path(parts[3])
                if path:
                    files.add(path)
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return len(files), added, removed
