# RU Semantic Frames and Patch Context Completion

**Status:** In progress (implementation, runtime verification, and benchmark complete; repository lint baseline pending)  
**Baseline commit:** `ef7f958` (`feat: add RU semantic and patch request planning`)  
**Workstream:** QuestionPlan RU surfaces and PatchRequestPlan authorization  
**Unrelated plan:** `2026-07-20-natural-language-library-retrieval.md` must not be modified by this work

## 1. Objective

Finish two independent public contracts:

1. Reviewed Russian documentation questions compile through `QuestionPlan` and require proposition-local evidence.
2. Reviewed imperative patch requests compile through `PatchRequestPlan`, resolve every mutation and preserve target, select patch-specific evidence, and produce edit-ready `patch_context` only after the complete mutation contract is validated.

The primary end-to-end request is:

```text
Fix partial permission handling in BrowserPermissionGate, ScanPermissionGate,
OfflineSyncGate, and PermissionService without changing
permission_result.freezed.dart.
```

The required public result is:

```json
{
  "kind": "patch_context",
  "status": "ok-or-truncated",
  "edit_ready": true,
  "mutation_ready": true,
  "mutation_intent": {
    "operation": "modify",
    "ready": true,
    "resolved_targets": [
      "BrowserPermissionGate",
      "ScanPermissionGate",
      "OfflineSyncGate",
      "PermissionService"
    ],
    "preserved_targets": [
      "permission_result.freezed.dart"
    ]
  }
}
```

## 2. Fixed Invariants

1. `QuestionPlan` only authorizes documentation answers.
2. `PatchRequestPlan` only interprets patch requests.
3. Docs-answer obligations never enter patch selection.
4. Patch requirements never authorize a docs answer.
5. Routing may authorize investigation but never editing.
6. `edit_ready=true` requires `mutation_ready=true`.
7. Implicit domain nouns never become mutation targets.
8. Generic source references never authorize target resolution.
9. Every mutation target requires a unique declaration or exact path witness.
10. Every preserve target is resolved independently and never enters the editable target set.
11. Unknown tails, input-limit overflow, and ambiguity fail closed.
12. Token compaction cannot remove polarity, mandatory targets, or mandatory requirement assignments from a successful packet.
13. The existing frozen QuestionPlan `100/100` surface remains unchanged.
14. Deletion of `AGENTS.md` is intentional; maintained-document inventories and tests must be updated instead of restoring it.
15. One request must never pass through both requirement systems.

## 3. Target Pipeline

```text
Public request
    |
    +-- is_change_request == false
    |       +-- QuestionPlan
    |       +-- ProjectAnswerRequirementContract
    |       +-- docs-answer evidence
    |       +-- docs_answer projection
    |
    +-- is_change_request == true
            +-- PatchRequestPlan
            +-- MutationIntentContract(plan)
            +-- PatchRequirementContract
            +-- declaration coverage lane
            +-- authoritative behavioral docs
            +-- mutation readiness
            +-- ActionPacket
            +-- patch_context projection
```

## 4. Phase 0: Freeze RED Contracts

### Files

```text
tests/docs/test_patch_request_plan.py
tests/docs/test_patch_context_public.py
tests/docs/test_patch_requirements.py
tests/docs/test_question_plan_v4.py
tests/diagnostic_labels.json
eval/project_answer_surface_v2/
scripts/run_patch_surface_gate.py
```

### Work

1. Add a dedicated `PatchRequestPlan` unit-test module.
2. Add public end-to-end tests through `handle_context_tool()` or the unified context service.
3. Do not treat direct `build_action_packet()` tests as public acceptance.
4. Add a separately versioned frozen RU semantic corpus.
5. Add a frozen patch-request surface gate.
6. Review and update diagnostic node hashes after adding tests.

### Required RED Cases

| Request | Required result |
|---|---|
| Exact four-target permission request | Public ready `patch_context` |
| `Fix the permission architecture.` | Patch recovery, not edit-ready |
| `Make browser and sync consistent.` | Patch recovery, not edit-ready |
| `Update the relevant files.` | Patch recovery, not edit-ready |
| `Исправь связанные модули.` | Patch recovery, not edit-ready |
| `Please fix BrowserPermissionGate` | Audited wrapper or fail closed; no fallback |
| `Fix BrowserPermissionGate and delete everything` | Unknown residue, fail closed |
| `Update FooService so that BarDecision is returned` | Only `FooService` is mutable |
| `Fix FooService without changing FooService` | Polarity conflict |
| `Fix FooService without changing missing.g.dart` | Preserve target unresolved |
| Two `FooService` declarations | Ambiguous, not ready |
| `FooService` only in comments or tests | Not a declaration witness |
| `Create a separate completion plan ...` | Investigation only; never edit-ready without an explicit target |

### Exit Criteria

All new tests fail for the intended contract gaps before production edits begin.

## 5. Phase 1: PatchRequestPlan V2

### Files

```text
docmancer/docs/domain/patch_request_plan.py
docmancer/docs/domain/request_intent.py
tests/docs/test_patch_request_plan.py
```

### Required Model

Add typed clauses, target roles, consumed spans, operation-specific context, and explicit provenance. The plan must include:

```text
operation
mutation_targets
preserve_targets
parent_context
scope_terms
behavioral_requirements
acceptance_conditions
consumed_spans
unresolved_parts
language
surface_id
schema_version
```

Every target must include:

```text
value
kind: path | symbol
role: mutate | preserve | destination | parent
query_span_start
query_span_end
provenance: user_request | explicit_task_contract
```

### Reviewed English Grammar

```text
Fix <Behavior> in <TargetList>.
Fix <Behavior> across <TargetList>.
Update <TargetList> so that <Acceptance>.
Refactor <TargetList> without changing <PreserveList>.
Fix <TargetList>; do not edit <PreserveList>.
Delete <TargetList>.
Rename <Source> to <Destination>.
Create <DestinationPath> in <ParentPathOrModule>.
```

Only explicitly reviewed wrappers are allowed:

```text
Please fix ...
Please update ...
```

Do not implement generic polite-prefix stripping.

### Target List Grammar

Allow exact paths, qualified symbols, CamelCase declarations, snake-case identifiers, and backtick-quoted exact identifiers. Allow comma and `and` separators only through reviewed list forms.

Reject implicit targets such as `relevant files`, `related modules`, `permission architecture`, `browser flow`, `scan flow`, `offline sync`, and `the implementation`. These may only become bounded search hints or `scope_terms`.

### Span Policy

1. Every clause records its exact source span.
2. Every meaningful character belongs to a consumed span.
3. Only reviewed punctuation and connectors may occur between consumed spans.
4. Any residue produces `unresolved_patch_clause:<text>`.
5. Bounds overflow produces an unresolved input-limit reason; never silently truncate.
6. Target extraction runs only inside a parsed `TargetList` span.
7. Acceptance and preserve clauses are never rescanned as mutable regions.
8. `surface_id` identifies the exact grammar family.

### RU Policy During This Phase

Russian imperative requests route to patch recovery but remain unsupported for edit authorization:

```text
language=ru
operation=none
unresolved_parts=("unsupported_patch_surface:ru",)
```

### Exit Criteria

1. Parser tests pass.
2. Unknown tails fail closed.
3. Acceptance symbols do not become mutation targets.
4. Polarity conflicts fail closed.
5. Bounds never silently truncate authorization data.

## 6. Phase 2: Remove Authorization Fallback

### Files

```text
docmancer/docs/domain/mutation_intent.py
docmancer/docs/domain/request_intent.py
tests/docs/test_action_packet.py
tests/docs/test_patch_request_plan.py
```

### Work

1. Make `build_mutation_intent()` consume an immutable `PatchRequestPlan`.
2. Keep a transitional question wrapper only if it builds the plan once and delegates.
3. Remove global operation regex fallback from unsupported plans.
4. Remove fallback path and symbol scanning from unsupported plans.
5. Return `operation=none`, no requested targets, and `patch_surface_not_supported` for unsupported change requests.
6. Preserve investigation routing with `edit_ready=false`.
7. Add a separate explicit constructor for task/benchmark targets with `explicit_task_contract` provenance.

### Exit Criteria

1. Unsupported plans cannot acquire mutation targets.
2. Question-shaped text containing `fix` cannot become a mutation plan.
3. Audited wrappers work or fail closed explicitly.
4. Direct task contracts use only the explicit constructor.

## 7. Phase 3: Patch-Specific Requirements

### Files

```text
docmancer/docs/domain/patch_requirements.py
docmancer/docs/application/evidence_requirements.py
docmancer/docs/application/_project_context_service_part01.py
docmancer/docs/application/_action_packet_part03.py
tests/docs/test_patch_requirements.py
```

### Requirement Kinds

```text
target_declaration
preserve_declaration
behavioral_contract
cross_module_invariant
preserve_constraint
generated_file_constraint
validation_requirement
```

Every requirement must include a stable ID, kind, bounded value, mandatory flag, provenance, proof role, and optional exact query span.

### Separation

The project service must select exactly one branch:

```python
if patch_request:
    requirements = build_patch_requirements(patch_plan, mutation_intent, explicit_task_contract)
else:
    requirements = build_requirements(question, profile="project_docs_answer")
```

Reject docs-answer requirements in patch packets instead of ignoring them. A user behavior clause states what must be proven; it is not proof. `behavioral_contract` requires authoritative project documentation. A user preserve clause remains mandatory independently of documentation and carries request-plan provenance.

### Exit Criteria

1. Patch selection sees no QuestionPlan obligations.
2. Every target has a mandatory declaration requirement.
3. Behavioral contracts require authoritative docs.
4. Preserve and generated-file constraints survive formatting.

## 8. Phase 4: Declaration Coverage Lane

### Files

```text
docmancer/docs/domain/source_map.py
docmancer/docs/domain/mutation_intent.py
docmancer/docs/application/_project_context_service_part01.py
docmancer/docs/domain/retrieval_routing.py
tests/docs/test_source_map.py
tests/docs/test_patch_context_public.py
```

### Work

1. Add a `mutation_target_declarations` retrieval stage before generic source evidence.
2. Resolve mutation and preserve targets independently.
3. Use priority: exact declaration, exact path, unique filename alias, navigation-only generic reference.
4. Generic references may guide search but never authorize editing.
5. Reserve one best witness per requested target before selecting a second witness for any target.
6. Treat duplicate production declarations as ambiguity.
7. Do not let comments, imports, fixtures, or tests outrank production declarations.
8. Include an explicitly named generated preserve path without enabling broad generated-file traversal.

### Exit Criteria

1. The four permission targets each receive a declaration witness.
2. The generated preserve path receives exact path evidence.
3. Duplicate declarations block readiness.
4. Comment-only references do not authorize targets.
5. Generic ranking cannot starve mandatory target coverage.

## 9. Phase 5: Operation-Specific Readiness

### Files

```text
docmancer/docs/domain/mutation_intent.py
docmancer/docs/application/_action_packet_part03.py
tests/docs/test_action_packet.py
tests/docs/test_patch_context_public.py
```

### Ready Formula

```text
supported operation
and no unresolved plan parts
and every mutation target uniquely resolved
and every preserve target uniquely resolved
and no normalized polarity conflict
and behavioral contract assigned
and every mandatory requirement assigned
and every mandatory assignment survives the packet
```

Apply operation-specific rules:

| Operation | Required readiness |
|---|---|
| modify | Every mutation target exists |
| delete | Every mutation target exists |
| rename | Source exists, destination is explicit, no collision |
| create | Destination does not exist, parent or module context exists |

Preserve targets must appear only in `preserved_targets`, never in editable target surfaces.

### Exit Criteria

All operation-specific, preserve, ambiguity, and polarity readiness tests pass.

## 10. Phase 6: ActionPacket V3

### Files

```text
docmancer/docs/application/_action_packet_shared.py
docmancer/docs/application/_action_packet_part02.py
docmancer/docs/application/_action_packet_part03.py
docmancer/docs/application/_action_packet_part04.py
docmancer/docs/application/model_visible_projection.py
tests/docs/test_action_packet.py
tests/docs/test_action_packet_part02.py
tests/docs/test_model_visible_projection.py
```

### Versions

```text
patch-request-plan-v2
mutation-intent-v3
action-packet-v3
patch-context-v3
```

Every patch packet must contain the request plan, mutation intent, requirements, forbidden changes, assignment-survival data, and contract hashes. The request plan is required even when no preserve targets exist.

Support two forbidden-change provenance forms:

```text
source-backed: evidence_ids + authoritative_project_doc provenance
request-backed: request_plan_hash + exact query span + user_request provenance
```

Never invent evidence IDs for user-request constraints.

### Compaction

Optional metadata, navigation hints, explanations, uncertainties, and optional snippets may be removed first. A successful packet may never lose request identity, mutation targets, preserve targets, polarity, mandatory requirements, mandatory assignments, readiness reasons, or hashes.

If mandatory data cannot fit, return insufficient evidence and set both readiness flags false.

### Exit Criteria

1. Tampered hashes fail validation.
2. Removed preserve targets fail validation.
3. Changed polarity fails validation.
4. Missing request plans fail validation.
5. Budget overflow fails closed.
6. The exact request fits within 2000 tokens.

## 11. Phase 7: Public MCP Authorization

### Files

```text
docmancer/docs/interfaces/mcp/context_tools.py
docmancer/docs/interfaces/mcp/recovery_projection.py
docmancer/docs/application/_unified_context_service_part01.py
docmancer/docs/application/_project_context_service_part01.py
tests/docs/test_patch_context_public.py
```

### Work

1. Build the patch plan once at ingress and pass the same immutable object through the pipeline.
2. Do not reparse the question inside ActionPacket construction.
3. Replace operation-based `source_search_edit_authorized` with investigation-only `source_search_allowed`.
4. Compute `edit_ready` only from validated packet, validated projection, mutation readiness, and mandatory assignment survival.
5. Force all recovery handoffs to `edit_ready=false`.
6. Publish stable top-level `mutation_ready` and `edit_ready` fields.
7. Reject inconsistent readiness combinations in the projection validator.
8. Route reviewed imperative words such as `make` to patch recovery without authorizing an operation or targets.

### Required Recovery Shape

```json
{
  "kind": "patch_context",
  "investigation_allowed": true,
  "edit_ready": false,
  "source_search_status": "required"
}
```

### Exit Criteria

The exact permission request succeeds through public `get_docs_context`, not only through direct packet construction.

## 12. Phase 8: RU Documentation Surface Completion

### Files

```text
docmancer/docs/domain/question_surface_normalization.py
docmancer/docs/domain/question_plan_proof.py
tests/docs/test_question_plan_v4.py
eval/project_answer_surface_v2/
scripts/run_question_surface_v2_gate.py
docs/modules/question-planning.md
```

### Work

1. Keep the audited surface-adapter architecture unless direct matchers are required by a stronger contract.
2. Require `fullmatch`, bounded captures before canonical rewrite, safe semantic tails, a distinct surface trace, and exact full-source-span rebinding.
3. Reject overlength fields instead of truncating them.
4. Keep a closed RU alias inventory; technical identifiers remain unchanged.
5. Freeze signatures for `decision_for_action`, `argument_value`, `applicable_contract`, `purpose_behavior`, and `behavior_before`.
6. Add wrong-subject, wrong-value, wrong-condition, split-proposition, and missing-ordering negatives.
7. Add punctuation and unrelated-tail mutations.

### Exit Criteria

1. The existing gate remains `100/100`.
2. The new RU gate passes.
3. Every RU case has exact source spans.
4. Unsafe extensions fail closed.
5. Positive and negative local proof covers all five relations.

## 13. Phase 9: RU Imperative Surfaces

Start only after public English patch authorization passes.

Reviewed forms:

```text
Исправь <Behavior> в <TargetList>.
Обнови <TargetList>, чтобы <Acceptance>.
Отрефактори <TargetList> без изменения <PreserveList>.
Исправь <TargetList>; не изменяй <PreserveList>.
```

Compile them into the same canonical operation and polarity model. Do not create a separate Russian mutation-intent implementation.

### Exit Criteria

Equivalent EN and RU requests produce the same semantic plan signature except for language, surface ID, and source spans.

## 14. Phase 10: Documentation and Governance

### Files

```text
.hermes/plans/2026-08-25-ru-semantic-and-patch-context-completion.md
docs/modules/question-planning.md
docs/modules/patch-request-planning.md
docs/modules/question-span-coverage.md
docs/PROJECT_MAP.md
tests/docs/test_documented_cli_contract.py
tests/docs/test_mcp_docs_tools_registration.py
tests/docs/test_user_facing_docs_branding.py
```

### Work

1. Add a patch-planning module document.
2. Document the QuestionPlan/PatchRequestPlan ownership boundary.
3. Document patch requirement kinds and readiness rules.
4. Document investigation versus edit authorization.
5. Remove `AGENTS.md` from maintained-document inventories because its deletion is intentional.
6. Do not restore `AGENTS.md` only to satisfy stale tests.
7. Keep the library-retrieval plan independent.
8. Change this plan from Draft to Complete only after every exit criterion passes.

## 15. Phase 11: Verification

### Focused Tests

```bash
uv run --offline pytest tests/docs/test_patch_request_plan.py -q
uv run --offline pytest tests/docs/test_patch_requirements.py -q
uv run --offline pytest tests/docs/test_patch_context_public.py -q
uv run --offline pytest tests/docs/test_question_plan_v4.py -q
uv run --offline pytest tests/docs/test_action_packet.py tests/docs/test_action_packet_part02.py -q
uv run --offline pytest tests/docs/test_model_visible_projection.py -q
uv run --offline pytest tests/docs/test_source_map.py -q
```

### Frozen Gates

```bash
uv run --offline python scripts/run_question_surface_gate.py
uv run --offline python scripts/run_question_surface_v2_gate.py
uv run --offline python scripts/run_patch_surface_gate.py
uv run --offline python scripts/run_legacy_contract_gate.py
```

### Full Checks

```bash
uv run --offline pytest tests/docs -q
uv run --offline pytest tests -q
uv run ruff check docmancer tests eval
git diff --check
```

Run lint in CI or a dev environment with `ruff` installed if the offline environment lacks the binary. Do not mark lint complete without executing it.

### Provider Smoke

After provider-free checks are green, run the documented two-cell smoke procedure only:

```text
provider-free control
provider/model-enabled comparison
```

Record status, latency, packet tokens, projection tokens, mutation readiness, target coverage, and mandatory-assignment survival.

### Benchmark

Compare correctness, packet and projection tokens, latency, unsupported-success rate, false-edit-ready rate, and target-declaration coverage before and after the change.

## 16. Definition of Done

1. The exact public permission request returns `patch_context`.
2. Top-level and nested mutation readiness are true and consistent.
3. Edit readiness is true only for the complete exact request.
4. All four mutation targets are uniquely resolved.
5. The generated preserve target is uniquely resolved.
6. The preserve target is absent from editable targets.
7. The preserve target appears in request-backed forbidden changes.
8. An authoritative behavioral contract is assigned as mandatory evidence.
9. No docs-answer obligations appear in the patch packet.
10. Every mandatory assignment survives packet and projection formatting.
11. Packet and projection each stay within 2000 tokens.
12. All implicit-target requests are recoverable but not edit-ready.
13. Unsupported grammar cannot use legacy extraction fallback.
14. Every source-search recovery has `edit_ready=false`.
15. The existing QuestionPlan gate remains `100/100`.
16. The new RU and patch gates pass.
17. The complete test suite passes.
18. `AGENTS.md` deletion is reconciled with all maintained-document tests.
19. Ruff and `git diff --check` pass.
20. The two-cell provider smoke is complete.
21. Benchmark comparison is saved.

## 17. Execution Status (2026-08-25)

Completed provider-free contracts:

- exact public permission request is mutation-ready and edit-ready through the indexed project service;
- patch and docs-answer requirements are separated;
- ActionPacket V3 preserves request polarity and mandatory target assignments;
- create, delete, rename, EN, and reviewed RU imperative surfaces are frozen;
- existing question surface gate passes `100/100`;
- RU semantic gate passes `12/12`;
- patch surface gate passes `20/20`;
- legacy contract gate passes;
- focused completion regression set passes `185` tests;
- maintained documentation no longer requires the intentionally deleted repository `AGENTS.md`;
- docs suite passes `1226` tests in isolated storage;
- complete suite passes `3329` tests with `10` expected skips in an isolated home;
- the documented two-cell exploratory smoke completed with a passing canary,
  both cells passing public and hidden tests, and exactly three audited provider
  event streams;
- the directional smoke comparison is saved at
  `eval/task_level/results/task43_smoke_run_20260825_091820/report.md`;
- the frozen before/after patch comparison is saved at
  `eval/patch_request_surface_v1/benchmark-report.md` (`7/20` to `20/20`
  exact outcomes, `3/8` to `0/8` unsafe-success proxy, and `19/24` to
  `24/24` target coverage);
- `git diff --check` passes.

Outstanding operational verification:

- repository-wide `ruff 0.16.4` executes but reports `5248` pre-existing
  violations, so the required lint command is not green; broad unrelated
  auto-fixes are intentionally not applied as part of this plan.
22. No unrelated dirty changes are reverted or included.
23. This plan is marked Complete only after all preceding conditions hold.

## 17. Execution Order for a Coding Model

1. Add RED public and parser tests.
2. Implement PatchRequestPlan V2 grammar.
3. Remove legacy mutation authorization fallback.
4. Add PatchRequirementContract.
5. Add the declaration coverage lane.
6. Implement operation-specific readiness.
7. Version and update ActionPacket.
8. Fix public MCP authorization.
9. Pass the exact public acceptance test.
10. Complete the frozen RU documentation surface.
11. Add RU imperative surfaces.
12. Update documentation and maintained-document tests.
13. Run focused suites after every phase.
14. Run all frozen gates.
15. Run full suites and static checks.
16. Run provider smoke and benchmark comparison.
17. Mark the plan Complete only after every Definition of Done item is proven.

The coding model must not proceed to a later phase until the current phase's exit criteria are demonstrated by tests.
