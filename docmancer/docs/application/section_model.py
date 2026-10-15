"""Explicit, checksum-pinned model provisioning; never imported by query execution."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

from .section_compression import MODEL_FILES, MODEL_REVISION


def download(directory: Path) -> None:
    directory = directory.expanduser().resolve()
    for name, (size, digest) in MODEL_FILES.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if (not target.is_symlink() and target.stat().st_size == size
                    and hashlib.sha256(target.read_bytes()).hexdigest() == digest):
                continue
            raise ValueError(f"Refusing to replace an unexpected asset: {target}")
        url = f"https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2/resolve/{MODEL_REVISION}/{name}"
        descriptor, temporary = tempfile.mkstemp(prefix=".minilm-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output, urllib.request.urlopen(url, timeout=60) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("Model download must remain HTTPS")
                count, checksum = 0, hashlib.sha256()
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > size:
                        raise ValueError("Model asset exceeds pinned size")
                    checksum.update(block)
                    output.write(block)
            if count != size or checksum.hexdigest() != digest:
                raise ValueError("Model asset failed checksum verification")
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    download(args.directory)
    print(f"Verified MiniLM {MODEL_REVISION} in {args.directory.resolve()}")


if __name__ == "__main__":
    main()
