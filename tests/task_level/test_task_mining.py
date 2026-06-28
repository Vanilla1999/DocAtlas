from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.task_mining.historical import render_markdown_report, sanitized_report_rows


REPORT_JSON = Path("eval/task_level/results/task_selection/mined_candidates.json")
REPORT_MD = Path("eval/task_level/results/task_selection/mined_candidates.md")


def test_mined_candidates_report_excludes_secrets():
    text = REPORT_JSON.read_text(encoding="utf-8") + "\n" + REPORT_MD.read_text(encoding="utf-8")

    forbidden = ("coderepo.corp", "git@", "https://github.com/", "AKIA", "-----BEGIN")
    assert not any(value in text for value in forbidden)


def test_mined_candidates_report_matches_sanitized_generator():
    committed = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert committed == sanitized_report_rows()
    assert REPORT_MD.read_text(encoding="utf-8") == render_markdown_report()


def test_mined_candidates_include_required_source_types():
    rows = sanitized_report_rows()
    source_types = {row["source_type"] for row in rows}

    assert {"historical_fix", "adr_mismatch", "dependency_trap", "generated_file_trap"} <= source_types


def test_top_mined_candidate_is_ready_to_implement_not_screen():
    rows = sanitized_report_rows()
    recommended = [row for row in rows if row["recommended"]]

    assert [row["task_id"] for row in recommended] == ["real_project_nbo_generated_policy_source_001"]
    assert recommended[0]["selection_recommendation"] == "implement_next"
