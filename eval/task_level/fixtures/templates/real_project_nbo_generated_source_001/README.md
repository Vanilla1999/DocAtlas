# NBO Permission Module Snapshot

This benchmark fixture is a sanitized snapshot derived from the local `nbo` Flutter project.

Only the permission module files needed for the task are included. Private git remotes, generated build output, `.git` history, IDE files, and environment files are intentionally excluded.

## Task

Permission UI needs a source-level helper that marks camera, phone, and foreground/background location as critical permissions. Add it to the source-of-truth model file, not generated Freezed output.

## Local constraints

- Follow `lib/modules/permission/ARCHITECTURE.md`.
- Model behavior belongs in `lib/modules/permission/data/models/permission_info.dart`.
- Do not hand-edit generated `*.g.dart` or `*.freezed.dart` files.
- Use pinned dependency versions from `pubspec.lock`, especially `permission_handler` version `11.4.0`.
