# NBO Hard Task Design

Purpose: define harder NBO-derived candidate tasks before implementing them. These tasks should test whether DocAtlas helps with private/project/offline context, not whether agents can follow explicit issue text.

## Design Principles

- Issue text should describe user-visible symptoms, not the implementation path.
- Hidden requirements must be discoverable from visible issue text, project docs, source, public tests, or lockfiles.
- Candidates should require more distributed local context than the current NBO smoke fixtures.
- Candidates should include tempting wrong locations that are plausible from nearby code alone.
- Candidates should include pinned-version traps where latest public docs may mislead the agent.
- Candidates should be screened with `repo_only_strict_offline` before any full 4-condition pilot.

Bad issue text: `Add Permission.notification to PermissionService when sdkInt >= 33.`

Better issue text: `Android 13 users can enter scan/browser flows without completing the project's required notification preflight. Fix the permission flow according to the permission architecture docs.`

Bad issue text: `Do not edit generated files.`

Better issue text: `Add the requested permission metadata while following the project source-of-truth conventions.`

## Screening Gate

Run a candidate through strict offline screening before full pilot:

```bash
uv run python -m eval.task_level.runner \
  --screen-tasks \
  --runner codex \
  --model gpt-5.5 \
  --tasks <candidate_task> \
  --conditions repo_only_strict_offline \
  --repeats 2 \
  --run-id <candidate_task>_screening_001
```

Accept if `repo_only_strict_offline` resolves `<= 1/2`, fairness review is clean, base fails, gold passes, hidden requirements are discoverable, and artifact integrity is clean.

Reject as too easy if `repo_only_strict_offline` resolves `2/2`.

Reject as unfair if hidden requirements require oracle-only information, the gold patch is the only plausible solution, or public tests do not exercise intended behavior.

## Candidate A: Distributed Permission Policy

Task id: `real_project_nbo_distributed_permission_policy_001`

Short description: fix scan/browser permission preflight behavior by applying documented Android permission policy in the correct layer.

Symptom-style issue: `Some scan/browser flows allow users to continue even though the permission preflight does not match the documented Android permission policy. Fix the permission policy in the correct layer.`

Why repo_only may struggle: the symptom does not name the exact API, service method, or wrong files. The correct patch requires combining module architecture docs, notification docs, browser/scan preflight docs, the lockfile, and nearby source.

Why DocAtlas should help: DocAtlas can retrieve and condense the relevant local project docs and pinned dependency context into an action-oriented context pack.

Visible sources required: `README.md`, `lib/modules/permission/ARCHITECTURE.md`, `docs/permission-notifications.md`, `docs/browser-scan-preflight.md`, `pubspec.lock`, `PermissionService` source, and presentation provider source as a tempting wrong location.

Hidden requirements: service layer owns policy; presentation provider is not modified; generated files are not modified; pinned `permission_handler` API is respected; Android 13 notification behavior is correct; `locationAlways` remains deferred.

Tempting wrong locations: provider/UI layer patch, flow-specific presentation branch, generated file edit, `photos`/`videos`/`audio` permissions, and early `locationAlways` request.

Fairness risk: if `docs/browser-scan-preflight.md` or public tests do not state the preflight contract clearly enough, hidden tests may become oracle-only.

Expected public tests: Android 13 notification preflight is required for scan/browser flows; existing deferred-location behavior remains visible.

Expected hidden tests: service-layer ownership, provider untouched, generated files untouched, pinned API use, no media permissions, no early background-location request.

Screening plan: implement only this candidate first, validate base-fail/gold-pass, run strict offline screening with 2 repeats, and only then consider DocAtlas pilot.

Accept/reject criteria: accept if strict offline resolves `<= 1/2` and fairness is clean; reject as too easy if strict offline resolves `2/2`; redesign if failures indicate ambiguous docs rather than meaningful context difficulty.

## Candidate B: Generated Policy Source

Task id: `real_project_nbo_generated_policy_source_001`

Short description: add a missing permission metadata policy flag through the source-of-truth model, not generated outputs.

Symptom-style issue: `Permission metadata shown by the app is missing one policy flag. Add it according to the project model conventions.`

Why repo_only may struggle: nearby generated files are large and look directly editable, while the issue does not name the source model or generated-file rule.

Why DocAtlas should help: the source-of-truth convention is local project policy that public docs and Context7 cannot know.

Visible sources required: `docs/generated-files.md`, Freezed source model, generated `.freezed.dart` file as tempting wrong location, runtime public tests, and architecture docs explaining source-of-truth.

Hidden requirements: source model changed; generated files untouched; runtime metadata correct; project convention followed.

Tempting wrong locations: `*.freezed.dart`, `*.g.dart`, tests only, duplicate metadata map in provider.

Fairness risk: if the generated-file policy is only implied by filename, agents may reasonably edit generated output. The policy must be explicit in visible docs/source comments.

Expected public tests: metadata flag exists at runtime and the source model exposes the intended helper.

Expected hidden tests: generated files remain unchanged, provider has no duplicate policy map, and source model contains the change.

Screening plan: validate the fixture, then run strict offline screening only after Candidate A is accepted or rejected.

Accept/reject criteria: accept if strict offline resolves `<= 1/2`; reject as too easy if generated-file docs make the task trivially explicit.

## Candidate C: Permission Handler Version Trap

Task id: `real_project_nbo_permission_handler_version_001`

Short description: fix an Android permission status mapping while keeping dependency versions unchanged.

Symptom-style issue: `The app's permission status mapping is wrong for one Android permission case. Fix it without changing dependency versions.`

Why repo_only may struggle: agents may rely on latest public API memory or invent enum members instead of reading the pinned lockfile and local dependency notes.

Why DocAtlas should help: exact pinned dependency context and local usage notes should be surfaced before code changes.

Visible sources required: `pubspec.lock`, `docs/dependencies.md`, `permission_handler 11.4.0` usage notes, existing source code, and tests with fake permission statuses.

Hidden requirements: `pubspec.lock` unchanged; no latest-only API; runtime mapping correct; imports valid; no invented `Permission` members.

Tempting wrong locations: latest `permission_handler` API, lockfile/version changes, invented permission enum names, and Android permission groups not exposed by the pinned package.

Fairness risk: if the fixture does not include enough pinned API evidence, hidden tests could punish a reasonable public-doc-based solution.

Expected public tests: fake status mapping reproduces the bug and the fixed mapping passes.

Expected hidden tests: dependency files unchanged, no latest-only symbols, no invented permission members.

Screening plan: run after at least one project-doc-heavy candidate, because this isolates pinned dependency behavior.

Accept/reject criteria: accept if strict offline resolves `<= 1/2` and hidden failures are version-related, not arbitrary naming.

## Candidate D: Cross-Module Permission Contract

Task id: `real_project_nbo_cross_module_permission_contract_001`

Short description: make scan and browser flows interpret a shared permission result consistently.

Symptom-style issue: `A permission result is being interpreted inconsistently between scan and browser flows. Fix the shared contract so both flows behave consistently.`

Why repo_only may struggle: a local edit in one caller may pass an obvious public test but fail the shared architecture contract across both flows.

Why DocAtlas should help: the correct solution requires multi-doc project context and architecture constraints across permission, scan, and browser modules.

Visible sources required: permission module architecture docs, scan flow docs, browser flow docs, shared `PermissionService`, two flow callers, and tests for both flows.

Hidden requirements: shared service logic used; both flows fixed; no duplicate permission policy; generated files not modified.

Tempting wrong locations: fix only one flow, duplicate logic in each caller, patch provider instead of service, ignore architecture docs.

Fairness risk: if public tests only exercise one flow, the hidden cross-flow check may be too surprising. Public tests must make the shared contract visible.

Expected public tests: one scan-flow failure and one browser-flow assertion documenting the shared contract.

Expected hidden tests: no duplicated caller policy, both flows fixed, service contains the shared policy.

Screening plan: implement only after Candidate A or C clarifies whether distributed project docs or pinned dependency context produces better differentiation.

Accept/reject criteria: accept if strict offline resolves `<= 1/2`; redesign if the task becomes a simple grep-and-copy change.
