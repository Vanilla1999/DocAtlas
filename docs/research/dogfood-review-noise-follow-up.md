# Dogfood review noise follow-up

## Context

NBO real-project dogfood found medium review/audit value for DocAtlas patch constraints, but also found too much noise for CI/pre-PR blocking.

This follow-up is a product-improvement PR, not benchmark evidence and not a pass-rate claim.

## Problems found

- Artifact pollution: `docs/research/docatlas-dogfood/**` outputs were visible to later constraint extraction and contaminated the next packet.
- UI glue false positives: normal presentation wiring such as `closeMenu()`, `context.push(...)`, and notifier calls was classified as provider/UI policy leakage.
- Missing task-local symbols: task labels/actions were not grounded to nearby existing source symbols such as menu-close or quick-info handlers.
- Manual workflow overhead: dogfood required separate manual steps for constraints, diff capture, validation, and summary notes.

## Changes

- Added default generated-artifact source exclusions for dogfood/eval outputs, `.docatlas/**`, and `.docmancer/**` patch-review artifacts.
- Exposed excluded artifact metadata through `ignored_generated_artifact_sources`, `excluded_source_count`, and warnings.
- Refined provider/UI policy validation so simple UI event wiring is not treated as a policy violation unless it introduces real decision logic.
- Added task-local symbol grounding metadata from quoted labels, enum-like terms, camel/snake/Pascal symbols, and short UI phrases.
- Added `docmancer patch-review` to generate constraints, changed files, patch diff, validation, and a review summary in one command.

## What improves

- Cleaner extraction: prior dogfood/patch-review artifacts are not reused as evidence.
- Fewer UI false positives: button callbacks and existing notifier/navigation calls no longer become policy violations by themselves.
- Better pre-edit context: source-attributed symbol candidates can point reviewers/agents at existing implementation paths.
- Better ergonomics: one command writes review artifacts under `.docatlas/patch-review/<run-id>`.

## What remains unproven

- No broad correctness claim.
- No pass-rate or benchmark superiority claim.
- No claim that DocAtlas replaces tests or human review.
- No claim that the validator is ready as a CI blocker.
- No broad product proof from one NBO dogfood project.

## Next dogfood

Run NBO dogfood again on 2-3 tasks using:

```bash
docmancer patch-review \
  --project-path /home/viadmin/StudioProjects/nbo \
  --task "<task intent>" \
  --base-ref HEAD \
  --strict
```

Review the generated `.docatlas/patch-review/<run-id>/review_summary.md` as a PR attachment, not as an automated correctness proof.
