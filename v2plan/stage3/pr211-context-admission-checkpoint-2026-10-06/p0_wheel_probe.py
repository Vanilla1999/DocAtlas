"""Import real wheel with repository/editable paths excluded, preserving dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    root = Path.cwd().resolve()
    modules = ("docmancer.core.config", "docmancer.docs.domain.documentation_query_plan",
               "docmancer.docs.application.project_docs_service",
               "docmancer.docs.application.patch_review_service", "docmancer.mcp.docs_server")
    outcomes = []
    for module in modules:
        code = f"""
import sys, importlib, importlib.util, json
from pathlib import Path
root = Path({str(root)!r})
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != root]
sys.path.insert(0, {str(wheel)!r})
spec = importlib.util.find_spec('docmancer')
assert {str(wheel)!r} in spec.origin, spec.origin
assert importlib.util.find_spec('eval') is None, 'repository eval leakage'
print(json.dumps({{'package_origin': spec.origin, 'eval_available': False}}))
importlib.import_module({module!r})
print('IMPORT_OK')
"""
        run = subprocess.run([sys.executable, "-I", "-c", code], cwd="/tmp/opencode",
                             capture_output=True, text=True)
        outcomes.append({"module": module, "returncode": run.returncode,
                         "stdout": run.stdout, "stderr": run.stderr})
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
    print(json.dumps({"schema": "p0-clean-wheel-probe-v1", "wheel": str(wheel),
                      "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                      "wheel_members": members, "imports": outcomes,
                      "limitations": "Wheel import with existing venv dependencies; not a new dependency installation or full release test."},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
