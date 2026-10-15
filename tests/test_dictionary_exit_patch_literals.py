from dataclasses import asdict
from types import SimpleNamespace

import pytest

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.application.patch_constraint_validation_service import PatchConstraintValidationService
from docmancer.docs.application.patch_review_service import PatchReviewService


def _service():
    return PatchConstraintsService(SimpleNamespace(
        read_project_metadata=lambda _: SimpleNamespace(docs_candidates=[], dependencies=[]),
    ))








@pytest.mark.parametrize("budget", [80, 120, 500, 1200])
def test_budget_limited_packet_does_not_authorize_edits(budget, tmp_path):
    packet = _service().get_patch_constraints("close menu", project_path=str(tmp_path), max_tokens=budget, max_constraints=2)
    assert packet.token_estimate <= budget
    assert len(packet.constraints) <= 2
    assert packet.next_actions[0]["type"] == "manual_review_required"
    validation = asdict(PatchConstraintValidationService().validate_patch_against_constraints(packet, changed_files=["src/menu.dart"]))
    coverage = PatchReviewService._constraint_coverage_payload(asdict(packet), validation)
    decision = PatchReviewService._review_summary_advisory_decision_payload({}, {}, coverage)
    assert decision["requires_manual_review"]
    assert decision["mutation_authorized"] is False







