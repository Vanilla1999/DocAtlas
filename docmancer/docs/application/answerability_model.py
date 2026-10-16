"""Explicit host-only provisioner for the pinned CC-BY-4.0 QA model.

No runtime imports this downloader. It uses immutable upstream revision metadata;
the local manifest is trusted host configuration, not a model/tool argument.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
from .answerability import MODEL_REPO, MODEL_REVISION_PREFIX, MODEL_NAMES


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def provision(directory: Path):
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        raise ValueError("Refusing to overwrite a provisioned manifest; use a fresh private directory")
    info = get_json(f"https://huggingface.co/api/models/{MODEL_REPO}/revision/{MODEL_REVISION_PREFIX}?blobs=true")
    revision = info["sha"]
    if len(revision) != 40 or not revision.startswith(MODEL_REVISION_PREFIX):
        raise ValueError("Unexpected upstream revision")
    siblings = {s["rfilename"]: s for s in info["siblings"]}
    manifest = {"repo": MODEL_REPO, "revision": revision, "license": "CC-BY-4.0",
                "base_model": "deepset/roberta-base-squad2", "files": {}}
    for name in MODEL_NAMES:
        meta = siblings[name]
        expected = (meta.get("lfs") or {}).get("sha256")
        size = meta.get("size") or (meta.get("lfs") or {}).get("size")
        if not isinstance(size, int) or not 0 < size < 600_000_000:
            raise ValueError("Missing or oversized pinned asset")
        target = directory / name
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if target.exists() or target.is_symlink():
            raise ValueError("Refusing to overwrite model asset")
        fd, temp = tempfile.mkstemp(dir=target.parent, prefix=".answerability-")
        try:
            h, count = hashlib.sha256(), 0
            with os.fdopen(fd, "wb") as out, urllib.request.urlopen(
                f"https://huggingface.co/{MODEL_REPO}/resolve/{revision}/{name}", timeout=120
            ) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("HTTPS required")
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > size:
                        raise ValueError("Asset exceeds pinned size")
                    h.update(block)
                    out.write(block)
            if count != size or (expected and expected != h.hexdigest()):
                raise ValueError("Asset checksum/size mismatch")
            os.chmod(temp, 0o600)
            os.replace(temp, target)
        finally:
            Path(temp).unlink(missing_ok=True)
        manifest["files"][name] = {"bytes": count, "sha256": h.hexdigest()}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(manifest_path, 0o600)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    provision(parser.parse_args().directory)
