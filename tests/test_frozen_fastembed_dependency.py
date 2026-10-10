"""Installation must retain the reviewed multilingual evaluator dependency."""
import json
from pathlib import Path
import tomllib

from packaging.requirements import Requirement


ROOT = Path(__file__).resolve().parents[1]


def test_install_dependency_matches_frozen_fastembed_version():
    protocol = json.loads(
        (ROOT / "eval/multilingual_retrieval_quality/protocol_v3.lock.json").read_text()
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    dependency = next(
        Requirement(value)
        for value in project["project"]["dependencies"]
        if Requirement(value).name == "fastembed"
    )
    expected = protocol["model_configuration"]["fastembed_version"]
    assert str(dependency.specifier) == f"=={expected}"


def test_uv_dependency_matches_install_dependency():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    expected = next(
        str(Requirement(value).specifier)
        for value in project["project"]["dependencies"]
        if Requirement(value).name == "fastembed"
    )
    package = next(item for item in lock["package"] if item["name"] == "doc-atlas")
    declared = next(
        item for item in package["metadata"]["requires-dist"]
        if item["name"] == "fastembed"
    )
    assert declared["specifier"] == expected
