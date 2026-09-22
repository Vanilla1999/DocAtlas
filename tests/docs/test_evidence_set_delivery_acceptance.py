"""Native RED targets for R1-R4; no translated queries or selected gold candidates."""
import pytest

from tests.docs._delivery_acceptance_helpers import assert_delivery, assert_wire_constraints
from tests.docs._evidence_set_fixtures import capture_case, old_assessment
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


@pytest.mark.parametrize('case_id', [
    'mkdocs-05', 'pydantic-03', 'fastapi-06', 'httpx-03', 'uv-04',
])
def test_missing_requested_fact_reaches_final_dto(tmp_path, case_id):
    assert_delivery(capture_case(tmp_path, case_id), case_id)


@pytest.mark.parametrize('case_id', ['pydantic-07', 'ruff-07'])
def test_existing_partial_gain_is_preserved(tmp_path, case_id):
    cap = capture_case(tmp_path, case_id)
    assert_wire_constraints(cap)
    assert old_assessment(case_id, cap)['claims']['required']['status'] == 'supported'
    assert cap['public_payload']['query_coverage'] != 'full'


def test_missing_explicit_class_does_not_leak_other_class_context(tmp_path):
    cap = capture_reference_case(tmp_path, {
        'Guide.md': '# OtherClass\n\nOtherClass retry scheduling uses a bounded queue.\n',
    }, 'Explain retry scheduling behavior of class MissingClass.')
    assert_wire_constraints(cap)
    assert 'OtherClass retry scheduling' not in visible(cap)
