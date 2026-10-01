# Change-aware documentation review

DocAtlas can inspect a diff and report which maintained documentation should be reviewed. The feature is intentionally advisory: it does not generate or modify repository docs on its own.

## Local use

```bash
doc-atlas docs-impact --base origin/main
doc-atlas docs-impact --changed-file packages/auth/src/token_service.ts
doc-atlas docs-impact --changed-file apps/web/src/routes.ts --fail-on-missing
doc-atlas docs-impact --base origin/main --sync-saved-docs --format json
```

Use `--format json` for CI integrations. With `--base`, DocAtlas reads added, copied, modified, deleted, and renamed paths from `git diff`; `--changed-file` is useful when the caller already has a changed-file list.

The JSON report contains `authoring_brief`, an evidence-bounded instruction for the host coding model. It names allowed files and headings, code/config/test facts to verify, missing evidence, and claims that must not be invented. DocAtlas itself never writes project Markdown.

After a reviewed documentation edit is saved, use the returned `prepare_docs(action="sync_project_docs")` arguments. Incremental sync accepts `changed_paths`, `deleted_paths`, and `{old_path,new_path}` entries in `renamed_paths`; unchanged content produces zero derived writes, deleted content is removed from retrieval, and the result includes bounded tombstones and reprocessing metrics.

`--sync-saved-docs` is an optional local CI adapter. It requires `--base/--head` so rename and deletion status comes from exact Git evidence. It may index files already present in that accepted snapshot, but does not author files, commit, push, post comments, or access the network.

## Result

The report distinguishes:

- `updated`: a maintained project-doc file changed in the diff.
- `review_required`: code or dependency metadata changed and a maintained document maps to that area.
- `missing`: a recognized module changed but has no maintained module documentation.

The GitHub Actions `docs-impact` job writes a Markdown version to the pull-request job summary. It is informational by default. Teams that want a blocking policy can run the same command with `--fail-on-missing`.

## Current mapping

Module paths under `packages/`, `apps/`, `services/`, `modules/`, `libs/`, `crates/`, `plugins/`, `components/`, `lib/modules/`, and `lib/features/` map to their discovered `README` and `docs/` files. General project code maps to root README/architecture docs; dependency manifests and lockfiles map to a discovered root README, or are reported as a documentation gap when none exists.

This is a review map, not proof that documentation is correct. An agent should use `get_docs_context` to read the selected docs and propose a normal, reviewable documentation diff when an update is needed. A rejected or merely proposed patch must not be synced as accepted project truth.
