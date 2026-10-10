# Dictionary exit: conservative admission slice

**Historical executor report, superseded by combined PRIMARY integration.**
Current status, fixes and next tasks:
[`CONTINUE_HERE_RU.md`](../../../v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/CONTINUE_HERE_RU.md).
The paths/action items/test counts below describe the first slice, not final state.

Worktree: `/tmp/opencode/dictionary-exit-admission`. No commit, external request,
existing test edit, threshold reduction, or frozen-corpus change. This is an
implemented bounded slice, **not a full dictionary-exit or acceptance claim**.

## Integrated interface agreement

- `DocumentationQueryPlan` / `DocumentationLookup` DTO remains owned by the
  other executor. Its live producer must issue **only the complete original
  question and explicitly supplied host lookups**, with `original/direct` and
  `host_lookup/host_lookup` lanes respectively. No inferred path, technical-term,
  component, concept, relation, intent, or need probes. Never shorten the original
  question into a generated retrieval query, including on fallback.
- Original and each explicit lookup are independent. No audited rewrite, public
  parent, derived-parent coverage, or implicit inheritance of another lane's
  policies. `derived_parent_trace` now always returns `None`; qualification rejects
  nonliteral origins/relations, parents and derived lineage. Anonymous legacy
  traces are retained for helper compatibility, not proof of host input provenance.
  Producers must supply honest original/lookup identity and text.
- Project answer DTO and helper call signatures remain. Its compiler now returns
  no subjects, expected values, proof obligations, retrieval hints or concepts.
  It hashes the complete original question; the historical 4,000-character input
  ceiling remains recorded/fail-closed through selector requirements.
- Ordinary read requirements contain technical literal/scope bindings only, not
  inferred semantic needs. `library_requirement_contract` is accepted for ABI
  compatibility but ignored: index/dispatcher-generated API/code expectations are
  not an explicit user task contract. Explicit requirements use the existing
  `public_requirements` / scope inputs and retain provenance/budget validation.
- Every selector `docs_answer` result is unsupported, even with complete lexical
  assignments, explicit source paths, or supplied typed requirements. Generic/SDK
  and mixed-selection children cannot use lexical coverage as answer authority.
  Eligible candidates may remain selected as context; selection/assignment hashes
  still bind the actual decision. The support packet records
  `unsupported_answer_authorization:context_only` as missing, not an inferred
  mandatory NL requirement.
- `qualify_evidence` preserves source identity/currentness/risk/lifecycle,
  reference/source-window validation, Markdown boundaries, exact subjects, lexical
  floors and exact-term checks. It no longer invokes semantic need admission.
  Its qualified trace means crop-local retrieval attribution, **not entailment**.
- Mutation readiness is not granted by read selection. Action-packet validation,
  explicit target checks, mandatory-loss handling and the separate
  `packet_valid AND mutation_ready AND mandatory_assignments_survived` edit gate
  are untouched. New tests exercise all three negative edit-gate cases.

## Other-file integration actions (not edited here)

1. `domain/documentation_query_plan.py`, `project_retrieval_intent.py`,
   `project_query_intent.py`, `question_surface_normalization.py`,
   `question_component_rewrite.py`, `retrieval_routing.py`, and
   `application/need_query_schedule.py`: remove remaining semantic query producers
   and rewrite-parent authorization; preserve DTO fields conservatively. A producer
   emitting old generated lanes will now get a `nonliteral_retrieval_lane` rejection.
2. `application/_project_docs_service_part03.py`: do not fabricate cross-lane
   original coverage or schedule inferred needs. Its final projection should retain
   original/explicit lookup quotations with honest independent IDs and false
   answer/edit flags, without converting missing semantic needs into a refusal to
   expose otherwise eligible context. This slice accepts context recall loss.
3. Excluded `project_doc_ranking.py`, `snippets.py`, `context_hint_policy.py`,
   `query_terms.py`, `context_windows.py`, `technical_terms.py`, `lifecycle_policy.py`
   and `tool_selection.py`: remove topic/synonym/routing rules without lowering
   technical eligibility, literal/span constraints, freshness or network guards.
4. Core/retrieval/MCP owners: dispatcher/config/search can still synthesize queries,
   library API contracts or topic boosts. This slice does not change them. Ensure
   explicit version/hash/budget/network contracts still apply before retrieval.
5. Preexisting supported canonical decisions supplied to
   `application/model_visible_projection.py:project_docs_answer` are still trusted
   by that facade. New selectors cannot produce supported docs decisions, but an
   independent supplied/cached old decision is a remaining compatibility path.
   Integrator must not present it as certified dictionary-free support.
6. New test collection requires diagnostic-manifest classification by its owner.
   Do not edit the frozen inventory merely to make this branch green. Until then,
   `--noconftest` below is only a standalone new-test run, not the repository gate.

## Removed mechanisms and retained safety

Removed D04 query aliases/product commands; D18 answer-compiler lifecycle inference;
D21 RU/EN words/forms/actions/states/pattern grammar and downstream relation proof;
D22 command/workflow expected-answer rules; D23 planned subject aliases, semantic
terms and topic-specific proof; D24 attribute/inventory synonym maps and D23 inline
cleanup/index derivations; selector comparison/result-access/architecture/etc.
facets and index-contract expected code; D36 semantic density/normative source-fact
proof; D15 legal-intent vocabulary; D34 comparison relation admission dictionaries.
The runtime frozen-question import in evidence requirements was removed; frozen
questions/tests themselves were not changed. Unknown semantic obligations stay
uncovered, not automatically accepted.

Retained: immutable DTO shape/validation, identifiers and explicit spans, general
numeric parsing, Markdown/code/JSON structural parsing, source identity/version,
snapshot/hash/span binding, trust/risk/currentness guards, declared constraints,
caps and budgets, mandatory-loss downgrade, and separate mutation safety.

## Remaining semantic mechanisms (still OPEN)

Within owned files, `question_plan.py` / `question_plan_core.py` and other
`question_plan_*` / `question_semantic_frames.py` still compile semantic facets;
`question_retrieval_needs.py`, `query_reference_binding.py`, `need_composition.py`,
`need_contracts.py`, `admission_local_binding.py`, `question_premise_proof.py`,
`governance_value_proof.py`, `answer_completeness.py`, `request_intent.py`,
`mutation_intent.py`, `context_request_preferences.py`, and `quality.py` retain
semantic rules. The default answer-requirement compiler no longer uses QuestionPlan,
and crop qualification no longer uses need admission; other callers and supplied
legacy contracts can still reach these rules. Reference binding is still called by
crop qualification. Default mutation/task and need/context planning rules are
**still reachable** elsewhere, not declared technical exemptions.

`_answer_units_shared.py` / `_answer_units_part02.py` still contain legacy
predicate/value/inventory proof and product-specific contract facts, reachable
through supplied obligations. `_evidence_selection_part02.py` retains legacy
behavioral-contract/cross-module/policy lexical proof for explicit patch contracts;
`_PATCH_FACT_RE` and qualifier/authority parsing remain. Patch constraint/review and
project-context shared/application rules (D09/D14/D29/D30/D35), subject-lead and
query-block scoring, dependency inference and context stopping are not migrated.
Excluded domain files and core/retrieval/MCP dictionary families remain outside
this patch. No claim that all remaining tables or call paths have been audited.

## Verification

Interpreter: `/tmp/opencode/docatlas-stage3-integration-active/.venv/bin/python`.
All commands use `PYTHONPATH=/tmp/opencode/dictionary-exit-admission`.

- New tests normal collection: exit 4, `diagnostic_unclassified` for the new file.
- `pytest --noconftest tests/test_dictionary_exit_admission.py -q`: **29 passed**.
- Normal bounded existing run of `tests/docs/test_evidence_selection.py`,
  `test_project_answer_contract_v2.py`, `test_evidence_qualification.py`, and
  `test_admission_guard_composition.py`: **40 failed, 83 passed**. Full output:
  `/tmp/opencode/dictionary-exit-admission-existing-tests.log`.
  Failures include removed question-derived requirements/expected commands,
  positive support assertions, historical-answer projection, generated-need
  admission and context recall. Some diagnostic-shape assertions fail because
  nonliteral lanes are rejected earlier. These are recorded failures, not a
  passed baseline or automatically approved test migrations.
- Network-disabled service run (`socket.socket.connect` raises) of
  `tests/docs/test_library_docs_service.py` and `test_project_context_service.py`:
  **2 failed, 29 passed**. Full output:
  `/tmp/opencode/dictionary-exit-admission-service-tests.log`. Failures:
  `test_auto_mode_inferred_dependency_cannot_hide_supported_local_docs_answer`
  (now confirmation_required) and
  `test_project_context_budget_overflow_keeps_answer_when_retained_trusted_evidence_is_complete`
  (answer_available remains false).
- `git diff --check`: passed. No external requests or full acceptance run.

## Changed paths

Production paths under `docmancer/docs/`:

```
application/_evidence_selection_part01.py
application/_evidence_selection_part02.py
application/_evidence_selection_part03.py
application/_evidence_selection_shared.py
application/evidence_requirements.py
application/evidence_semantic_density.py
application/need_context_disposition.py
domain/_answer_units_part01.py
domain/_answer_units_part02.py
domain/_project_answer_contract_part01.py
domain/_project_answer_contract_part02.py
domain/_project_answer_contract_shared.py
domain/admission_grammar.py
domain/admission_relations.py
domain/evidence_qualification.py
domain/project_answer_contract.py
domain/question_plan_command_rules.py
domain/question_plan_proof.py
```

Also: this integration note and `tests/test_dictionary_exit_admission.py` only.
Patch output: `/tmp/opencode/dictionary-exit-admission.patch`.
