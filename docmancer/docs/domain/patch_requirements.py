"""Typed requirements derived only from an immutable patch request plan."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from docmancer.docs.domain.patch_request_plan import PatchRequestPlan
from docmancer.retrieval.contracts import canonical_hash


PatchRequirementKind = Literal[
    "target_declaration",
    "preserve_declaration",
    "behavioral_contract",
    "cross_module_invariant",
    "preserve_constraint",
    "generated_file_constraint",
    "validation_requirement",
]


@dataclass(frozen=True, slots=True)
class PatchRequirement:
    requirement_id: str
    kind: PatchRequirementKind
    value: str
    mandatory: bool
    provenance: Literal[
        "user_request", "authoritative_project_doc", "source_declaration",
        "explicit_task_contract",
    ]
    proof_role: str
    query_span_start: int | None = None
    query_span_end: int | None = None


def _requirement_id(kind: PatchRequirementKind, value: str, index: int) -> str:
    return f"patch:{kind}:{index}:{canonical_hash(value.casefold())[:12]}"


def build_patch_requirements(plan: PatchRequestPlan) -> tuple[PatchRequirement, ...]:
    requirements: list[PatchRequirement] = []
    for index, target in enumerate(plan.mutation_targets):
        requirements.append(PatchRequirement(
            _requirement_id("target_declaration", target.value, index),
            "target_declaration", target.value, True, "source_declaration",
            "target_identity", target.query_span_start, target.query_span_end,
        ))
    for index, target in enumerate(plan.preserve_targets):
        requirements.append(PatchRequirement(
            _requirement_id("preserve_declaration", target.value, index),
            "preserve_declaration", target.value, True, "source_declaration",
            "target_identity", target.query_span_start, target.query_span_end,
        ))
        requirements.append(PatchRequirement(
            _requirement_id("preserve_constraint", target.value, index),
            "preserve_constraint", target.value, True, "user_request",
            "request_constraint", target.query_span_start, target.query_span_end,
        ))
        if target.value.casefold().endswith((".g.dart", ".freezed.dart", ".pb.go")):
            requirements.append(PatchRequirement(
                _requirement_id("generated_file_constraint", target.value, index),
                "generated_file_constraint", target.value, True, "user_request",
                "request_constraint", target.query_span_start, target.query_span_end,
            ))
    for index, clause in enumerate(plan.behavioral_requirements):
        requirements.append(PatchRequirement(
            _requirement_id("behavioral_contract", clause.text, index),
            "behavioral_contract", clause.text, True, "authoritative_project_doc",
            "behavioral_contract", clause.query_span_start, clause.query_span_end,
        ))
    for index, clause in enumerate(plan.acceptance_conditions):
        requirements.append(PatchRequirement(
            _requirement_id("validation_requirement", clause.text, index),
            "validation_requirement", clause.text, True, "user_request",
            "acceptance_condition", clause.query_span_start, clause.query_span_end,
        ))
    if len(plan.mutation_targets) > 1 and ":across" in plan.surface_id:
        value = "\n".join(target.value for target in plan.mutation_targets)
        requirements.append(PatchRequirement(
            _requirement_id("cross_module_invariant", value, 0),
            "cross_module_invariant", value, True, "authoritative_project_doc",
            "cross_module_invariant",
        ))
    return tuple(requirements)


__all__ = ["PatchRequirement", "PatchRequirementKind", "build_patch_requirements"]
