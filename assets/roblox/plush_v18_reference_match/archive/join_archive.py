"""Reconstruct the optional self-contained v18 ZIP from its four GitHub parts.

Usage: download part00..part03 beside this script, then `python join_archive.py`.
The ready-to-open .blend is also provided separately; this is only necessary
when the full builder/source/audit package is desired.
"""

from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEM = "Plush-v18-Reference-Match-Complete.zip"
EXPECTED_SHA256 = "e41ad54b268b44d40f28b7296bcc2e21744ee331863726674f98c35df8f82649"
PARTS = [HERE / f"{STEM}.part{i:02d}" for i in range(4)]

missing = [p.name for p in PARTS if not p.is_file()]
if missing:
    raise SystemExit(f"Please download all four parts first. Missing: {missing}")

data = b"".join(p.read_bytes() for p in PARTS)
actual = sha256(data).hexdigest()
if actual != EXPECTED_SHA256:
    raise SystemExit(f"Archive checksum mismatch: {actual}. No file was written.")

out = HERE / STEM
if out.exists():
    if sha256(out.read_bytes()).hexdigest() == EXPECTED_SHA256:
        print(f"Already assembled and verified: {out}")
        raise SystemExit(0)
    raise SystemExit(f"Refusing to overwrite an existing different archive: {out}")

out.write_bytes(data)
print(f"Assembled and SHA-256 verified: {out} ({len(data)} bytes)")
