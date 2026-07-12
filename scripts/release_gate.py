#!/usr/bin/env python3
"""Validate that release source metadata and the built artifacts agree."""
from __future__ import annotations

import argparse
import email
import hashlib
import json
import re
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ASSETS = ("docmancer/docs/curated_sources.json", "docmancer/support_surfaces.json")


def source_version() -> str:
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', (ROOT / "docmancer/_version.py").read_text())
    if not match:
        raise SystemExit("release gate: source version not found")
    return match.group(1)


def metadata(data: bytes) -> tuple[str, str]:
    parsed = email.message_from_bytes(data)
    return str(parsed["Name"]), str(parsed["Version"])


def inspect_artifact(path: Path) -> dict[str, object]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            meta = next(name for name in names if name.endswith(".dist-info/METADATA"))
            name, version = metadata(archive.read(meta))
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            names = archive.getnames()
            pkg_info = next(name for name in names if name.count("/") == 1 and name.endswith("/PKG-INFO"))
            member = archive.extractfile(pkg_info)
            assert member is not None
            name, version = metadata(member.read())
    else:
        raise SystemExit(f"release gate: unsupported artifact: {path}")
    missing = [asset for asset in REQUIRED_ASSETS if not any(n.endswith(asset) for n in names)]
    if missing:
        raise SystemExit(f"release gate: {path.name} missing package assets: {missing}")
    return {"file": path.name, "name": name, "version": version,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--tag")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    files = sorted([*args.dist.glob("*.whl"), *args.dist.glob("*.tar.gz")])
    if sum(p.suffix == ".whl" for p in files) != 1 or sum(p.name.endswith(".tar.gz") for p in files) != 1:
        raise SystemExit("release gate: dist must contain exactly one wheel and one sdist")
    version = source_version()
    if f"## [{version}]" not in (ROOT / "CHANGELOG.md").read_text():
        raise SystemExit(f"release gate: CHANGELOG has no [{version}] release heading")
    records = [inspect_artifact(path) for path in files]
    if {str(record["version"]) for record in records} != {version}:
        raise SystemExit(f"release gate: artifact/source versions disagree: {records} vs {version}")
    if {str(record["name"]) for record in records} != {"doc-atlas"}:
        raise SystemExit(f"release gate: unexpected project metadata: {records}")
    if args.tag and args.tag.removeprefix("v") != version:
        raise SystemExit(f"release gate: tag {args.tag} does not match {version}")
    payload = {"project": "doc-atlas", "version": version, "tag": args.tag, "artifacts": records}
    output = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        args.manifest.write_text(output)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
