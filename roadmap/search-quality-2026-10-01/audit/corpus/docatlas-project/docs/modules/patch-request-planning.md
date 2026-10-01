# Patch request planning module

`PatchRequestPlan` is the bounded, polarity-aware interpretation contract for
reviewed imperative change requests. It is independent from `QuestionPlan`:
documentation-answer obligations cannot authorize a patch, and patch
requirements cannot authorize a documentation answer.

## Responsibility

`docmancer/docs/domain/patch_request_plan.py` parses only complete reviewed EN
and RU imperative surfaces. It records the operation, mutation and preserve
targets, destination or parent context, behavioral and acceptance clauses,
exact source spans, provenance, and unresolved residue. Unsupported grammar,
implicit targets, overflow, and polarity conflicts fail closed.

`docmancer/docs/domain/mutation_intent.py` resolves the immutable plan against
local source declarations. Every mutable and preserved symbol requires one
unique declaration path; exact paths require an exact local path witness.
Create, delete, and rename operations additionally enforce their
operation-specific parent, existence, and collision contracts.

## Requirement boundary

Patch selection uses only the typed requirements produced from the patch plan:

- `target_declaration` and `preserve_declaration` bind requested identities;
- `behavioral_contract` and assignment-bound `cross_module_invariant` entries
  bind coordinated behavior across multiple mutation targets;
- `preserve_constraint` retains explicit negative polarity;
- `generated_file_constraint` prevents direct edits to generated artifacts;
- `validation_requirement` binds explicit validation expectations.

Canonical project policy becomes mandatory only when it proves a request-local
patch requirement. Retrieval may not synthesize new mutation targets.

## Authorization

Routing permits investigation, not editing. A recovery projection always has
`investigation_allowed=true`, `source_search_status=required`, and
`edit_ready=false`.

A successful public `patch_context` may set `edit_ready=true` only when:

1. the complete patch plan has no unresolved parts;
2. all mutation and preserve targets resolve under the operation contract;
3. the ActionPacket preserves every mandatory evidence assignment;
4. packet and public projection validation succeed within their token bounds;
5. top-level and nested mutation readiness agree.

Cross-module witnesses must be canonical normative statements and remain cited
in `required_invariants`. Missing proof or loss of a mandatory assignment during
budget fitting returns `insufficient_evidence`, requires local source search,
and keeps `edit_ready=false`. Ordinary truncation may remain edit-ready only
when every mandatory assignment survives.

Preserve targets remain cited constraints and never enter the editable target
surface.

## Frozen contracts

`tests/docs/test_patch_request_plan.py`,
`tests/docs/test_patch_requirements.py`,
`tests/docs/test_patch_context_public.py`, and
`scripts/run_patch_surface_gate.py` protect this boundary.
