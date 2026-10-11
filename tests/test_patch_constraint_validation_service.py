from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from docmancer.docs.application.patch_constraint_validation_service import PatchConstraintValidationService
from docmancer.docs.models import PatchConstraint, PatchConstraintPacket


def _constraint(
    constraint_id: str,
    type_: str,
    instruction: str,
    *,
    source: str = "docs/architecture.md",
    severity: str = "must",
    confidence: str = "high",
    evidence: str | None = None,
    files: list[str] | None = None,
    symbols: list[str] | None = None,
) -> PatchConstraint:
    return PatchConstraint(
        id=constraint_id,
        type=type_,
        instruction=instruction,
        source=source,
        severity=severity,
        confidence=confidence,
        evidence=evidence or instruction,
        files=files or [],
        symbols=symbols or [],
    )


def _service() -> PatchConstraintValidationService:
    return PatchConstraintValidationService()



























