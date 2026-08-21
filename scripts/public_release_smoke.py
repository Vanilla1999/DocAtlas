#!/usr/bin/env python3
"""Verify one exact public DocAtlas release from PyPI on the current OS."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPI_INDEX = "https://pypi.org/simple"


def source_version() -> str:
    text = (ROOT / "docmancer" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)', text)
    if not match:
        raise SystemExit("public release smoke: source version not found")
    return match.group(1)


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def install_public(version: str, *, cwd: Path, env: dict[str, str]) -> None:
    command = [
        sys.executable,
        "-m",
        "pip",
        "--isolated",
        "install",
        "--no-cache-dir",
        "--force-reinstall",
        "--index-url",
        PYPI_INDEX,
        f"doc-atlas=={version}",
    ]
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, 6):
        try:
            result = run(command, cwd=cwd, env=env)
            print(result.stdout, end="")
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            print(exc.stdout or "", end="")
            if attempt == 5:
                raise
            time.sleep(attempt * 15)
    raise SystemExit(f"public release smoke: install failed: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()

    tag = str(args.tag).strip()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise SystemExit(f"public release smoke: expected immutable vMAJOR.MINOR.PATCH tag, got {tag!r}")
    version = tag.removeprefix("v")
    if source_version() != version:
        raise SystemExit(
            f"public release smoke: checkout source version {source_version()} does not match tag {tag}"
        )

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PIP_NO_CACHE_DIR"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    with tempfile.TemporaryDirectory(prefix="docatlas-public-release-") as raw:
        cwd = Path(raw)
        install_public(version, cwd=cwd, env=env)

        version_result = run(["doc-atlas", "--version"], cwd=cwd, env=env)
        print(version_result.stdout, end="")
        actual = version_result.stdout.strip()
        expected = f"doc-atlas {version}"
        if actual != expected:
            raise SystemExit(
                f"public release smoke: installed CLI version mismatch: expected {expected!r}, got {actual!r}"
            )

        smoke = run(
            [sys.executable, str(ROOT / "scripts" / "docs_mcp_stdio_smoke.py")],
            cwd=cwd,
            env=env,
        )
        print(smoke.stdout, end="")

    print(f"Exact public DocAtlas {version} smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
