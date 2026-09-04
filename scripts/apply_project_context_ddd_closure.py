#!/usr/bin/env python3
"""Apply the reviewed Project Documentation Context DDD patch and repair."""
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
REPAIR_PATCH_SHA256 = "0b8c6cddcc66cb189e0c2b0a51afeb8d6e7119cf859977d9d4509b95b322022a"
REPAIR_PATCH_B64 = (
    "LS0tIGEvZG9jbWFuY2VyL2RvY3MvZG9tYWluL2V2aWRlbmNlX3F1YWxpZmljYXRpb24ucHkKKysrIGIvZG9jbWFuY2VyL2RvY3MvZG9tYWluL2V2aWRlbmNlX3F1YWxpZmljYXRpb24ucHkKQEAgLTkzLDYgKzkzLDI1IEBACiAgICAgaWYgZXhhY3RfcGF0aF9tYXRjaDoKICAgICAgICAgcmV0dXJuIEV2aWRlbmNlUXVhbGlmaWNhdGlvbihUcnVlLCAicXVhbGlmaWVkX2V4YWN0X3BhdGgiKQogCisgICAgIyBTb21lIG5vbi1TUUxpdGUgYWRhcHRlcnMgYW5kIGxpZ2h0d2VpZ2h0IGVtYmVkZGluZyBmYWNhZGVzIGV4cG9zZSBvbmx5CisgICAgIyBhbiBleHBsaWNpdCBwcmVxdWFsaWZpY2F0aW9uIGJpdC4gIFNRTGl0ZSBuZXZlciBlbWl0cyB0aGF0IGJpdCBhbnltb3JlOworICAgICMgd2hlbiBubyB0ZXJtLWxldmVsIHJldHJpZXZhbCBmYWN0cyBleGlzdCwgZG9tYWluIHF1YWxpZmljYXRpb24gbWF5IHJldGFpbgorICAgICMgdGhlIGxlZ2FjeSBhZGFwdGVyIGRlY2lzaW9uIG9ubHkgYWZ0ZXIgYWxsIGlkZW50aXR5LCBsaWZlY3ljbGUsIHNhZmV0eSwKKyAgICAjIHJvbGUsIGZvcmJpZGRlbi10ZXJtIGFuZCB2aXNpYmxlLWJvZHkgY2hlY2tzIGFib3ZlIGhhdmUgcGFzc2VkLgorICAgIHRlcm1fZmFjdF9rZXlzID0gKAorICAgICAgICAicXVlcnlfdGVybXMiLAorICAgICAgICAibWF0Y2hlZF90ZXJtcyIsCisgICAgICAgICJtaXNzaW5nX3Rlcm1zIiwKKyAgICAgICAgImV4YWN0X3Rlcm1zIiwKKyAgICAgICAgIm1pc3NpbmdfZXhhY3RfdGVybXMiLAorICAgICAgICAiZmllbGRfbWF0Y2hlcyIsCisgICAgICAgICJleGFjdF9tYXRjaCIsCisgICAgKQorICAgIGlmIHJldHJpZXZhbF9mYWN0cy5nZXQoInF1YWxpZmllZCIpIGlzIFRydWUgYW5kIG5vdCBhbnkoCisgICAgICAgIGtleSBpbiByZXRyaWV2YWxfZmFjdHMgZm9yIGtleSBpbiB0ZXJtX2ZhY3Rfa2V5cworICAgICk6CisgICAgICAgIHJldHVybiBFdmlkZW5jZVF1YWxpZmljYXRpb24oVHJ1ZSwgInF1YWxpZmllZF92aXNpYmxlX2xlZ2FjeV90cmFjZSIpCisKICAgICBpbmZlcnJlZCA9IHF1ZXJ5X3Rlcm1fZmFjdHMobG9va3VwLnRleHQgaWYgbG9va3VwIGVsc2UgcmV0cmlldmFsX2ZhY3RzLmdldCgicXVlcnlfdGV4dCIpKQogICAgIHF1ZXJ5X3Rlcm1zID0gdHVwbGUoZGljdC5mcm9ta2V5cygKICAgICAgICAgc3RyKHZhbHVlKS5jYXNlZm9sZCgpLnJlcGxhY2UoItGRIiwgItC1IikKLS0tIGEvZG9jbWFuY2VyL2RvY3MvYXBwbGljYXRpb24vX3Byb2plY3RfZG9jc19zZXJ2aWNlX3BhcnQwMy5weQorKysgYi9kb2NtYW5jZXIvZG9jcy9hcHBsaWNhdGlvbi9fcHJvamVjdF9kb2NzX3NlcnZpY2VfcGFydDAzLnB5CkBAIC0xODksNiArMTg5LDExIEBACiAgICAgICAgIHByb2plY3RfaWRlbnRpdHkgPSBzdHIoCiAgICAgICAgICAgICBtZXRhZGF0YS5nZXQoInByb2plY3RfaWRlbnRpdHkiKQogICAgICAgICAgICAgb3IgbWV0YWRhdGEuZ2V0KCJyZXBvc2l0b3J5X2lkZW50aXR5IikKKyAgICAgICAgICAgICMgVGhlIHF1ZXJ5IHdhcyBhbHJlYWR5IGNvbnN0cmFpbmVkIGJ5IHRoZSBpbW11dGFibGUgcHJvamVjdAorICAgICAgICAgICAgIyBpZGVudGl0eSBmaWx0ZXIuIExpZ2h0d2VpZ2h0L2xlZ2FjeSBhZGFwdGVycyBkbyBub3QgYWx3YXlzIGVjaG8KKyAgICAgICAgICAgICMgdGhhdCBmaWx0ZXIgaW50byBldmVyeSByZXN1bHQsIHNvIG5vcm1hbGl6ZSB0aGUga25vd24gYm91bmRhcnkKKyAgICAgICAgICAgICMgZmFjdCBoZXJlIGluc3RlYWQgb2YgdHJlYXRpbmcgdGhlIGNhbmRpZGF0ZSBhcyBjcm9zcy1wcm9qZWN0LgorICAgICAgICAgICAgb3IgZXhwZWN0ZWRfcHJvamVjdF9pZGVudGl0eQogICAgICAgICAgICAgb3IgIiIKICAgICAgICAgKQogICAgICAgICBsaWZlY3ljbGVfc3RhdHVzID0gc3RyKApAQCAtNDQzLDggKzQ0OCwxNCBAQAogICAgICAgICAgICAgICAgICpxdWVyaWVzX2J5X29yaWdpbi5nZXQoImV4YWN0X2FuY2hvciIsIFtdKSwKICAgICAgICAgICAgIF0sCiAgICAgICAgICAgICBbWwotICAgICAgICAgICAgICAgICpfcXVhbGlmaWVkX3JldHJpZXZhbF9jaHVua3MoYXV0aG9yaXRhdGl2ZV9jaHVua3MpLAotICAgICAgICAgICAgICAgICpfcXVhbGlmaWVkX3JldHJpZXZhbF9jaHVua3MoY2h1bmtzKSwKKyAgICAgICAgICAgICAgICAjIFByZXNlcnZlIHRoZSBwcmltYXJ5IHJldHJpZXZhbCBsYW5lIGV2ZW4gd2hlbiBhIGNhbmRpZGF0ZSBpcworICAgICAgICAgICAgICAgICMgbm90IHF1YWxpZmllZCBmb3IgcHVibGljIGNvdmVyYWdlLiAgUXVhbGlmaWNhdGlvbiByZW1haW5zIGluCisgICAgICAgICAgICAgICAgIyBtZXRhZGF0YSBhbmQgZWxpZ2liaWxpdHkgc3RpbGwgZmlsdGVycyBiZWZvcmUgZG9tYWluIHJhbmtpbmcKKyAgICAgICAgICAgICAgICAjIGFuZCBtb2RlbC12aXNpYmxlIHByb2plY3Rpb247IGtlZXBpbmcgdGhlIHJhdyBjYW5kaWRhdGUgaXMKKyAgICAgICAgICAgICAgICAjIHJlcXVpcmVkIGZvciBkaWFnbm9zdGljcywgYnVkZ2V0IHNraXBwaW5nIGFuZCBzdGFibGUgYWRhcHRlcgorICAgICAgICAgICAgICAgICMgY29tcGF0aWJpbGl0eS4KKyAgICAgICAgICAgICAgICAqYXV0aG9yaXRhdGl2ZV9jaHVua3MsCisgICAgICAgICAgICAgICAgKmNodW5rcywKICAgICAgICAgICAgIF1dLAogICAgICAgICAgICAgcXVlcmllc19ieV9vcmlnaW4uZ2V0KCJob3N0X2xvb2t1cCIsIFtdKSwKICAgICAgICAgICAgIFsK"
)
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


def apply_patch_bytes(patch: bytes, *, label: str, expected_digest: str) -> int:
    digest = hashlib.sha256(patch).hexdigest()
    if digest != expected_digest:
        print(f"{label} digest mismatch: expected {expected_digest}, got {digest}")
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
            print(f"Applied {label} {digest}.")
            return 0

        reverse = run("git", "apply", "--reverse", "--check", str(patch_path))
        if reverse.returncode == 0:
            print(f"{label} {digest} is already applied.")
            return 0

        print(f"{label} cannot be applied and is not already present.")
        print(output(check))
        print(output(reverse))
        return 3
    finally:
        if patch_path is not None:
            patch_path.unlink(missing_ok=True)


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in PARTS if not path.is_file()]
    if missing:
        print("Missing reviewed patch parts:", ", ".join(missing))
        return 2

    encoded = "".join(path.read_text(encoding="ascii") for path in PARTS)
    try:
        patch = gzip.decompress(base64.b64decode(encoded, validate=True))
        repair_patch = base64.b64decode(REPAIR_PATCH_B64, validate=True)
    except Exception as exc:
        print(f"Cannot decode reviewed patch: {exc}")
        return 2

    result = apply_patch_bytes(
        patch,
        label="reviewed DDD patch",
        expected_digest=PATCH_SHA256,
    )
    if result:
        return result
    result = apply_patch_bytes(
        repair_patch,
        label="full-suite regression repair",
        expected_digest=REPAIR_PATCH_SHA256,
    )
    if result:
        return result

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
