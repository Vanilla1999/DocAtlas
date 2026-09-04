#!/usr/bin/env python3
"""Apply the byte-for-byte reviewed Project Documentation Context DDD patch."""
from __future__ import annotations

import base64
import gzip
import hashlib
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = tuple(ROOT / ".github/ddd-patch" / f"part-{index:02d}.txt" for index in range(9))
PATCH_SHA256 = "e3a60a0832ab027a03c0582b11cc5e19fae327e84e86a05cbd0f0346ef806401"
DELIVERY_ONLY_FILES = (
    ".github/workflows/project-context-ddd-agent-fix.yml",
    ".github/workflows/project-context-ddd-apply.yml",
    ".github/workflows/project-context-ddd-final-transaction.yml",
    ".github/workflows/project-context-ddd-finalize.yml",
    ".github/workflows/project-context-ddd-second-pass.yml",
    ".github/workflows/project-context-ddd-watchdog.yml",
    "scripts/apply_project_context_ddd_closure.py",
    *(f".github/ddd-patch/part-{index:02d}.txt" for index in range(9)),
)


def run(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def output(result: subprocess.CompletedProcess[bytes]) -> str:
    return result.stdout.decode("utf-8", errors="replace")


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in PARTS if not path.is_file()]
    if missing:
        print("Missing reviewed patch parts:", ", ".join(missing))
        return 2

    encoded = "".join(path.read_text(encoding="ascii") for path in PARTS)
    try:
        patch = gzip.decompress(base64.b64decode(encoded, validate=True))
    except Exception as exc:
        print(f"Cannot decode reviewed patch: {exc}")
        return 2

    digest = hashlib.sha256(patch).hexdigest()
    if digest != PATCH_SHA256:
        print(f"Reviewed patch digest mismatch: expected {PATCH_SHA256}, got {digest}")
        return 2

    patch_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="docatlas-ddd-", suffix=".patch", delete=False) as handle:
            handle.write(patch)
            patch_path = Path(handle.name)

        check = run("git", "apply", "--check", str(patch_path))
        if check.returncode == 0:
            applied = run("git", "apply", "--whitespace=error", str(patch_path))
            if applied.returncode != 0:
                print(output(applied))
                return applied.returncode
            print(f"Applied reviewed DDD patch {digest}.")
        else:
            reverse = run("git", "apply", "--reverse", "--check", str(patch_path))
            if reverse.returncode != 0:
                print("Patch cannot be applied and is not already present.")
                print(output(check))
                print(output(reverse))
                return 3
            print(f"Reviewed DDD patch {digest} is already applied.")
    finally:
        if patch_path is not None:
            patch_path.unlink(missing_ok=True)

    for relative in DELIVERY_ONLY_FILES:
        (ROOT / relative).unlink(missing_ok=True)

    diff_check = run("git", "diff", "--check")
    if diff_check.returncode != 0:
        print(output(diff_check))
        return diff_check.returncode

    print("Removed all one-shot delivery files; product diff is ready for validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
