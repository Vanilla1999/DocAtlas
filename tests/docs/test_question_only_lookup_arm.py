from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARM = ROOT / "eval/global_evidence_tdd/question_only_lookup_arm.json"


def _question_registry() -> dict[tuple[str, str], str]:
    external = json.loads((ROOT / "eval/evidence_quality_v2/cases.json").read_text())["cases"]
    generic = json.loads((ROOT / "eval/project_context_quality/generic_blind_lookup_pair30_questions.json").read_text())["cases"]
    target = json.loads((ROOT / "eval/project_context_quality/v13_v15_questions.json").read_text())["cases"]
    return {
        **{("external80", row["id"]): row["question"] for row in external},
        **{("generic30", row["id"]): row["question"] for row in generic},
        **{("target30", row["id"]): row["question"] for row in target},
    }


def test_question_only_lookup_arm_is_frozen_and_does_not_leak_answers():
    data = json.loads(ARM.read_text())
    assert data["state"] == "frozen_exposed_development_arm"
    assert data["host_integration_verified"] is False
    registry = _question_registry()
    assert len(data["cases"]) == len({(row["suite"], row["id"]) for row in data["cases"]})

    for row in data["cases"]:
        assert row["question"] == registry[(row["suite"], row["id"])]
        lookups = row["lookup_queries"]
        assert 1 <= len(lookups) <= 3
        assert len(lookups) == len(set(lookups))
        assert all(isinstance(value, str) and 1 <= len(value) <= 500 for value in lookups)
        rendered = "\n".join(lookups).casefold()
        for forbidden in row.get("forbidden_answer_terms", []):
            assert forbidden.casefold() not in rendered


def test_lookup_arm_keeps_root_question_separate_from_lookup_queries():
    data = json.loads(ARM.read_text())
    for row in data["cases"]:
        assert row["question"] not in row["lookup_queries"]
        assert all(value.strip() != row["question"].strip() for value in row["lookup_queries"])
