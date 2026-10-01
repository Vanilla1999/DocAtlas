# Patch-review artifact exclusion and symbol grounding follow-up

## Context

NBO dogfood v2 showed that `docmancer patch-review` improved UX and removed the known UI-wiring false positives, but two blockers remained before another clean dogfood run:

- patch-review output artifacts could still be reused as source evidence by later `get_patch_constraints` runs;
- task-local symbol grounding was useful but imprecise for method-call chains, close-menu wording, and generated asset registries.

This follow-up is product hardening only. It is not benchmark evidence, not a broad value claim, and not a CI/pre-PR blocker rollout.

## Problems fixed

- Patch-review output artifacts are excluded from extraction, including nested `patch-review` / `patch_review` directories under `.docatlas`, `.docmancer`, and research docs.
- Dogfood/review artifact file names are excluded when they appear in dogfood research output paths.
- Method-call symbol grounding now prefers the final meaningful method in call chains, e.g. `ref.read(...).openInfo()` surfaces `openInfo`, not `read`.
- Close-menu phrase aliases were added for Russian and English task wording such as `закрывать шторку`, `закрыть меню`, and `close menu`.
- Generated asset registry candidates are filtered for non-asset tasks and kept only at low confidence for explicit asset/icon/image tasks.

## What this enables

Cleaner NBO dogfood v3 and more trustworthy `review_summary.md` artifacts:

- a previous patch-review summary should not become a source-of-truth constraint in the next run;
- quick-info/menu tasks should surface `openInfo` and `closeMenu` more directly;
- generated asset registries should not dominate symbol notes for non-asset tasks.

## What remains unproven

- No correctness claim.
- No broad product value claim.
- No CI blocker readiness claim.
- No repo-only or Context7 comparison.
- No claim that constraint use caused better code.

## Next step

Run NBO dogfood v3 with the same two tasks or one new small real task and compare:

- artifact pollution;
- useful symbol candidates;
- false positives;
- unknown/manual-review count;
- review summary quality.
