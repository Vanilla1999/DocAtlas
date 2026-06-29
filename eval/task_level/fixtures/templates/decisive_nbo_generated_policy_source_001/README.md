# NBO Permission Module Snapshot

This benchmark fixture is a sanitized snapshot derived from the local `nbo` Flutter project.

Only the permission module files needed for the task are included. Private git remotes, generated build output, `.git` history, IDE files, and environment files are intentionally excluded.

## Task

Permission review must separate immediate browser/scan preflight blockers from permissions that stay deferred follow-up work. Keep that policy in the source-of-truth permission model file, not generated Freezed output.

## Local constraints

- Follow `lib/modules/permission/ARCHITECTURE.md`.
- Model behavior belongs in `lib/modules/permission/data/models/permission_info.dart`.
- Do not hand-edit generated `*.g.dart` or `*.freezed.dart` files.
- Use pinned dependency versions from `pubspec.lock`, especially `permission_handler` version `11.4.0`.
