from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import jsonschema


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kotlin_live_smoke.py"
ROOT = SCRIPT.parents[1]
SPEC = importlib.util.spec_from_file_location("kotlin_live_smoke", SCRIPT)
assert SPEC and SPEC.loader
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)



















