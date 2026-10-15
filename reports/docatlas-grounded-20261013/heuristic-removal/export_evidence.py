"""Copy the new evidence folder without overwriting unfamiliar destination bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    records = {}
    files = [p for p in sorted(source.rglob("*")) if p.is_file()]
    for path in files:
        relative = path.relative_to(source)
        target = destination / relative
        checksum = digest(path)
        if target.exists() and digest(target) != checksum:
            raise SystemExit(f"Refusing to overwrite different destination: {target}")
        records[str(relative)] = checksum
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(path, target)
        if digest(target) != records[str(path.relative_to(source))]:
            raise SystemExit(f"Hash mismatch: {target}")
    receipt = {"source": str(source), "destination": str(destination),
               "files_sha256": records, "verified": len(records), "mismatches": 0}
    receipt_path = destination.parent / "HEURISTIC_REMOVAL_EXPORT_MANIFEST.json"
    if receipt_path.exists():
        raise SystemExit(f"Receipt already exists; copied bytes verified: {receipt_path}")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"copied_verified": len(records), "mismatches": 0,
                      "receipt": str(receipt_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
