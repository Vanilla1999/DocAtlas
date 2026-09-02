from eval.project_context_quality_protocol import run_contract


def test_project_context_quality_contract_passes():
    report = run_contract()

    assert report["verdict"] == "PASS"
    assert report["passed_count"] == report["case_count"] == 16
