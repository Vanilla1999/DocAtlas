"""Restore losslessly archived diagnostic JSON; never run DocAtlas or a model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    manifest = json.loads((run_dir / "selection-archive-manifest.json").read_bytes())
    archive = run_dir / "selection-receipts.tar.xz"
    if digest(archive.read_bytes()) != manifest["archive_sha256"]:
        raise ValueError("archive SHA-256 differs from the recorded original")
    expected = {row["path"]: row for row in manifest["files"]}
    if len(expected) != manifest["file_count"]:
        raise ValueError("duplicate manifest members")
    written = 0
    with tarfile.open(archive, "r:xz") as bundle:
        members = bundle.getmembers()
        if len(members) != len(expected) or {member.name for member in members} != set(expected):
            raise ValueError("archive members differ from the manifest")
        for member in members:
            relative = PurePosixPath(member.name)
            if (not member.isfile() or relative.is_absolute() or ".." in relative.parts
                    or len(relative.parts) != 4 or relative.parts[0] != "calls"
                    or relative.parts[2] not in {"budget", "mini"}
                    or relative.name != "selection.json"):
                raise ValueError("unexpected archive member")
            record = expected[member.name]
            if member.size != record["bytes"]:
                raise ValueError("archive member size differs from manifest")
            content = bundle.extractfile(member).read()
            if digest(content) != record["sha256"]:
                raise ValueError("original diagnostic JSON hash mismatch")
            target = run_dir.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(run_dir):
                raise ValueError("destination escapes the selected run directory")
            if target.exists():
                if target.is_symlink() or digest(target.read_bytes()) != record["sha256"]:
                    raise ValueError("refusing to replace a different existing diagnostic file")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(content)
            written += 1
    return {"verified_original_files": len(expected), "restored_files": written,
            "raw_bytes": manifest["raw_bytes"], "model_calls": 0, "product_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path(__file__).resolve().parent / "attempt-01")
    print(json.dumps(restore(parser.parse_args().run_dir), indent=2))
