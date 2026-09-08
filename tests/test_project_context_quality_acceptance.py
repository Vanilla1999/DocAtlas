from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from scripts.check_legacy_project_context_lineage import verify_legacy_lineage_floor
from scripts.run_project_context_quality_v2_gate import load_acceptance_lock, verify_v2_acceptance


def _v2_report():
    lock = load_acceptance_lock()
    lanes = {}
    for lane, thresholds in lock["lanes"].items():
        metrics = {}
        for metric, threshold in thresholds.items():
            numerator = threshold.get("minimum", threshold.get("maximum", 0))
            metrics[metric] = {"numerator": numerator, "denominator": threshold["denominator"]}
        lanes[lane] = {"metrics": metrics}
    return {
        "schema_version": "project-context-quality-v2-result-2",
        "run_mode": "live_self_host",
        "validation": {"case_count": 25},
        "lanes": lanes,
    }


def test_v2_acceptance_requires_full_semantic_safety_budget_and_zero_false_full():
    report = _v2_report()
    assert verify_v2_acceptance(report) == []
    for lane, metric in (
        ("natural", "semantic_usefulness"),
        ("exposed_paraphrases", "semantic_usefulness"),
        ("natural", "safety"),
        ("exposed_paraphrases", "budget_compliance"),
    ):
        broken = deepcopy(report)
        broken["lanes"][lane]["metrics"][metric]["numerator"] -= 1
        assert verify_v2_acceptance(broken)
    broken = deepcopy(report)
    broken["lanes"]["natural"]["metrics"]["false_full_coverage"]["numerator"] = 1
    assert verify_v2_acceptance(broken)


def test_v2_acceptance_keeps_lookup_attribution_as_a_non_regression_floor():
    report = _v2_report()
    broken = deepcopy(report)
    broken["lanes"]["natural"]["metrics"]["lookup_attribution"]["numerator"] = 32
    assert verify_v2_acceptance(broken)


def test_v2_acceptance_rejects_inventory_denominator_changes():
    report = _v2_report()
    report["lanes"]["natural"]["metrics"]["semantic_usefulness"]["denominator"] = 14
    assert verify_v2_acceptance(report)


def test_legacy_compatibility_floor_keeps_original_threshold_and_hard_safety():
    lock = load_acceptance_lock()
    floor = lock["legacy_lineage_floor"]
    metrics = {name: 0 for name in floor["hard_zero_metrics"]}
    metrics["original_query_covered_count"] = floor["original_query_coverage_min"]
    report = {"lane": "legacy", "input_mode": "question_with_lookups", "metrics": metrics}
    assert verify_legacy_lineage_floor(report) == []
    broken = deepcopy(report)
    broken["metrics"]["original_query_covered_count"] -= 1
    assert verify_legacy_lineage_floor(broken)
    broken = deepcopy(report)
    broken["metrics"][floor["hard_zero_metrics"][0]] = 1
    assert verify_legacy_lineage_floor(broken)


def test_acceptance_clis_run_without_repo_pythonpath(tmp_path):
    root = Path(__file__).parents[1]
    for script in (
        root / "scripts/run_project_context_quality_v2_gate.py",
        root / "scripts/check_legacy_project_context_lineage.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=tmp_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env={"PATH": str(Path(sys.executable).parent)},
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
