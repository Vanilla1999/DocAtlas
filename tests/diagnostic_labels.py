from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

DIAGNOSTIC_LABELS = frozenset({
    "behavioral",
    "schema",
    "artifact",
    "serialization",
    "compatibility",
})


def load_diagnostic_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    module_labels = manifest.get("module_labels")
    node_overrides = manifest.get("node_overrides")
    node_hashes = manifest.get("module_node_hashes")
    if not all(isinstance(value, dict) for value in (module_labels, node_overrides, node_hashes)):
        raise pytest.UsageError("diagnostic label manifest must contain object maps")
    invalid = {
        str(label)
        for label in [*module_labels.values(), *node_overrides.values()]
        if label not in DIAGNOSTIC_LABELS
    }
    if invalid:
        raise pytest.UsageError(f"invalid diagnostic labels: {sorted(invalid)}")
    return manifest


def validate_diagnostic_inventory(
    items: list[Any],
    manifest: dict[str, Any],
    complete_modules: set[str],
) -> None:
    by_module: dict[str, set[str]] = {}
    for item in items:
        base_nodeid = item.nodeid.split("[", 1)[0]
        module = base_nodeid.split("::", 1)[0]
        by_module.setdefault(module, set()).add(base_nodeid)

    known_modules = set(manifest["module_labels"])
    unknown_modules = sorted(set(by_module) - known_modules)
    missing_complete_modules = sorted(complete_modules - set(by_module))
    if unknown_modules or missing_complete_modules:
        raise pytest.UsageError(
            f"diagnostic_unclassified modules={unknown_modules}; "
            f"stale modules={missing_complete_modules}"
        )
    collected_complete_nodes = {
        nodeid
        for module in complete_modules
        for nodeid in by_module.get(module, set())
    }
    stale_overrides = sorted(
        nodeid
        for nodeid in manifest["node_overrides"]
        if nodeid.split("::", 1)[0] in complete_modules
        and nodeid not in collected_complete_nodes
    )
    if stale_overrides:
        raise pytest.UsageError(f"stale diagnostic node overrides: {stale_overrides}")

    for module in complete_modules:
        nodeids = by_module[module]
        digest = hashlib.sha256("\n".join(sorted(nodeids)).encode()).hexdigest()
        if manifest["module_node_hashes"].get(module) != digest:
            raise pytest.UsageError(
                f"diagnostic_unclassified or stale tests in {module}; "
                "refresh and review the diagnostic manifest"
            )


def diagnostic_label_for(nodeid: str, manifest: dict[str, Any]) -> str:
    base_nodeid = nodeid.split("[", 1)[0]
    module = base_nodeid.split("::", 1)[0]
    label = manifest["node_overrides"].get(base_nodeid)
    if label is None:
        label = manifest["module_labels"].get(module)
    if label is None:
        raise pytest.UsageError(f"diagnostic_unclassified: {nodeid}")
    return str(label)


def apply_diagnostic_label(item: Any, manifest: dict[str, Any]) -> None:
    expected = diagnostic_label_for(item.nodeid, manifest)
    explicit = {
        label for label in DIAGNOSTIC_LABELS if item.get_closest_marker(label) is not None
    }
    if len(explicit) > 1:
        raise pytest.UsageError(
            f"multiple diagnostic labels for {item.nodeid}: {sorted(explicit)}"
        )
    if explicit and explicit != {expected}:
        raise pytest.UsageError(
            f"diagnostic label mismatch for {item.nodeid}: "
            f"manifest={expected}, explicit={sorted(explicit)}"
        )
    if not explicit:
        item.add_marker(getattr(pytest.mark, expected))
