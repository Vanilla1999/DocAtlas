# Change-aware documentation review

DocAtlas can inspect a diff and report which maintained documentation should be reviewed. The feature is intentionally advisory: it does not generate or modify repository docs on its own.

## Local use

```bash
doc-atlas docs-impact --base origin/main
doc-atlas docs-impact --changed-file packages/auth/src/token_service.ts
doc-atlas docs-impact --changed-file apps/web/src/routes.ts --fail-on-missing
```

Use `--format json` for CI integrations. With `--base`, DocAtlas reads added, copied, modified, deleted, and renamed paths from `git diff`; `--changed-file` is useful when the caller already has a changed-file list.

## Result

The report distinguishes:

- `updated`: a maintained project-doc file changed in the diff.
- `review_required`: code or dependency metadata changed and a maintained document maps to that area.
- `missing`: a recognized module changed but has no maintained module documentation.

The GitHub Actions `docs-impact` job writes a Markdown version to the pull-request job summary. It is informational by default. Teams that want a blocking policy can run the same command with `--fail-on-missing`.

## Current mapping

Module paths under `packages/`, `apps/`, `services/`, `modules/`, `libs/`, `crates/`, `plugins/`, `components/`, `lib/modules/`, and `lib/features/` map to their discovered `README` and `docs/` files. General project code maps to root README/architecture docs; dependency manifests and lockfiles map to a discovered root README, or are reported as a documentation gap when none exists.

This is a review map, not proof that documentation is correct. An agent should use `get_docs_context` to read the selected docs and propose a normal, reviewable documentation diff when an update is needed.
