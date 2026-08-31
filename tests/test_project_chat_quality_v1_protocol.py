from eval.project_chat_quality_v1_protocol import load_onboarding_cases, run, run_onboarding


def test_project_chat_quality_v1_novel_adversarial_gate_passes():
    report = run()

    assert report["verdict"] == "PASS"
    assert report["passed_count"] == report["case_count"] == 40
    assert report["false_supported_count"] == 0
    assert set(report["class_failures"].values()) == {0}
    assert report["contamination_overlap_case_ids"] == []


def test_project_chat_onboarding_production_corpus_is_frozen():
    cases = load_onboarding_cases()

    assert len(cases) == 20
    assert {case["expected_kind"] for case in cases} == {
        "docs_answer", "docs_context", "insufficient_evidence",
    }
    assert {case["class"] for case in cases} >= {
        "onboarding", "operational_workflow", "architecture_storage",
        "tests_contribution", "wrong_relation", "nonexistent",
    }


def test_project_chat_onboarding_production_path_passes():
    report = run_onboarding()

    assert report["verdict"] == "PASS", report["errors"]
    assert report["metrics"]["false_supported_count"] == 0
    assert report["metrics"]["operational_contamination_count"] == 0
