"""Deterministic, provider-free minimal evidence selection.

The selector owns evidence eligibility and fitting. Formatters receive only a
validated whole-item subset and remain responsible for serialization safety,
not for deciding which source facts are important.
"""

from __future__ import annotations

from dataclasses import replace as _replace
from functools import wraps as _wraps
from typing import Any as _Any, Iterable as _Iterable, Mapping as _Mapping, Sequence as _Sequence

from ._evidence_selection_shared import *  # noqa: F401,F403
from ._evidence_selection_shared import build_requirements as _build_requirements_impl

from ._evidence_selection_part01 import *  # noqa: F401,F403

from ._evidence_selection_part02 import *  # noqa: F401,F403

from ._evidence_selection_part03 import *  # noqa: F401,F403
from ._evidence_selection_part03 import select_evidence as _select_evidence_impl

from ._evidence_selection_part04 import *  # noqa: F401,F403

from .proofability import *  # noqa: F401,F403


_GOVERNANCE_PROJECT_RULE_RELATIONS = frozenset({
    "governed_scope",
    "governance_facet",
    "governance_ownership",
    "governance_requirement",
    "governance_state",
    "governance_version",
})


def _bind_governance_project_rule_roles(
    requirements: EvidenceRequirementSet | _Sequence[EvidenceRequirement],
) -> EvidenceRequirementSet | tuple[EvidenceRequirement, ...]:
    """Bind governance obligations to project-rule authority in the canonical facade."""

    def bind(item: EvidenceRequirement) -> EvidenceRequirement:
        if (
            item.kind == "proof_obligation"
            and item.relation in _GOVERNANCE_PROJECT_RULE_RELATIONS
            and item.proof_role != "project_rule"
        ):
            return _replace(item, proof_role="project_rule")
        return item

    if isinstance(requirements, EvidenceRequirementSet):
        rebound = tuple(bind(item) for item in requirements.requirements)
        if rebound == requirements.requirements:
            return requirements
        return _replace(requirements, requirements=rebound)
    return tuple(bind(item) for item in requirements)


@_wraps(_build_requirements_impl)
def build_requirements(*args: _Any, **kwargs: _Any) -> EvidenceRequirementSet:
    """Build canonical requirements and attach governance authority semantics."""

    requirements = _build_requirements_impl(*args, **kwargs)
    bound = _bind_governance_project_rule_roles(requirements)
    if not isinstance(bound, EvidenceRequirementSet):
        raise RuntimeError("canonical requirement binding returned an invalid requirement set")
    return bound


def select_evidence(
    items: _Iterable[_Mapping[str, _Any]],
    *,
    question: str,
    config: SelectionConfig,
    trust_contract: _Mapping[str, _Any] | None = None,
    requirements: EvidenceRequirementSet | _Sequence[EvidenceRequirement] | None = None,
    required_evidence_paths: _Iterable[str] = (),
    required_target_paths: _Iterable[str] = (),
    public_requirements: _Iterable[_Mapping[str, _Any] | str] = (),
    library_requirement_contract: _Mapping[str, _Iterable[str]] | None = None,
    exact_version: str | None = None,
    project_identity: str | None = None,
    module_id: str | None = None,
) -> SelectionDecision:
    """Select evidence after binding governance obligations to project-rule authority."""

    canonical_requirements = (
        _bind_governance_project_rule_roles(requirements)
        if requirements is not None
        else build_requirements(
            question,
            required_evidence_paths=required_evidence_paths,
            required_target_paths=required_target_paths,
            public_requirements=public_requirements,
            library_requirement_contract=library_requirement_contract,
            exact_version=exact_version,
            project_identity=project_identity,
            module_id=module_id,
            profile=config.profile,
        )
    )
    return _select_evidence_impl(
        items,
        question=question,
        config=config,
        trust_contract=trust_contract,
        requirements=canonical_requirements,
        exact_version=exact_version,
        project_identity=project_identity,
        module_id=module_id,
    )


_FACADE_PRIVATE_NAMES = {
    "_replace", "_wraps", "_Any", "_Iterable", "_Mapping", "_Sequence",
    "_build_requirements_impl", "_select_evidence_impl",
    "_GOVERNANCE_PROJECT_RULE_RELATIONS", "_bind_governance_project_rule_roles",
}
__all__ = [
    n for n in globals()
    if not n.startswith("__") and n not in _FACADE_PRIVATE_NAMES
]
