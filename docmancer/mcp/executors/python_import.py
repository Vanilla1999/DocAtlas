"""Section 29: python_import executor (opt-in via allow_execute).

Runs the requested Python callable in a subprocess that uses the user's
detected venv. The dispatcher only routes here when the installed package
has `allow_execute=True`. By default SDK-style packages stay on `noop_doc`.

Operation contract for this executor:
    operation["python_import"] = {
        "module": "httpx",
        "callable": "get",               # dot-path resolved at runtime
        "via_kwargs": True,              # if True, args dict expands to kwargs; else first positional arg
    }
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from docmancer.mcp.executors.base import Executor, ExecutorResult

DEFAULT_TIMEOUT_SECONDS = 30


def detect_python(start: Path | None = None, *, use_project_venv: bool = False) -> str:
    """Resolve the Python runtime.

    Project venv discovery is opt-in because executing pack code inside the
    caller project's environment expands the trust boundary to that project.
    """
    here = (start or Path.cwd()).resolve()
    if use_project_venv:
        for parent in [here, *here.parents]:
            for candidate in (".venv", "venv"):
                python = parent / candidate / "bin" / "python"
                if python.exists():
                    return str(python)
    return shutil.which("python") or shutil.which("python3") or sys.executable


def validate_python_import(meta: dict[str, Any], grant: dict[str, Any]) -> str | None:
    module = meta.get("module")
    callable_name = meta.get("callable")
    if not module or not callable_name:
        return "missing_python_import_target"
    if not module_matches(str(module), tuple(grant.get("allowed_modules") or ())):
        return "module_not_allowed"
    if "__" in str(callable_name):
        return "dunder_callable_blocked"
    return None


def module_matches(module: str, allowed_modules: tuple[str, ...]) -> bool:
    for allowed in allowed_modules:
        allowed = str(allowed).strip()
        if not allowed:
            continue
        if module == allowed or module.startswith(allowed + "."):
            return True
    return False


def safe_path() -> str:
    return os.pathsep.join(part for part in ("/usr/local/bin", "/usr/bin", "/bin") if Path(part).exists())


def minimal_env(grant: dict[str, Any]) -> dict[str, str]:
    env = {
        "PATH": safe_path(),
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    for name in grant.get("allowed_env") or ():
        if name in os.environ:
            env[str(name)] = os.environ[str(name)]
    return env


_RUNNER = """
import importlib, json, sys, traceback
data = json.loads(sys.stdin.read())
try:
    module = importlib.import_module(data["module"])
    target = module
    for part in data["callable"].split("."):
        target = getattr(target, part)
    if data.get("via_kwargs", True):
        result = target(**data.get("args", {}))
    else:
        result = target(data.get("args", {}))
    try:
        out = json.dumps({"ok": True, "result": result}, default=str)
    except Exception:
        out = json.dumps({"ok": True, "result": repr(result)})
    sys.stdout.write(out)
except SystemExit:
    raise
except BaseException as exc:
    sys.stdout.write(json.dumps({
        "ok": False,
        "error": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }))
"""


class PythonImportExecutor(Executor):
    def __init__(self, *, python: str | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self._python = python
        self._timeout = timeout

    def call(
        self,
        *,
        operation: dict[str, Any],
        args: dict[str, Any],
        auth_headers: dict[str, str],
        required_headers: dict[str, str],
        idempotency_key: str | None,
        idempotency_header: str | None,
        auth_params: dict[str, str] | None = None,
        auth_cookies: dict[str, str] | None = None,
    ) -> ExecutorResult:
        meta = operation.get("python_import") or {}
        grant = operation.get("_docmancer_operation_grant") or {}
        validation_error = validate_python_import(meta, grant)
        if validation_error:
            return ExecutorResult(False, validation_error, None, error=validation_error)
        python = self._python or detect_python(use_project_venv=bool(grant.get("use_project_venv")))
        payload = json.dumps({
            "module": meta["module"],
            "callable": meta["callable"],
            "via_kwargs": meta.get("via_kwargs", True),
            "args": {k: v for k, v in args.items() if not k.startswith("_docmancer")},
        })
        env = minimal_env(grant)
        try:
            proc = subprocess.run(
                [python, "-c", _RUNNER],
                input=payload, capture_output=True, text=True,
                env=env, timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            return ExecutorResult(False, "timeout", None,
                                  error=f"python subprocess exceeded {self._timeout}s")
        if proc.returncode != 0:
            return ExecutorResult(
                False, proc.returncode, None,
                error=f"python subprocess failed: {proc.stderr.strip() or proc.stdout.strip()}",
            )
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            return ExecutorResult(False, "decode_error", proc.stdout, error=str(exc))
        if not result.get("ok"):
            return ExecutorResult(
                False, "execution_error", result,
                error=result.get("message") or "python execution failed",
            )
        return ExecutorResult(True, 0, result.get("result"))
