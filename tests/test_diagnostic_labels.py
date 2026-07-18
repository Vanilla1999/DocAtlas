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


def test_diagnostic_manifest_assigns_module_and_exact_override_labels():
    manifest = _manifest()

    assert diagnostic_label_for("tests/test_example.py::test_behavior", manifest) == "behavioral"
    assert diagnostic_label_for("tests/test_example.py::test_shape[param]", manifest) == "schema"


def test_diagnostic_manifest_fails_closed_for_unknown_module():
    with pytest.raises(pytest.UsageError, match="diagnostic_unclassified"):
        diagnostic_label_for("tests/test_new.py::test_new", _manifest())


def test_diagnostic_label_application_rejects_multiple_explicit_labels():
    item = _Item("tests/test_example.py::test_behavior", ("behavioral", "artifact"))

    with pytest.raises(pytest.UsageError, match="multiple diagnostic labels"):
        apply_diagnostic_label(item, _manifest())


def test_diagnostic_label_application_adds_exactly_one_label():
    item = _Item("tests/test_example.py::test_behavior")

    apply_diagnostic_label(item, _manifest())

    assert item._markers & DIAGNOSTIC_LABELS == {"behavioral"}


def test_diagnostic_inventory_rejects_new_test_in_known_module():
    known = "tests/test_example.py::test_behavior"
    known_shape = "tests/test_example.py::test_shape"
    manifest = _manifest()
    manifest["module_node_hashes"] = {
        "tests/test_example.py": hashlib.sha256(
            "\n".join(sorted((known, known_shape))).encode()
        ).hexdigest(),
    }

    with pytest.raises(pytest.UsageError, match="diagnostic_unclassified or stale tests"):
        validate_diagnostic_inventory(
            [_Item(known), _Item(known_shape), _Item("tests/test_example.py::test_new")],
            manifest,
            {"tests/test_example.py"},
        )


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
