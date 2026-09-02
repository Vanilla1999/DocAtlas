# Evidence selection module

`EvidenceSelection` assigns retrieved answer units to mandatory requirements and authorizes certified library, dependency, or mixed answers only when every required facet is locally proven.

`ProjectAnswerRequirementContract` is the input boundary emitted by question planning and consumed unchanged by evidence selection.

## Responsibility

The evidence-selection module turns bounded candidates into an auditable certification decision. Project-only reads bypass answer certification and use `ContextSelectionDecision`, which reports retrieval coverage without a support verdict.

Candidate normalization, requirement compilation, proof matching, ranking, budget fitting, and projection identity are separate responsibilities even though they cooperate in one pipeline.

## Contract with question planning

The module consumes the project-answer requirement contract emitted by question planning. It may only mark a mandatory facet covered when a model-visible answer unit locally proves that exact obligation. It does not broaden subjects or replace unresolved question semantics.

This relation is intentionally reciprocal in the documentation: `question-planning` owns **what must be proven**; `evidence-selection` owns **whether the available evidence proves it**.

## Invariants

- a retrieval hit is not proof;
- complete exact proof outranks generic or partial evidence;
- every mandatory selected witness survives final projection revalidation;
- authority, lifecycle, source identity, and visible token cost participate in the deterministic decision;
- a missing mandatory facet yields fail-closed `insufficient_evidence`.

## Tests

`tests/docs/test_evidence_selection*.py`, `tests/docs/test_model_visible_projection*.py`, and provider-free quality protocols protect the selector contract.
