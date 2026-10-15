"""Unchanged real frozen flow regression."""
from experiments.language_aware_context.flow_experiment import flow_experiment


def test_real_frozen_flow_all_witnesses_without_changing_expected_labels():
    from tests.docs.test_context_projection_boundaries import (
        test_frozen_request_flow_prefers_project_context_module_witnesses,
    )
    # Same existing integration assertion, no weakened rubric or replacement payload.
    with flow_experiment():
        test_frozen_request_flow_prefers_project_context_module_witnesses()
