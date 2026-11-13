#!/usr/bin/env python3
"""Archive raw trace dirs losslessly, verify extracted SHA-256 against originals, then delete originals.

Per owner artifact-storage rules (AGENTS.md 2026-11-12): compressed archive + verified
SHA256 registry must exist before the uncompressed original is removed.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/home/viadmin/.local/share/docatlas-eval")
REGISTRY = BASE / "ARCHIVE_REGISTRY.json"

TARGETS = [
    "step15/work",
    "step14/work",
    "step16/recovered",
    "step16/paired-cache",
]


def file_hashes(root: Path) -> dict[str, tuple[str, int]]:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as fh:
                while block := fh.read(4 * 1024 * 1024):
                    size += len(block)
                    digest.update(block)
            out[str(path.relative_to(root))] = (digest.hexdigest(), size)
    return out


def main() -> int:
    registry = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else []
    failures = []
    for rel in TARGETS:
        src = BASE / rel
        if not src.is_dir():
            print(f"skip (missing): {rel}")
            continue
        archive = src.with_suffix(".tar.zst") if src.suffix else src.parent / (src.name + ".tar.zst")
        t0 = time.time()
        original = file_hashes(src)
        total_bytes = sum(size for _, size in original.values())
        if not archive.exists():
            subprocess.run(
                ["tar", "-I", "zstd -3", "-cf", str(archive), "-C", str(src.parent), src.name],
                check=True,
            )
        # Stream-verify: zstd decompresses into a plain tar stream hashed by
        # tarfile in streaming mode; no uncompressed data touches the disk.
        import tarfile
        verified = {}
        prefix = src.name + "/"
        zstd_proc = subprocess.Popen(["zstd", "-dc", str(archive)], stdout=subprocess.PIPE)
        with tarfile.open(fileobj=zstd_proc.stdout, mode="r|") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                digest = hashlib.sha256()
                stream = tar.extractfile(member)
                while block := stream.read(4 * 1024 * 1024):
                    digest.update(block)
                name = member.name
                if name.startswith(prefix):
                    name = name[len(prefix):]
                verified[name] = (digest.hexdigest(), member.size)
        zstd_proc.stdout.close()
        if zstd_proc.wait() != 0:
            raise RuntimeError(f"zstd decode failed for {archive}")
        mismatch = [name for name, (sha, _) in original.items() if verified.get(name, (None,))[0] != sha]
        size_mismatch = [name for name, (sha, size) in original.items()
                         if verified.get(name, (None, None))[1] != size]
        missing = sorted(set(original) - set(verified))
        if mismatch or missing or len(original) != len(verified) or size_mismatch:
            failures.append(rel)
            print(f"FAIL {rel}: hash_mismatches={len(mismatch)} missing={len(missing)} "
                  f"extra={len(verified) - len(original) + len(missing)} size_mismatches={len(size_mismatch)}")
            continue
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        registry.append({
            "original": str(src),
            "archive": str(archive),
            "archive_sha256": archive_sha,
            "archive_bytes": archive.stat().st_size,
            "original_bytes": total_bytes,
            "original_files": len(original),
            "verified": True,
            "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "duration_s": round(time.time() - t0, 1),
        })
        REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2))
        shutil.rmtree(src)
        print(f"OK {rel}: {len(original)} files, {total_bytes >> 20} MiB -> "
              f"{archive.stat().st_size >> 20} MiB, verified, original removed "
              f"({time.time() - t0:.0f}s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
