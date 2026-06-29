from __future__ import annotations

import configparser
from pathlib import Path


def _pytest_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(Path(__file__).resolve().parents[1] / "pytest.ini")
    return config


def test_normal_pytest_collection_is_limited_to_tests_tree() -> None:
    config = _pytest_config()
    assert config.get("pytest", "testpaths").strip() == "tests"


def test_benchmark_runtime_dirs_are_excluded_from_normal_pytest_collection() -> None:
    config = _pytest_config()
    norecursedirs = set(config.get("pytest", "norecursedirs").split())

    required = {
        ".cache",
        ".pytest_cache",
        ".uv",
        "archive-v0",
        "eval/task_level/fixtures",
        "eval/task_level/hidden_tests",
        "eval/task_level/oracles",
        "eval/task_level/results",
        "eval/task_level/runtime",
        "eval/task_level/workspaces",
        "materialized",
        "results",
        "runtime",
        "uv-cache",
        "workspaces",
    }
    assert required <= norecursedirs
