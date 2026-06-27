# Source Project Profile: NBO

## Privacy level

Sanitized real-project-derived fixture.
No live repository access is required by benchmark agents.
No `.git`, credentials, private remotes, environment files, build output, caches, or customer/private data are included.

## Project type

Flutter/Dart mobile application.

## Fixture scope

Only permission-related module excerpts and minimal dependency metadata are included.

## Included context categories

- README excerpts
- permission module architecture docs
- notification permission docs
- permission service source
- generated-file policy examples
- sanitized `pubspec.yaml` / `pubspec.lock` excerpts
- tests designed for benchmark validation

## Excluded context

- full application domain details
- private business logic outside fixture scope
- live repository history
- credentials and environment files
- generated runtime/build outputs
- user/customer data

## Why NBO is useful for DocAtlas benchmark

NBO contains local project conventions that external public docs cannot know:

- where permission policy belongs;
- which files are source-of-truth;
- generated files must not be edited;
- browser/scan preflight flow constraints;
- Android permission behavior must be combined with pinned dependency context;
- `permission_handler` version is pinned.

## Current limitation

The first NBO tasks were fair but too easy: `repo_only_strict_offline` solved all of them without network access.
They should remain smoke/regression fixtures, not proof-of-value fixtures.
