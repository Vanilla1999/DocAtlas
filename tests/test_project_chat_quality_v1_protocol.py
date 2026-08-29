from eval.project_chat_quality_v1_protocol import run


def test_project_chat_quality_v1_novel_adversarial_gate_passes():
    report = run()

    assert report["verdict"] == "PASS"
    assert report["passed_count"] == report["case_count"] == 40
    assert report["false_supported_count"] == 0
    assert set(report["class_failures"].values()) == {0}
    assert report["contamination_overlap_case_ids"] == []
