# P0 governance value-proof remediation

Status: implementation plan. This document freezes the defect model and acceptance gates before code changes.

## Problem statement

A project-doc governance question can currently be declared fully supported when selected text merely says that a policy, version pin, ownership rule, or deferred behavior is documented somewhere, without exposing the requested value itself. This violates the project-answer contract: planning owns what must be proven, selection may prove or reject that obligation, and a retrieval/navigation hit is not substantive proof.

The confirmed failure chain is:

1. `governance_facets` emits generic relation facets with `response_mode="value"`, but without enough typed value semantics for ownership, version, required behavior, or deferred state.
2. governance local proof accepts partial subject-token overlap plus a governance-looking predicate.
3. metadata-only `navigation_only` rejection cannot catch ordinary project prose such as "the version pin is recorded in pubspec.lock".
4. assignments created by that proof make `mandatory_coverage=1.0`; this is an internal selector-coverage metric, not an independent semantic-quality check.
5. final projection revalidates the same local-proof predicate, so a systematic semantic false positive survives twice.
6. MCP may then expose `answer_supported=true`, encouraging the coding agent to stop source follow-up.

## Scope

This PR closes the P0 proof-authority defect without retuning retrieval thresholds or loosening fail-closed behavior.

Implementation requirements:

- classify governance facets into typed proof semantics where the surface supplies enough intent: ownership, version, required behavior, deferred/remaining state, and generic governance facts;
- bind governance rules to `proof_role="project_rule"` so supporting overview text cannot authorize project policy;
- require a substantive value-bearing proposition for governance proof, not merely subject overlap plus `policy`/`rule`/`pin`/`documented` language;
- reject navigation/meta formulations such as `documented in`, `explained in`, `recorded in`, `see`, or equivalent when they do not contain the requested value;
- preserve positive support for explicit propositions such as `PermissionService owns ...`, `Android 13 requires ...`, `Background location remains deferred ...`, and `permission_handler version is 11.4.0`;
- keep projection validation and selector hashes deterministic;
- add adversarial regressions at selector and production MCP quality-path levels.

## Required negative controls

All of the following must fail closed for the corresponding mandatory facet:

- `Policy ownership is documented in ARCHITECTURE.md.`
- `Notification permission requirements are documented in permission-notifications.md.`
- `Background location policy is documented in permission-notifications.md.`
- `The permission_handler version pin is recorded in pubspec.lock.`
- mixed README-style summaries that mention every governance noun but contain none of the requested values.

A navigation summary must never produce `answer_supported=true`, `mandatory_coverage=1.0`, or a direct MCP answer for the five-facet governance question.

## Required positive controls

The existing substantive governance answer remains supported when evidence states the values directly:

- shared browser/scan preflight scope is governed by the same policy;
- `PermissionService` owns the policy;
- Android 13+ requires notification permission before startup;
- background location remains deferred from preflight;
- pinned `permission_handler` version is `11.4.0`.

## Review gates

Before merge:

1. exact PR head is reviewed from the GitHub diff, not from the PR description;
2. focused governance/evidence-selection tests pass;
3. project-answer production-path quality tests pass;
4. full repository CI on the exact reviewed head passes;
5. no retrieval budget/threshold is weakened to make tests green;
6. no unrelated public API expansion is introduced;
7. branch is deleted after successful merge.
