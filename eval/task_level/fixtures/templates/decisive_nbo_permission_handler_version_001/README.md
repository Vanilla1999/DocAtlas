# NBO Permission Review Snapshot

This benchmark fixture is a sanitized snapshot derived from the local `nbo` Flutter project.

Only the permission review files needed for the task are included. Private git remotes, generated build output, `.git` history, IDE files, and environment files are intentionally excluded.

## Task

Permission review action labels must match how the pinned permission dependency reports status values. Review cards currently show some blocked permissions as retryable and some notification follow-up states as app-settings errors.

## Local constraints

- Follow `lib/modules/permission/ARCHITECTURE.md`.
- Dependency-version behavior is recorded in `docs/dependencies.md` and `pubspec.lock`.
- Keep status classification in `lib/modules/permission/domain/services/permission_status_mapper.dart`.
- Presentation providers should consume the mapper and should not duplicate dependency enum policy.
- Do not change dependency versions to make a symbol available.
