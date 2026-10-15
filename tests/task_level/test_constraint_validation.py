from __future__ import annotations

from eval.task_level.context.patch_constraints import PatchConstraint, PatchConstraintPacket
from eval.task_level.evaluators.constraint_validation import validate_patch_against_constraints


def _packet(constraint: PatchConstraint) -> PatchConstraintPacket:
    return PatchConstraintPacket(
        task_id="t",
        constraints=[constraint],
        suggested_checks=[],
        warnings=[],
        source_summary=[],
        token_estimate=10,
    )









