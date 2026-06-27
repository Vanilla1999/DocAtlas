# NBO Permission Module Snapshot

This benchmark fixture is a sanitized snapshot derived from the local `nbo` Flutter project.

Only the permission module files needed for the task are included. Private git remotes, generated build output, `.git` history, IDE files, and environment files are intentionally excluded.

## Task

Android 13+ devices must request notification permission before browser/scan flows. Add this to the existing permission flow.

## Local constraints

- Follow `lib/modules/permission/ARCHITECTURE.md`.
- Add permission checks in `PermissionService`.
- Do not move permission logic into presentation providers.
- Do not hand-edit generated `*.g.dart` or `*.freezed.dart` files.
- Use pinned dependency versions from `pubspec.lock`, especially `permission_handler` version `11.4.0`.
