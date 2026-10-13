"""Offline input freeze: no product imports, calls or oracle execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extra", type=Path, action="append", default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    paths = set(subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
    ).decode().split("\0"))
    selected = {
        name: sha(root / name) for name in sorted(paths)
        if name and (root / name).is_file()
        and name.startswith(("docmancer/", "tests/", "eval/heuristic_removal", "pyproject.toml"))
    }
    extras = {}
    for item in args.extra:
        files = sorted(item.rglob("*")) if item.is_dir() else [item]
        for path in files:
            if path.is_file():
                extras[str(path.resolve())] = sha(path)
    record = {
        "schema_version": 1,
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "root": str(root), "inputs_sha256": selected,
        "external_inputs_sha256": extras,
        "product_calls": 0, "status": "pre_execution_input_freeze",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"inputs": len(selected), "external": len(extras),
                      "manifest_sha256": sha(args.output)}))


if __name__ == "__main__":
    main()
