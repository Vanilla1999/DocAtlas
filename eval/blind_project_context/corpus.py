"""Rebuild the frozen L0/L2 project corpora from git objects (sha256-verified).

L0 is the project's own documentation catalog and its 19 documents at
``L0_COMMIT``. L2 adds the Markdown stress documents recorded by the ACQ pilot
manifest (``eval/opencode_compat/acq_pilot/evidence/corpus-manifest.json``);
L0 files win on path collisions, additions are catalogued as active
project/source_of_truth documents exactly as in that pilot. Requires the git
history of this repository (CI: ``fetch-depth: 0``). Nothing is downloaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
L0_COMMIT = "3d21bfeaa5dfbfed26faa5dd85fc8a85bf9a7d90"
MANIFEST = ROOT / "eval/opencode_compat/acq_pilot/evidence/corpus-manifest.json"
CATALOG = "docatlas.project-docs.yaml"
CORPORA = ("L0", "L2")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def lock() -> dict:
    return json.loads((HERE / "corpus-lock.json").read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build(out: Path) -> dict[str, Path]:
    """Write ``out/L0/project`` and ``out/L2/project``; verify every byte."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = lock()
    if sha256(MANIFEST.read_bytes()) != expected["l2_manifest_sha256"]:
        raise RuntimeError("L2 corpus manifest changed")
    catalog_bytes = git_blob(L0_COMMIT, CATALOG)
    catalog = yaml.safe_load(catalog_bytes)
    l0_paths = [entry["path"] for entry in catalog["documents"]]
    projects = {name: out / name / "project" for name in CORPORA}
    for project in projects.values():
        if project.exists():
            raise FileExistsError(project)
    for path in l0_paths:
        data = git_blob(L0_COMMIT, path)
        for project in projects.values():
            _write(project / path, data)
    _write(projects["L0"] / CATALOG, catalog_bytes)
    entries = {entry["path"]: entry for entry in catalog["documents"]}
    for item in manifest["files"]:
        if item["path"] in entries:
            continue
        _write(projects["L2"] / item["path"], git_blob(manifest["additions_commit"], item["path"]))
        entries[item["path"]] = {
            "path": item["path"], "role": "other", "scope": "project",
            "description": "Project documentation: " + item["path"],
            "authority": "source_of_truth", "status": "active", "impact": "track",
        }
    l2_catalog = dict(catalog)
    l2_catalog["documents"] = list(entries.values())
    _write(projects["L2"] / CATALOG,
           yaml.safe_dump(l2_catalog, sort_keys=False, allow_unicode=True).encode("utf-8"))
    for name, documents in (("L0", catalog["documents"]), ("L2", l2_catalog["documents"])):
        for entry in documents:
            if entry.get("module_path"):
                (projects[name] / entry["module_path"]).mkdir(parents=True, exist_ok=True)
    errors = [item["path"] for item in manifest["files"]
              if sha256((projects["L2"] / item["path"]).read_bytes()) != item["sha256"]]
    for name in CORPORA:
        got = sha256((projects[name] / CATALOG).read_bytes())
        if got != expected["catalog_sha256"][name]:
            errors.append(f"{name}:{CATALOG}")
    if errors:
        raise RuntimeError(f"corpus bytes differ from the frozen manifest: {errors[:5]}")
    return projects


def documents(project: Path) -> dict[str, str]:
    """Catalogued documents of a built corpus as text (path -> UTF-8 text)."""
    catalog = yaml.safe_load((project / CATALOG).read_text(encoding="utf-8"))
    return {entry["path"]: (project / entry["path"]).read_text(encoding="utf-8")
            for entry in catalog["documents"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    for name, project in build(args.out).items():
        print(name, project, len(documents(project)))
