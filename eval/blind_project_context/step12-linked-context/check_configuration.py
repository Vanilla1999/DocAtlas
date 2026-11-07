"""Three real CLI startup denials; no model or fake selector.

The caller supplies the fresh installed-wheel executable. Results cover host
configuration validation, not successful Qwen startup or answer quality.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time


CASES = (
    ("unknown-mode", {"DOCATLAS_CONTEXT_LINKS": "not-a-mode"},
     "invalid_DOCATLAS_CONTEXT_LINKS"),
    ("minimal-disabled", {"DOCATLAS_CONTEXT_LINKS": "one-hop-v1",
                          "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "0"},
     "one-hop-v1 requires DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT=1"),
    ("incompatible-recipe", {"DOCATLAS_CONTEXT_LINKS": "one-hop-v1",
                             "DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT": "1",
                             "DOCATLAS_MINIMAL_CONTEXT_RECIPE": "qwen3-contextual-addressed-section-closure-v3"},
     "one-hop-v1 requires qwen3-contextual-own-body-evidence-v1"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.executable.is_absolute() or not args.executable.is_file():
        raise ValueError("explicit installed executable required")
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for name, flags, message in CASES:
        work = args.output / name
        work.mkdir(mode=0o700)
        environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR") if key in os.environ}
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "DOCATLAS_HOME"):
            directory = work / key.lower()
            directory.mkdir(mode=0o700)
            environment[key] = str(directory.resolve())
        environment.update(PYTHONNOUSERSITE="1", DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0",
                           DOCATLAS_REGISTRY_API_URL="http://127.0.0.1:1", **flags)
        started = time.monotonic()
        result = subprocess.run([str(args.executable), "mcp", "docs-serve"],
            env=environment, cwd=work, input="", capture_output=True, text=True, timeout=20)
        record = {"case": name, "flags": flags, "expected_denial": message,
                  "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                  "seconds": time.monotonic() - started,
                  "databases_created": [str(p.relative_to(work)) for p in work.rglob("*.db")]}
        record["status"] = "PASS" if result.returncode != 0 and message in result.stderr else "FAIL"
        records.append(record)
        (args.output / "RESULTS.json").write_text(json.dumps({
            "boundary": "real installed CLI startup; no Qwen inference", "executable": str(args.executable),
            "startup_attempts": len(records), "prepare": 0, "context": 0, "model_calls": 0,
            "cases": records}, ensure_ascii=False, indent=2) + "\n")
        if record["status"] != "PASS":
            raise AssertionError(record)
    print(json.dumps({"status": "PASS", "startup_attempts": 3, "model_calls": 0}))


if __name__ == "__main__":
    main()
