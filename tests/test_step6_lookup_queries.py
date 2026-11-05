"""Step-6 lookup study: the blind runner sends host lookups for dev cases only."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "eval" / "blind_project_context" / "run.py"


@pytest.fixture(scope="module")
def runner():
    sys.path.insert(0, str(RUNNER.parent))
    try:
        spec = importlib.util.spec_from_file_location("blind_project_context_run", RUNNER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(RUNNER.parent))
    return module


def test_committed_lookup_variants_name_only_dev_cases(runner):
    dev = {case["id"] for case in runner.load_cases() if case["split"] == "dev"}
    files = sorted((runner.HERE / "lookups").glob("*.json"))
    assert files
    for path in files:
        assert set(runner.load_lookups(path)) <= dev, path.name


def test_lookup_file_rejects_a_holdout_case(runner, tmp_path):
    holdout = next(case["id"] for case in runner.load_cases() if case["split"] == "holdout")
    path = tmp_path / "lookups.json"
    path.write_text('{"cases": {"%s": {"lookup_queries": ["x"]}}}' % holdout, encoding="utf-8")
    with pytest.raises(ValueError, match="not a dev case"):
        runner.load_lookups(path)


def test_lookup_entry_adds_lookups_and_can_drop_the_translation(runner):
    case = {"id": "T01-ru", "question": "q", "search_question": "s"}
    assert runner.with_host_additions(case, None) is case
    assert runner.with_host_additions(case, {"search_question": None, "lookup_queries": ["a"]}) == {
        "id": "T01-ru", "question": "q", "search_question": None, "lookup_queries": ["a"]}
    assert case == {"id": "T01-ru", "question": "q", "search_question": "s"}
