# Project constraint compiler next steps

Date: 2026-06-28
Status: recommendation after benchmark-only prototype and smoke pilot

## Decision

Recommendation: `IMPLEMENT_GET_PATCH_CONSTRAINTS`

Next production PR:

```text
feat: add get_patch_constraints MCP tool
```

Implementation status: this narrow production PR has been implemented as a read-only MCP tool. It adds production `PatchConstraint` / `PatchConstraintPacket` models, a deterministic `PatchConstraintsService`, and the `get_patch_constraints` MCP surface. The tool is designed to provide actionable project constraints for coding agents; it is not evidence that DocAtlas improves coding-agent success.

## get_patch_constraints — expanded deterministic heuristics

The hardening pass expands deterministic extraction without changing `get_docs_context` behavior or adding patch validation. Supported visible project-rule sources include `ARCHITECTURE.md`, `docs/architecture.md`, ADR files, `CONTRIBUTING.md`, root/module READMEs, and maintained docs. The compiler looks for explicit language such as `must`, `must not`, `should`, `belongs to`, `owned by`, `source of truth`, `canonical`, `single source`, `do not duplicate`, `do not bypass`, `do not hardcode`, layer ownership, repository/adapter ownership, and provider delegation.

Owner/source-of-truth extraction handles forms like `PermissionService owns permission policy`, `policy belongs in PermissionService`, `PermissionService is source of truth for policy`, and `Provider delegates to PermissionService`. Generated-file guardrails cover generated artifacts, regeneration/source-model instructions, `build_runner`, `*.g.dart`, `*.freezed.dart`, protobuf outputs, `*.generated.*`, `generated/`, and `dist/`.

Dependency/version constraints remain evidence-bound: they are derived from visible manifests and lockfiles such as `pubspec.yaml`/`pubspec.lock`, `pyproject.toml`, `requirements.txt`, `poetry.lock`, `uv.lock`, `package.json`, lockfiles for npm/pnpm/yarn, `Cargo.toml`/`Cargo.lock`, and `go.mod`/`go.sum` when deterministic versions are available. `changed_files` and task keywords affect ranking and suggested checks only; they must not produce high-confidence invented owners, versions, or hidden-test-derived requirements.

This should be a narrow, experimental production API, not a broad rewrite and not a claim that DocAtlas is better than repo-only prompting.

## Should patch constraints become production API?

Yes, but only as a minimal source-attributed API with conservative language and telemetry.

Rationale:

- The benchmark prototype can build structured `PatchConstraintPacket` artifacts from visible docs/source/lockfiles.
- The new condition can inject a bounded packet and save `patch_constraints.json` / `patch_constraints.md`.
- Constraint usage and post-patch violations are measurable.
- The product direction is more differentiated than raw docs retrieval or Context7-style API help.

Guardrail:

- Do not claim patch constraints improve patch success yet.
- Keep the first API read-only and compiler-only: return constraints, sources, warnings, and token estimate.
- Do not auto-validate or block patches in the first production PR.
- Do not change retrieval/ranking or `get_docs_context` behavior in this PR.

## Should action-checklist remain benchmark-only?

Yes for now.

Action checklist remains useful as an evaluation presentation format, but it is less precise as a product API because it mixes instructions, suggestions, and verification items. Keep it in benchmark/eval until more evidence shows whether checklist-style free text or structured constraints better changes agent behavior.

## Target token budget

Initial target budget:

```text
800-1200 tokens per packet
```

Operational defaults:

```text
max_constraint_packet_tokens = 1200
max_constraints = 12
max_sources = 8
```

Reasoning:

- The smoke pilot packet was 1138 tokens, within the current 1200-token ceiling.
- That packet was used and validated with zero violations, but it did not resolve the task.
- Further work should optimize packet quality before increasing budget.

## What production tool should be implemented first?

Implement first:

```text
get_patch_constraints(project_path, task_or_issue, budget?)
```

Minimum response shape:

```json
{
  "task_id": "optional",
  "constraints": [],
  "suggested_checks": [],
  "warnings": [],
  "source_summary": [],
  "token_estimate": 0
}
```

Do not implement these in the first production PR:

- patch mutation;
- automatic patch rejection;
- hidden-test-derived requirements;
- broad source rewrites;
- full validation enforcement.

## What benchmark evidence is still missing?

Missing evidence:

- A completed two-task or larger pilot where `docatlas_patch_constraints_injected` finishes under the runner timeout.
- At least 3 accepted differentiating tasks where repo-only does not solve everything.
- Repeats greater than 1 for confidence.
- A task where patch constraints improve resolved or hidden-pass rate, not only constraint usage.
- Evidence that token overhead stays inside the 800-1200 token target and does not increase total run cost disproportionately.
- Evidence separating vector retrieval success from `fallback_local_project_context` success.

## Current evidence summary

- Existing cost analysis verdict remains `QUALITY_POSITIVE_COSTLY`.
- Historical artifacts mostly predate constraint packets, so new constraint token fields are unavailable/null there.
- Smoke pilot completed comparable rows for `real_project_nbo_001` only.
- `docatlas_patch_constraints_injected` produced a 1138-token packet, detected constraint use, and had zero post-patch constraint violations.
- No completed smoke condition resolved the task.
- DocAtlas injected smoke rows used fallback-local-project-context, not vector retrieval success.

## Claims guardrail

Can claim:

- DocAtlas can compile visible project docs/source/lockfiles into structured patch constraint packets in the benchmark layer.
- Constraint packets can be injected, bounded, source-attributed, persisted, and measured.
- Post-patch validation can conservatively detect generated-file, lockfile, provider-layer, source-of-truth, duplicate-policy, and unknown cases.

Cannot claim:

- Patch constraints improve coding-agent success.
- DocAtlas is broadly better than repo-only prompting.
- Patch constraints are efficient versus repo-only on current artifacts.
- Fallback-local-project-context is vector retrieval success.


## validate_patch_against_constraints — deterministic post-edit guardrail

Status: production MCP tool added after `get_patch_constraints` stabilization. The intended workflow is:

1. Call `get_patch_constraints` before editing.
2. Edit code.
3. Call `validate_patch_against_constraints` with the returned constraints and caller-supplied `changed_files` or `patch_diff`.
4. Fix deterministic violations.
5. Run tests.

The validator is deterministic best-effort. It can detect clear generated-file edits, lockfile edits, forbidden provider/UI policy logic, and source-of-truth layer edits. It does not call an LLM, does not fetch constraints automatically, does not prove patch correctness, does not replace tests, and does not show benchmark superiority. Unknown results mean manual review is required.

## Recommended PR scope

`feat: add get_patch_constraints MCP tool` should:

1. reuse the benchmark dataclass shape after production API review;
2. derive constraints only from visible indexed project docs/source/manifests/lockfiles;
3. include source attribution for every constraint;
4. include warnings and confidence;
5. enforce packet budget;
6. emit telemetry fields compatible with the benchmark analyzer;
7. stay read-only.

Validation is now available as a separate deterministic best-effort MCP guardrail after the compiler surface stabilized. Keep future claims cautious until targeted task-level evidence exists.
