from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.diagnostic_labels import (
    DIAGNOSTIC_LABELS,
    apply_diagnostic_label,
    diagnostic_label_for,
    validate_diagnostic_inventory,
)


class _Item:
    def __init__(self, nodeid: str, explicit: tuple[str, ...] = ()):
        self.nodeid = nodeid
        self._markers = set(explicit)

    def get_closest_marker(self, name: str):
        return SimpleNamespace(name=name) if name in self._markers else None

    def add_marker(self, marker):
        self._markers.add(marker.name)


def _manifest():
    return {
        "module_labels": {"tests/test_example.py": "behavioral"},
        "node_overrides": {
            "tests/test_example.py::test_shape": "schema",
        },
    }












def test_single_node_pytest_selection_passes_inventory_hook():
    root = Path(__file__).parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/task_level/test_actionability.py::test_active_task33_protocol_has_public_actionability_contract",
            "-q",
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
