from __future__ import annotations

import importlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApiCheckResult:
    symbol: str
    exists: bool
    detail: str = ""


def check_python_symbols(symbols: list[str]) -> list[ApiCheckResult]:
    results: list[ApiCheckResult] = []
    for symbol in symbols:
        module_name, _, attr_path = symbol.partition(":")
        try:
            obj = importlib.import_module(module_name)
            for attr in filter(None, attr_path.split(".")):
                obj = getattr(obj, attr)
            results.append(ApiCheckResult(symbol=symbol, exists=True))
        except Exception as exc:  # pragma: no cover - detail is diagnostic
            results.append(ApiCheckResult(symbol=symbol, exists=False, detail=repr(exc)))
    return results


def run_static_check(command: str, cwd: Path) -> bool:
    return subprocess.run(command, cwd=cwd, shell=True, check=False).returncode == 0
