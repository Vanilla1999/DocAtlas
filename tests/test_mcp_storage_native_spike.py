"""Portable spike admission checks: no compiler, artifact, or native loading."""
from __future__ import annotations

import hashlib
import ast
import fnmatch
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPIKE = ROOT / "experiments/mcp_storage_native"
SPEC = importlib.util.spec_from_file_location("portable_storage_spike_worker", SPIKE / "worker.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)













