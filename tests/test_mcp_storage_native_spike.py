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


def test_header_hashes_and_exact_three_line_normalization():
    for name, digest in MODULE.HEADER_HASHES.items():
        assert hashlib.sha256((SPIKE / "include" / name).read_bytes()).hexdigest() == digest
    normalized = (SPIKE / "include" / "sqlite3ext.h").read_bytes()
    lines = normalized.splitlines(keepends=True)
    for number in (15, 709, 716):
        assert lines[number - 1].endswith(b"\n")
        assert not lines[number - 1].endswith(b" \n")
        lines[number - 1] = lines[number - 1][:-1] + b" \n"
    assert hashlib.sha256(b"".join(lines)).hexdigest() == "9a91de0d5e5ccc04ec59041275c67972d6f8894f7543a10033e387b69987beb5"


@pytest.mark.parametrize("facet", ["hook", "compile", "version", "source"])
def test_unsupported_profiles_deny_without_storage_or_native_loading(facet):
    profile = MODULE.EXPECTED_PROFILE
    identity = ("3.50.4", MODULE.EXPECTED_SOURCE_ID)
    options = list(MODULE.EXPECTED_COMPILE_OPTIONS)
    if facet == "hook":
        profile += ",unreviewed"
    elif facet == "compile":
        options[1] = "COMPILER=unreviewed"
    elif facet == "version":
        identity = ("unreviewed", identity[1])
    else:
        identity = (identity[0], "unreviewed")
    with pytest.raises(PermissionError, match="unsupported"):
        MODULE.validate_profile(profile, identity, options)


@pytest.mark.parametrize("payload", [
    [], {}, {"operation": "arbitrary_sql"}, {"operation": "profile", "sql": "SELECT 1"},
    {"operation": "upsert"},
    {"operation": "upsert", "expected_generation": 1, "new_generation": "g", "content": "x"},
    {"operation": "upsert", "expected_generation": "g", "new_generation": "h", "content": "x", "pause": "unreviewed"},
])
def test_invalid_finite_requests_deny_before_runtime_admission(payload):
    with pytest.raises(ValueError):
        MODULE.validate_request(json.dumps(payload))


def test_oversize_request_denied_before_json_or_runtime_admission():
    with pytest.raises(ValueError, match="too large"):
        MODULE.validate_request("x" * (MODULE.MAX_REQUEST + 1))


def test_valid_finite_request_parsing_does_not_imply_runtime_support():
    request = {"operation": "upsert", "expected_generation": "g", "new_generation": "h", "content": "x"}
    assert MODULE.validate_request(json.dumps(request)) == request
    assert MODULE.validate_request('{"operation":"profile"}') == {"operation": "profile"}


def test_unsupported_platform_denies_before_extension_or_storage_access(monkeypatch):
    monkeypatch.setattr(MODULE, "sys", SimpleNamespace(platform="unreviewed"))
    result = MODULE.run(SimpleNamespace(), {"operation": "profile"})
    assert result["status"] == "error" and result["error"] == "unsupported spike platform"
    assert result["commit_outcome"] == "no_member_write_attempt"


def test_standalone_research_is_compatible_with_default_directory_inventory(pytestconfig, tmp_path):
    from tests.diagnostic_labels import load_diagnostic_manifest, validate_diagnostic_inventory

    portable = "tests/test_mcp_storage_native_spike.py"
    research = "tests/mcp_storage_native_spike_checks.py"
    patterns = pytestconfig.getini("python_files")
    assert not any(fnmatch.fnmatch(Path(research).name, pattern) for pattern in patterns)
    manifest = json.loads((ROOT / "tests/diagnostic_labels.mcp_storage_native_spike.json").read_text())
    complete_manifest = load_diagnostic_manifest(ROOT / "tests/diagnostic_labels.json")
    assert research not in complete_manifest["module_labels"]
    assert research not in complete_manifest["module_node_hashes"]
    runner_tree = ast.parse((ROOT / research).read_text())
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                   node.name.startswith("test_") for node in ast.walk(runner_tree))
    assert not any((isinstance(node, ast.Import) and any(alias.name == "pytest" for alias in node.names)) or
                   (isinstance(node, ast.ImportFrom) and node.module == "pytest")
                   for node in ast.walk(runner_tree))
    functions = [node.name for node in ast.parse((ROOT / portable).read_text()).body
                 if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    portable_items = [SimpleNamespace(nodeid=portable + "::" + name) for name in functions]
    # Match conftest's directory-selection complete_modules computation for this
    # shard. The standalone runner is not pytest inventory; no bypass is needed.
    complete_modules = {module for module in manifest["module_labels"]
                        if (ROOT / module).resolve().is_relative_to(ROOT / "tests")}
    assert complete_modules == {portable}
    validate_diagnostic_inventory(portable_items, manifest, complete_modules)
    (tmp_path / "directory-gate-observation.json").write_text(json.dumps({
        "python_files": patterns, "research_file_default_discovered": False,
        "directory_inventory": "compatible", "runner_is_pytest_inventory": False,
        "ci_green_claim": False,
    }, indent=2))
